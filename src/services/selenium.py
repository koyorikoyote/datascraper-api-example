import subprocess
import tempfile, shutil, atexit
import os
import uuid
import time
import socket
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup, Comment
import httpx
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

from src.utils.decorators import try_except_decorator, try_except_decorator_no_raise
from src.utils.legacy_selenium_contact import LegacySeleniumContact
from src.utils.constants import ExecutionTypeConst, StatusConst
from src.config.config import get_env
import logging

COLUMN_ORDER = [
    "last", "first",
    "last_kana",  "first_kana",
    "last_hira",  "first_hira",
    "email",
    "company", "department", "url",
    "phone1", "phone2", "phone3",
    "zip1", "zip2",
    "address1", "address2", "address3",
    "subject", "body",
]


class RendererTimeoutError(Exception):
    """Raised when Selenium renderer times out, indicating a critical page failure."""
    pass


class SeleniumService:
    """Chrome in a container-friendly, headless configuration."""

    def __init__(
        self,
        headless: bool = True,
        # Environment variable for Selenium Grid URL has to be localhost even in production
        remote_url: str = get_env("SELENIUM_GRID_URL", default="http://localhost:4444/wd/hub"),
    ) -> None:
        self.headless = headless
        self.remote_url = remote_url
        
        # Clean up any stale profiles from previous crashed runs to free up space
        self._clean_stale_profiles()
        
        # spin up Xvfb only when *headed*
        self._xvfb_proc = None
        if not headless and "DISPLAY" not in os.environ:
            self._xvfb_proc = subprocess.Popen(
                ["Xvfb", ":99", "-screen", "0", "1920x1080x24"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            os.environ["DISPLAY"] = ":99"  # Chrome finds the display

        # 2. unique Chrome profile with UUID and timestamp to ensure uniqueness
        unique_id = f"{uuid.uuid4()}-{int(time.time())}"
        self._profile_dir = tempfile.mkdtemp(prefix=f"selenium-profile-{unique_id}-", dir="/tmp")
        
        try:
            # Register cleanup immediately
            atexit.register(self._cleanup)
            
            # Initialize the driver
            self.driver = self._create_driver()
        except Exception:
            logging.error("Failed to initialize SeleniumService, cleaning up profile directory immediately.")
            self._cleanup(force=True)
            raise

        # Suppress benign "Connection pool is full" warnings from urllib3
        logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

    def _clean_stale_profiles(self):
        """Clean up orphaned selenium profiles from /tmp that are older than 1 hour."""
        try:
            tmp_dir = "/tmp"
            if not os.path.exists(tmp_dir):
                return

            current_time = time.time()
            max_age = 3600  # 1 hour in seconds
            
            # Find all directories matching the pattern
            # Using listdir instead of glob for better performance in loose environments
            for filename in os.listdir(tmp_dir):
                if filename.startswith("selenium-profile-"):
                    dir_path = os.path.join(tmp_dir, filename)
                    try:
                        # Check modification time
                        if os.path.isdir(dir_path):
                            stat = os.stat(dir_path)
                            if current_time - stat.st_mtime > max_age:
                                logging.info(f"Removing stale selenium profile: {dir_path}")
                                shutil.rmtree(dir_path, ignore_errors=True)
                    except Exception as e:
                        # Just log and continue, don't crash on maintenance
                        logging.debug(f"Could not check/remove stale profile {dir_path}: {e}")
                        
        except Exception as e:
            logging.warning(f"Error during stale profile cleanup: {e}")
        
    def _create_driver(self):
        """Create a new WebDriver instance with the configured options."""
        opts = Options()

        # Choose headless vs headed
        if self.headless:
            opts.add_argument("--headless")

        # Set page load strategy to eager to fix timeouts on heavy sites
        # This makes Selenium return control as soon as DOM is interactive
        opts.page_load_strategy = 'eager'

        # Common hardening flags
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        
        # Use unique user data directory for each session
        opts.add_argument(f"--user-data-dir={self._profile_dir}")
        
        # Add additional flags to help with concurrency issues
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-application-cache")
        opts.add_argument("--disable-session-storage")

        # Set a common User-Agent to avoid simple bot blocking (which causes timeouts)
        opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # Connect to the Grid running on port 4444 
        logging.info("Creating new WebDriver session")
        
        driver = None
        max_retries = 2 # Changed from 5 to 2 as per requirement (1 retry only)
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                driver = webdriver.Remote(
                    command_executor=self.remote_url,
                    options=opts,
                    keep_alive=True,
                )
                break
            except Exception as e:
                # Attempt to cleanup any partial/stuck session if we have a reference
                # This mirrors the reset_driver behavior requested as fallback
                try:
                    if hasattr(self, 'driver') and self.driver:
                        self.driver.quit()
                except Exception:
                    pass

                error_msg = str(e)
                if attempt < max_retries - 1:
                    wait_time = retry_delay
                    
                    # Check for 504 Gateway Timeout specifically
                    if "504 Gateway Timeout" in error_msg or "Gateway Time-out" in error_msg:
                        logging.warning(f"Gateway Timeout (504) detected. Infrastructure might be overloaded.")
                        wait_time = 45 # Wait 45s to allow container/service recovery
                    
                    # Check for Session Creation Timeout specifically
                    if "New session request timed out" in error_msg:
                        logging.warning(f"Session creation timed out. Grid might be overloaded.")
                        wait_time = 45 # Wait 45s to allow Grid recovery

                    logging.warning(
                        f"Failed to create WebDriver session (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time}s... Error: {error_msg[:200]}"
                    )
                    time.sleep(wait_time)
                    
                    # Only exponential backoff if it's not a special long wait
                    if wait_time == retry_delay:
                        retry_delay *= 2
                else:
                    logging.error(f"Failed to create WebDriver session after {max_retries} attempts.")
                    raise e
        
        # Set timeouts
        driver.set_page_load_timeout(60)     # 1 minute for page loads
        driver.set_script_timeout(30)        # 30 seconds for scripts
        
        # Configure the command executor with reasonable timeout
        # Set to 120s (2 mins) to safely cover the 60s page_load_timeout plus overhead
        driver.command_executor._conn.timeout = 120 
        
        return driver
        
    def init_session(self) -> str:
        """Return the underlying WebDriver's session ID."""
        if not self._is_session_valid():
            self._ensure_valid_session()
        session_id = self.driver.session_id
        logging.info(f"Initialized Selenium session: {session_id}")
        return session_id
    
    def _is_session_valid(self):
        """Check if the current WebDriver session is valid."""
        try:
            # A simple command that should work if the session is valid
            self.driver.current_url
            return True
        except WebDriverException:
            logging.warning("WebDriver session is invalid, will recreate")
            return False
            
    def _ensure_valid_session(self):
        """Ensure the WebDriver session is valid, recreating it if necessary."""
        if not self._is_session_valid():
            try:
                # Try to quit the old driver first
                self.driver.quit()
            except Exception:
                pass  # Ignore errors when quitting an already invalid driver
                
            self.driver = self._create_driver()
            logging.info("WebDriver session recreated successfully")

    def reset_driver(self):
        """
        Forcefully quit the current driver and create a new one.
        Useful when a thread is stuck or the driver is in a bad state.
        """
        try:
            logging.warning("offloading stuck driver...")
            if self.driver:
                self.driver.quit()
        except Exception as e:
            logging.warning(f"Error quitting driver during reset: {e}")
        
        logging.info("Creating new driver session...")
        self.driver = self._create_driver()

    def _reset_state(self):
        """
        Hard reset of the browser state to prevent data leakage between requests.
        Clears cookies, local/session storage, and navigates to about:blank.
        """
        try:
            self._ensure_valid_session()
            
            # 1. Navigate to about:blank first to detach from current page
            self.driver.get("about:blank")
            
            # 2. Delete all cookies
            self.driver.delete_all_cookies()
            
            # 3. Clear storage (must be done after navigation or on a valid page)
            try:
                self.driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
            except Exception:
                # Ignore errors if storage access is restricted (e.g. on about:blank in some versions)
                pass
                
        except Exception as e:
            logging.warning(f"Error resetting browser state: {e}")
            # If reset fails, we might want to force a session recreation
            try:
                self.driver.quit()
            except:
                pass
            self.driver = self._create_driver()

    def _fallback_fetch_httpx(self, url: str) -> tuple[list[str], str | None, str]:
        """
        Fallback method to fetch content using httpx when Selenium fails (e.g. renderer timeout).
        Returns: (list_of_links, text_content, effective_url)
        """
        try:
            logging.warning(f"Attempting HTTPX fallback for {url}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            # Use a slightly longer timeout for stability
            response = httpx.get(url, timeout=30.0, follow_redirects=True, headers=headers)
            response.raise_for_status()
            
            # Use response.encoding if available, else charset detection is automatic
            html_content = response.text
            effective_url = str(response.url)
            
            soup = BeautifulSoup(html_content, "html.parser")
            
            # --- Extract Links ---
            links = set()
            for a in soup.find_all("a", href=True):
                links.add(urljoin(effective_url, a["href"]))
            
            # --- Extract Text ---
            # Reuse cleanup logic briefly
            blacklist_tags = ["script", "style", "noscript", "form", "svg", "canvas", "iframe", "button", "input", "select", "option", "link", "meta", "object", "embed", "video", "audio"]
            for tag in soup(blacklist_tags):
                tag.decompose()
            for element in soup(text=lambda t: isinstance(t, Comment)):
                element.extract()
            
            text_content = soup.get_text(separator=" ", strip=True) or ""
            text_content = " ".join(text_content.split())
            
            logging.info(f"HTTPX fallback successful for {url}. Links: {len(links)}, Text: {len(text_content)}")
            return list(links), text_content, effective_url

        except Exception as e:
            logging.error(f"HTTPX fallback failed for {url}: {e}")
            return [], None, url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  
        self._cleanup()

    def _cleanup(self, force=False):
        """
        Clean up resources (Driver, Xvfb, Temp Dir). 
        Safe to call multiple times.
        """
        # Unregister atexit handler since we are cleaning up now
        try:
            atexit.unregister(self._cleanup)
        except Exception:
            pass

        # Skip cleanup if we want to keep browser open on failure
        if not force and getattr(self, '_keep_open_on_failure', False):
            logging.info("Keeping browser open due to failure")
            return
            
        # Try to quit the driver multiple times with increasing delays
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if hasattr(self, 'driver') and self.driver:
                    self.driver.quit()
                    # Give Chrome time to fully shut down
                    time.sleep(1.0 if attempt == 0 else 2.0)
                    break
            except Exception as e:
                # If session is already gone, stop retrying
                if "Unable to find session with ID" in str(e):
                    logging.info(f"Session already gone during cleanup (attempt {attempt + 1}/{max_attempts}). Stopping retries.")
                    break

                if attempt < max_attempts - 1:
                    logging.warning(f"Error quitting driver (attempt {attempt + 1}/{max_attempts}): {e}")
                    time.sleep(1.0)
                else:
                    logging.warning(f"Failed to quit driver after {max_attempts} attempts: {e}")
        
        # Cleanup Xvfb
        try:
            if self._xvfb_proc:
                self._xvfb_proc.terminate()
                try:
                    self._xvfb_proc.wait(timeout=3)
                except:
                    self._xvfb_proc.kill()
                    try:
                        self._xvfb_proc.wait(timeout=2)
                    except:
                        pass
        except Exception as e:
            logging.warning(f"Error terminating Xvfb: {e}")
            
        # Cleanup profile directory with retry and robust error handling
        if hasattr(self, '_profile_dir') and self._profile_dir and os.path.exists(self._profile_dir):
            for attempt in range(3):
                try:
                    time.sleep(0.5)
                    shutil.rmtree(self._profile_dir)  # Removed ignore_errors=True to catch errors, but loop handles them
                    break
                except Exception as e:
                    if attempt < 2:
                        logging.debug(f"Retrying profile cleanup ({attempt+1}/3): {e}")
                        time.sleep(1.0)
                    else:
                        logging.warning(f"Error removing profile directory {self._profile_dir}: {e}")
    
    def get_html_content(self, url: str, max_retries: int = 1) -> str | None:
        """
        Return the HTML content from the given URL, or None on failure.
        Will retry up to max_retries times if there's an error.
        """
        for attempt in range(max_retries):
            try:
                self._ensure_valid_session()
                self.driver.get(url)
                page_source = self.driver.page_source
                
                if not page_source and attempt < max_retries - 1:
                    logging.warning(f"No HTML content for {url}, attempt {attempt+1}/{max_retries}")
                    continue
                    
                return page_source
                
            except Exception as e:
                error_msg = str(e)[:200]
                logging.warning(f"Error getting HTML content for {url}, attempt {attempt+1}/{max_retries}: {error_msg}")
                if attempt < max_retries - 1:
                    continue
                return None

    def get_text_content(self, url: str, max_retries: int = 1, 
                         progressive_timeout: int = 30, 
                         content_check_interval: int = 2,
                         min_content_length: int = 500) -> str | None:
        """
        Return visible text from the given URL using progressive loading.
        
        Args:
            url: The URL to extract text from
            max_retries: Number of retry attempts
            progressive_timeout: Max seconds to wait for content (default 30s)
            content_check_interval: Seconds between content checks (default 2s)
            min_content_length: Minimum content length to consider sufficient (default 500 chars)
            
        Returns:
            Extracted text content or None on failure
        """
        for attempt in range(max_retries):
            try:
                self._reset_state()
                self._ensure_valid_session()
                
                # Start loading the page
                self.driver.get(url)
                
                # Initialize variables for progressive loading
                start_time = time.time()
                best_content = ""
                content_stable_count = 0
                previous_content_length = 0
                
                # Progressive loading loop
                while time.time() - start_time < progressive_timeout:
                    # Get current page source
                    current_source = self.driver.page_source
                    
                    if not current_source:
                        time.sleep(content_check_interval)
                        continue
                    
                    # Process the current state of the page
                    soup = BeautifulSoup(current_source, "html.parser")
                    
                    # Remove unwanted elements
                    blacklist_tags = [
                        "script", "style", "noscript", "form", "svg", "canvas", "iframe",
                        "button", "input", "select", "option", "link", "meta", "object",
                        "embed", "video", "audio",
                    ]
                    
                    for tag in soup(blacklist_tags):
                        tag.decompose()
                    
                    for element in soup(text=lambda t: isinstance(t, Comment)):
                        element.extract()
                    
                    for tag in soup.find_all(style=True):
                        try:
                            style_attr = tag.get("style")
                            if style_attr is None:
                                continue
                            style = "".join(str(style_attr).split()).lower()
                            if "display:none" in style or "visibility:hidden" in style:
                                tag.decompose()
                        except Exception:
                            continue
                    
                    # Extract text content
                    current_text = soup.get_text(separator=" ", strip=True) or ""
                    current_text = " ".join(current_text.split())
                    current_length = len(current_text)
                    
                    # Update best content if this is better
                    if current_length > len(best_content):
                        best_content = current_text
                        logging.info(f"Found better content for {url}: {current_length} chars")
                    
                    # Check if content has stabilized
                    if current_length == previous_content_length:
                        content_stable_count += 1
                    else:
                        content_stable_count = 0
                        previous_content_length = current_length
                    
                    # Exit conditions:
                    # 1. Content has stabilized (same length for multiple checks)
                    # 2. We have enough content
                    if (content_stable_count >= 2 and current_length > 0) or current_length >= min_content_length:
                        logging.info(f"Content stabilized for {url} at {current_length} chars")
                        return best_content
                    
                    # Wait before checking again
                    time.sleep(content_check_interval)
                
                # If we've reached the timeout but have some content, return it
                if best_content:
                    logging.info(f"Progressive loading timeout for {url}, returning {len(best_content)} chars")
                    return best_content
                
                # No content found within timeout
                logging.warning(f"No content found within timeout for {url}, attempt {attempt+1}/{max_retries}")
                if attempt < max_retries - 1:
                    continue
                return None
                
            except Exception as e:
                error_msg = str(e)

                # Check for "Timed out receiving message from renderer" specifically. This error often indicates a specific page issue but the driver is likely still healthy
                if "Timed out receiving message from renderer" in error_msg:
                    logging.warning(f"Renderer timeout for {url}: {error_msg}. Resetting driver and attempting HTTPX fallback.")
                    try:
                        self.reset_driver()
                    except:
                        pass
                    
                    # Fallback to HTTPX immediately -> avoids infinite loops in Selenium
                    # Since get_text_content returns only text, we discard links/url
                    _, fallback_text, _ = self._fallback_fetch_httpx(url)
                    return fallback_text

                # Check for network/connection/DNS errors that warrant a driver reset
                if "net::ERR_CONNECTION_TIMED_OUT" in error_msg or \
                   "net::ERR_NAME_NOT_RESOLVED" in error_msg or \
                   "net::ERR_CONNECTION_REFUSED" in error_msg:
                    
                    logging.warning(f"Network error for {url}: {error_msg[:100]}. Resetting driver...")
                    try:
                        self.reset_driver()
                    except:
                        pass
                
                logging.warning(f"Error getting text content for {url}, attempt {attempt+1}/{max_retries}: {error_msg[:200]}")
                if attempt < max_retries - 1:
                    continue
                return None
    
    def get_all_possible_links(self, url: str, max_retries: int = 1,
                              progressive_timeout: int = 20,
                              content_check_interval: int = 1) -> list[str]:
        """
        Get all possible links from a URL using progressive loading.
        
        Args:
            url: The URL to extract links from
            max_retries: Number of retry attempts
            progressive_timeout: Max seconds to wait for links (default 20s)
            content_check_interval: Seconds between content checks (default 1s)
            
        Returns:
            List of extracted links
        """
        for attempt in range(max_retries):
            try:
                self._reset_state()
                self._ensure_valid_session()
                
                # Start loading the page
                self.driver.get(url)
                
                # Initialize variables for progressive loading
                start_time = time.time()
                best_links = set()
                links_stable_count = 0
                previous_links_count = 0
                
                # Progressive loading loop
                while time.time() - start_time < progressive_timeout:
                    # Get current page source
                    current_source = self.driver.page_source
                    
                    if not current_source:
                        time.sleep(content_check_interval)
                        continue
                    
                    # Process the current state of the page
                    soup = BeautifulSoup(current_source, "html.parser")
                    current_links = set()
                    
                    # 1. Standard <a href="">
                    for a in soup.find_all("a", href=True):
                        current_links.add(urljoin(url, a["href"]))
                    
                    # 2. Forms with action attribute
                    for form in soup.find_all("form", action=True):
                        current_links.add(urljoin(url, form["action"]))
                    
                    # 3. Elements with onclick that look like redirects
                    for tag in soup.find_all(onclick=True):
                        onclick = tag["onclick"]
                        if "location" in onclick or "window.location" in onclick:
                            # Very naive extraction
                            for part in onclick.split("'"):
                                if "/" in part:
                                    current_links.add(urljoin(url, part.strip()))
                    
                    # 4. data-link or data-url attributes
                    # 4. data-link or data-url or data-href attributes
                    for tag in soup.find_all(attrs={"data-link": True}):
                        current_links.add(urljoin(url, tag["data-link"]))
                    for tag in soup.find_all(attrs={"data-url": True}):
                        current_links.add(urljoin(url, tag["data-url"]))
                    for tag in soup.find_all(attrs={"data-href": True}):
                        current_links.add(urljoin(url, tag["data-href"]))

                    # 5. role="link"
                    for tag in soup.find_all(attrs={"role": "link"}):
                        if tag.has_attr("href"):
                            current_links.add(urljoin(url, tag["href"]))
                        elif tag.has_attr("data-href"):
                            current_links.add(urljoin(url, tag["data-href"]))
                        elif tag.has_attr("onclick"): # try to parse onclick if present
                             onclick = tag["onclick"]
                             if "location" in onclick or "window.location" in onclick:
                                for part in onclick.split("'"):
                                    if "/" in part:
                                        current_links.add(urljoin(url, part.strip()))
                    
                    # Update best links
                    best_links.update(current_links)
                    current_count = len(best_links)
                    
                    # Check if links have stabilized
                    if current_count == previous_links_count:
                        links_stable_count += 1
                    else:
                        links_stable_count = 0
                        previous_links_count = current_count
                        logging.info(f"Found {current_count} links for {url}")
                    
                    # Exit if links have stabilized
                    if links_stable_count >= 2 and current_count > 0:
                        logging.info(f"Links stabilized for {url} at {current_count} links")
                        return list(best_links)
                    
                    # Wait before checking again
                    time.sleep(content_check_interval)
                
                # If we've reached the timeout but have some links, return them
                if best_links:
                    logging.info(f"Progressive loading timeout for {url}, returning {len(best_links)} links")
                    return list(best_links)
                
                # No links found within timeout
                logging.warning(f"No links found within timeout for {url}, attempt {attempt+1}/{max_retries}")
                if attempt < max_retries - 1:
                    continue
                return []
                
                return []
                
            except Exception as e:
                error_msg = str(e)[:200]
                
                # Check for "Timed out receiving message from renderer" specifically
                if "Timed out receiving message from renderer" in str(e):
                    logging.warning(f"Renderer timeout for {url}: {error_msg}. Resetting driver and attempting HTTPX fallback.")
                    try:
                        self.reset_driver()
                    except:
                        pass
                    
                    # Fallback to HTTPX immediately
                    fallback_links, _, _ = self._fallback_fetch_httpx(url)
                    return fallback_links

                logging.warning(f"Error getting links for {url}, attempt {attempt+1}/{max_retries}: {error_msg}")
                if attempt < max_retries - 1:
                    continue
                return []

    def fetch_main_page_data(self, url: str, max_retries: int = 1,
                            progressive_timeout: int = 30,
                            check_interval: int = 2) -> tuple[list[str], str | None, str]:
        """
        Fetch both links and text content from the main page in a single visit.
        Optimized to reduce page loads.
        
        Returns:
            (list_of_links, text_content, effective_url)
        """
        for attempt in range(max_retries):
            try:
                self._reset_state()
                self._ensure_valid_session()
                
                # Start loading the page
                self.driver.get(url)
                
                start_time = time.time()
                
                # State tracking
                best_links = set()
                best_text = ""
                
                links_stable_count = 0
                text_stable_count = 0
                
                prev_links_count = 0
                prev_text_len = 0
                
                while time.time() - start_time < progressive_timeout:
                    current_source = self.driver.page_source
                    if not current_source:
                        time.sleep(check_interval)
                        continue
                        
                    soup = BeautifulSoup(current_source, "html.parser")
                    
                    # --- 1. Extract Links (before cleaning) ---
                    current_links = set()
                    # Standard <a>
                    for a in soup.find_all("a", href=True):
                        current_links.add(urljoin(url, a["href"]))
                    # Forms
                    for form in soup.find_all("form", action=True):
                        current_links.add(urljoin(url, form["action"]))
                    # Button/onclick (naive)
                    for tag in soup.find_all(onclick=True):
                        onclick = tag["onclick"]
                        if "location" in onclick or "window.location" in onclick:
                            for part in onclick.split("'"):
                                if "/" in part:
                                    current_links.add(urljoin(url, part.strip()))

                    # data-link/url/href
                    for tag in soup.find_all(attrs={"data-link": True}):
                        current_links.add(urljoin(url, tag["data-link"]))
                    for tag in soup.find_all(attrs={"data-url": True}):
                        current_links.add(urljoin(url, tag["data-url"]))
                    for tag in soup.find_all(attrs={"data-href": True}):
                        current_links.add(urljoin(url, tag["data-href"]))

                    # role="link"
                    for tag in soup.find_all(attrs={"role": "link"}):
                        if tag.has_attr("href"):
                            current_links.add(urljoin(url, tag["href"]))
                        elif tag.has_attr("data-href"):
                            current_links.add(urljoin(url, tag["data-href"]))
                                    
                    # Update best links
                    best_links.update(current_links)
                    curr_links_count = len(best_links)
                    
                    if curr_links_count == prev_links_count:
                        links_stable_count += 1
                    else:
                        links_stable_count = 0
                        prev_links_count = curr_links_count
                    
                    # --- 2. Extract Text (after cleaning) ---
                    # Clean soup
                    blacklist_tags = [
                        "script", "style", "noscript", "form", "svg", "canvas", "iframe",
                        "button", "input", "select", "option", "link", "meta", "object",
                        "embed", "video", "audio",
                    ]
                    for tag in soup(blacklist_tags):
                        tag.decompose()
                    for element in soup(text=lambda t: isinstance(t, Comment)):
                        element.extract()
                    for tag in soup.find_all(style=True):
                        try:
                            s = "".join(str(tag.get("style")).split()).lower()
                            if "display:none" in s or "visibility:hidden" in s:
                                tag.decompose()
                        except: pass
                        
                    current_text = soup.get_text(separator=" ", strip=True) or ""
                    current_text = " ".join(current_text.split())
                    curr_text_len = len(current_text)
                    
                    if curr_text_len > len(best_text):
                        best_text = current_text
                        
                    if curr_text_len == prev_text_len:
                        text_stable_count += 1
                    else:
                        text_stable_count = 0
                        prev_text_len = curr_text_len
                        
                    # Exit condition: Both stabilized (count >= 2) and we have data
                    # Or we have "enough" data (e.g. text > 500 chars and some links)
                    links_ready = (links_stable_count >= 2 and curr_links_count > 0)
                    text_ready = (text_stable_count >= 2 and curr_text_len > 0) or curr_text_len > 1000
                    
                    if links_ready and text_ready:
                        logging.info(f"Main page fetch stabilized for {url}. Links: {curr_links_count}, Text: {curr_text_len}")
                        return list(best_links), best_text, url
                        
                    time.sleep(check_interval)
                    
                # Timeout fallback
                return list(best_links), best_text, url
                
            except Exception as e:
                error_msg = str(e)
                
                # Check for "Timed out receiving message from renderer" specifically. This error often indicates a specific page issue but the driver is likely still healthy
                # Check for "Timed out receiving message from renderer" specifically
                if "Timed out receiving message from renderer" in error_msg:
                    logging.warning(f"Renderer timeout fetching main page data for {url}: {error_msg}. Resetting driver and attempting HTTPX fallback.")
                    try:
                        self.reset_driver()
                    except:
                        pass
                    
                    # Fallback to HTTPX immediately - Single attempt, returns results directly
                    return self._fallback_fetch_httpx(url)

                # Check for connection refused on HTTPS -> Try HTTP fallback
                if "net::ERR_CONNECTION_REFUSED" in error_msg and url.startswith("https://"):
                    logging.warning(f"Connection refused for HTTPS: {url}. Retrying with HTTP...")
                    http_url = url.replace("https://", "http://", 1)
                    # Use recursion with max_retries=2 (so it tries HTTP once and maybe 1 retry) => limit recursion
                    # We pass max_retries=1 to ensure just one attempt at HTTP if we want to be strict
                    return self.fetch_main_page_data(http_url, max_retries=1, progressive_timeout=progressive_timeout, check_interval=check_interval)

                # Check for network/connection/DNS errors that warrant a driver reset
                if "net::ERR_CONNECTION_TIMED_OUT" in error_msg or \
                   "net::ERR_NAME_NOT_RESOLVED" in error_msg or \
                   "net::ERR_CONNECTION_REFUSED" in error_msg:
                    
                    logging.warning(f"Network error for {url}: {error_msg[:100]}. Resetting driver...")
                    try:
                        self.reset_driver()
                    except:
                        pass

                logging.warning(f"Error fetching main page data for {url}: {e}")
                if attempt < max_retries - 1:
                    continue
                return [], None, url

    def _dict_to_row(self, d: dict[str, str | None]) -> list[str]:
        """Return a list in COLUMN_ORDER, filling missing keys with ''."""
        return [(d.get(k) or "") for k in COLUMN_ORDER]

    def _hostname_resolves(self, hostname: str) -> bool:
        """
        Return True if hostname resolves via DNS inside this container, False otherwise.
        """
        try:
            # getaddrinfo works for both IPv4 and IPv6 and respects container DNS config
            socket.getaddrinfo(hostname, None)
            return True
        except Exception:
            return False

    def _build_normalized_company_url(self, company: dict) -> str | None:
        """
        Build a fully-qualified, resolvable URL for a company's contact page or domain.

        - If corporate_contact_url is relative (e.g. '/contact' or 'contact'), combine with domain
        - Ensure scheme is present (default https://)
        - Convert internationalized domains to ASCII (IDNA / punycode)
        - If DNS doesn't resolve, try 'www.' prefix as a fallback
        """
        try:
            props = company.get("properties", {}) if isinstance(company, dict) else {}
        except Exception:
            props = {}

        contact = str(props.get("corporate_contact_url") or "").strip()
        domain = str(props.get("domain") or "").strip()

        url = ""

        if contact:
            # If contact is absolute keep it, else join with domain as base
            if contact.startswith("http://") or contact.startswith("https://"):
                url = contact
            else:
                # make relative path start with '/'
                path = contact if contact.startswith("/") else f"/{contact}"
                if domain:
                    base = domain
                    if "://" not in base:
                        base = f"https://{base}"
                    url = urljoin(base, path)
                else:
                    # No domain to anchor to; will get scheme below if missing
                    url = contact
        elif domain:
            url = domain
        else:
            return None

        # Ensure scheme
        if "://" not in url:
            url = f"https://{url}"

        # Normalize host to punycode (IDNA) and ensure a path at least '/'
        try:
            sp = urlsplit(url)
            host = (sp.hostname or "").strip()
            if host:
                ascii_host = host.encode("idna").decode("ascii")
                netloc = ascii_host
                if sp.port:
                    netloc += f":{sp.port}"
                normalized = urlunsplit(
                    (sp.scheme or "https", netloc, sp.path or "/", sp.query, sp.fragment)
                )
            else:
                normalized = url
        except Exception:
            normalized = url

        # DNS resolution check with 'www.' fallback if needed
        try:
            host_to_check = urlsplit(normalized).hostname or ""
            if host_to_check and (not self._hostname_resolves(host_to_check)) and not host_to_check.startswith("www."):
                alt_host = f"www.{host_to_check}"
                sp = urlsplit(normalized)
                alt_netloc = alt_host
                if sp.port:
                    alt_netloc += f":{sp.port}"
                normalized_www = urlunsplit((sp.scheme, alt_netloc, sp.path, sp.query, sp.fragment))
                if self._hostname_resolves(alt_host):
                    return normalized_www
        except Exception as e:
            # If anything goes wrong, just return what we have
            logging.exception("Error during DNS resolution check for '%s': %s", normalized, e)
            pass

        return normalized

    # TODO: Improve this function, currently using the legacy code from the client
    def send_contact(self, company_list: list[dict], contact_template: dict[str, Any], max_retries: int = 1) -> list[dict]:
        """
        Send contact form to companies.
        Will retry up to max_retries times if there's an error.
        """
        self._ensure_valid_session()
        
        # Track if any submission failed
        has_failure = False
        
        # l: only row[1] matters
        row1 = self._dict_to_row(contact_template)
        # row[0] can be anything of the same length; keep it simple
        dummy_header = [""] * len(COLUMN_ORDER)

        template: list[list[str]] = [dummy_header, row1]  

        for company in company_list:
            normalized_url = self._build_normalized_company_url(company)
            title = company["properties"].get("name", "")

            # Validate URL and title
            if not normalized_url or not title:
                logging.error("Missing or invalid URL or name for company: %s", company)
                company["properties"]["status"] = StatusConst.FAILED
                continue
            
                
            for attempt in range(max_retries):
                try:
                    self._ensure_valid_session()
                    logging.info("Trying to navigate to: %s", normalized_url)
                    
                    is_success = LegacySeleniumContact(driver=self.driver).contact_sending_process(
                        normalized_url,
                        title,
                        template, # l[1] is still the template row
                        is_submit = True
                    )
                    
                    company["properties"]["status"] = (
                        StatusConst.SUCCESS if is_success else StatusConst.FAILED
                    )
                    
                    # Track if we have a failure
                    if not is_success:
                        has_failure = True
                    
                    logging.info(
                        "Contact send %s for company '%s' (%s), attempt %d/%d",
                        "SUCCESS" if is_success else "FAILED",
                        title,
                        normalized_url,
                        attempt+1,
                        max_retries
                    )
                    
                    # If successful or we've tried all retries, break out of the retry loop
                    if is_success or attempt >= max_retries - 1:
                        break
                        
                    # If not successful, log and retry
                    logging.warning("Retrying contact send for company '%s' (%s)", title, normalized_url)
                    
                except Exception as e:
                    logging.error("Error for company '%s' (%s): %s, attempt %d/%d", 
                                 title, normalized_url, e, attempt+1, max_retries)
                    
                    company["properties"]["status"] = StatusConst.FAILED
                    has_failure = True
                    
                    # If we've tried all retries, break out of the retry loop
                    if attempt >= max_retries - 1:
                        break
                        
                    # Otherwise, log and retry
                    logging.warning("Retrying contact send for company '%s' (%s) after error", title, normalized_url)

        # If there was a failure, keep the browser open
        if has_failure:
            self._keep_open_on_failure = True
            logging.info("Keeping browser open due to failed submission(s)")
        
        return company_list

    def open_company_urls(
        self, company_list: list[dict], contact_template: dict[str, Any]
    ) -> list[dict]:
        """
        Open all company contact URLs in separate browser tabs.
        Prefills the form using the contact template but does not submit.
        """

        self._ensure_valid_session()

        # Build template like send_contact
        row1 = self._dict_to_row(contact_template)
        template: list[list[str]] = [[""] * len(COLUMN_ORDER), row1]

        if not company_list:
            return company_list

        def _process_company(company: dict, is_first: bool = False) -> None:
            url = self._build_normalized_company_url(company)
            title = company["properties"].get("name", "")

            if not url or not title:
                logging.error("Missing domain or name for company: %s", company)
                company["properties"]["status"] = StatusConst.FAILED
                return

            try:
                if not is_first:
                    self.driver.execute_script(f"window.open('{url}', '_blank');")
                    self.driver.switch_to.window(self.driver.window_handles[-1])

                LegacySeleniumContact(driver=self.driver).contact_sending_process(
                    url, title, template, is_submit=False, time_sleep=0.1
                )
                logging.info("Opened company '%s' (%s)", title, url)

            except Exception as e:
                logging.error("Error opening company '%s' (%s): %s", title, url, e)

        # Process first company in existing tab
        _process_company(company_list[0], is_first=True)

        # Process remaining companies in new tabs
        for company in company_list[1:]:
            _process_company(company)
            
        return company_list