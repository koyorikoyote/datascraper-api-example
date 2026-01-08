import subprocess
import tempfile, shutil, atexit
import os
import uuid
import time
import socket
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup, Comment
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

class SeleniumService:
    """Chrome in a container-friendly, headless configuration."""

    def __init__(
        self,
        headless: bool = True,
        remote_url: str = get_env("SELENIUM_GRID_URL", default="http://localhost:4444/wd/hub"),
    ) -> None:
        self.headless = headless
        self.remote_url = remote_url
        
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
        
        # Initialize the driver
        self.driver = self._create_driver()

        atexit.register(self._cleanup)
        
    def _create_driver(self):
        """Create a new WebDriver instance with the configured options."""
        opts = Options()

        # Choose headless vs headed
        if self.headless:
            opts.add_argument("--headless")

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

        # Connect to the Grid running on port 4444 
        logging.info("Creating new WebDriver session")
        
        driver = None
        max_retries = 5
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
                error_msg = str(e)
                if attempt < max_retries - 1:
                    wait_time = retry_delay
                    
                    # Check for 504 Gateway Timeout specifically
                    if "504 Gateway Timeout" in error_msg or "Gateway Time-out" in error_msg:
                        logging.warning(f"Gateway Timeout (504) detected. Infrastructure might be overloaded.")
                        wait_time = 45 # Wait 45s to allow container/service recovery
                    
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
                
            # Create a new driver
            self.driver = self._create_driver()
            logging.info("WebDriver session recreated successfully")

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  
        self._cleanup()

    def _cleanup(self, force=False):
        # Skip cleanup if we want to keep browser open on failure
        if not force and getattr(self, '_keep_open_on_failure', False):
            logging.info("Keeping browser open due to failure")
            return
            
        try:
            self.driver.quit()
        except Exception as e:
            logging.warning(f"Error quitting driver: {e}")
        finally:
            if self._xvfb_proc:
                self._xvfb_proc.terminate()
            try:
                # Add a small delay before removing the directory to ensure Chrome has released it
                time.sleep(0.5)
                shutil.rmtree(self._profile_dir, ignore_errors=True)
            except Exception as e:
                logging.warning(f"Error removing profile directory: {e}")
    
    def get_html_content(self, url: str, max_retries: int = 3) -> str | None:
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

    def get_text_content(self, url: str, max_retries: int = 3, 
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
                error_msg = str(e)[:200]
                logging.warning(f"Error getting text content for {url}, attempt {attempt+1}/{max_retries}: {error_msg}")
                if attempt < max_retries - 1:
                    continue
                return None
    
    def get_all_possible_links(self, url: str, max_retries: int = 3,
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
                    for tag in soup.find_all(attrs={"data-link": True}):
                        current_links.add(urljoin(url, tag["data-link"]))
                    for tag in soup.find_all(attrs={"data-url": True}):
                        current_links.add(urljoin(url, tag["data-url"]))
                    
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
                
            except Exception as e:
                error_msg = str(e)[:200]
                logging.warning(f"Error getting links for {url}, attempt {attempt+1}/{max_retries}: {error_msg}")
                if attempt < max_retries - 1:
                    continue
                return []

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