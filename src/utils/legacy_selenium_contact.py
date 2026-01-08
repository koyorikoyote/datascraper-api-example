from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import time
import csv
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    WebDriverException,
    StaleElementReferenceException,
    NoAlertPresentException
)
from src.utils.decorators import try_except_decorator
import re
import logging


    
class LegacySeleniumContact:
    def __init__(self, driver):
        self.driver = driver
        self.CLICK_WAIT = 3
        self.CONFIRM_TIMEOUT = 5
        
    def _is_session_valid(self):
        """Check if the current WebDriver session is valid."""
        try:
            # A simple command that should work if the session is valid
            self.driver.current_url
            return True
        except WebDriverException:
            return False
        
    def _normalise_url(self, raw: str) -> str:
        raw = raw.strip()
        if not re.match(r"^https?://", raw):
            raw = "https://" + raw          # default to HTTPS
        return raw

    @try_except_decorator
    def contact_sending_process(self, url: str, title: str, l: list[list[str]], is_submit: bool = True, time_sleep: int = 3) -> bool:
        logging.info(f"Starting contact_sending_process for company '{title}' (URL: {url})")
        logging.info(f"WebDriver session valid: {self._is_session_valid()}")
        
        # Check if session is valid before proceeding
        if not self._is_session_valid():
            logging.error("WebDriver session is invalid, cannot proceed with contact sending")
            return False
            
        # 問い合わせフォームへの入力
        url = self._normalise_url(url)
        
        # Check if this is the first URL (no navigation history in current tab)
        # If the current tab is about:blank or empty, use it; otherwise open new tab
        current_url = self.driver.current_url
        logging.info(f"Current URL before navigation: '{current_url}'")
        
        # Only create new tab if current tab has real content (not empty/blank)
        # Include various Chrome new tab page URLs (including potential localized versions)
        blank_pages = [
            'about:blank', 
            'data:,', 
            '', 
            'chrome://new-tab-page/',
            'chrome://newtab/',
            'chrome://新しいタブ/',  # Japanese version if it exists
            None  # In case current_url is None
        ]
        if current_url and current_url not in blank_pages:
            logging.info(f"Current tab has content ({current_url}), opening new tab")
            # Current tab has content, open a new tab
            # This keeps failed submissions visible in their own tabs
            self.driver.execute_script("window.open('');")
            # Switch to the new tab
            self.driver.switch_to.window(self.driver.window_handles[-1])
        else:
            logging.info(f"Using existing tab (was: {current_url})")
        
        # Navigate to the URL
        self.driver.get(url)
        time.sleep(time_sleep)
        logging.info("Contacting %s (%s)", url, title)
        logging.debug("Last name = %s", l[1][0])
        # 名前の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][0] + l[1][1])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][0] + l[1][1])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][0] + l[1][1])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][0] + l[1][1])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@*='name' or @*='your-name' or @name='fullname' or @name='form_name' or @name='お名前' or @name='氏名' or @name='ご担当者名' or contains(@placeholder,'名前') or contains(@placeholder,'氏名') or contains(@placeholder,'山田太郎') or contains(@placeholder,'山田 太郎') or contains(@placeholder,'山田　太郎') or contains(@placeholder,'山田花子') or contains(@placeholder,'山田 花子') or contains(@placeholder,'山田　花子')]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@*='name' or @*='your-name' or @name='fullname' or @name='form_name' or @name='お名前' or @name='氏名' or @name='ご担当者名' or contains(@placeholder,'名前') or contains(@placeholder,'氏名') or contains(@placeholder,'山田太郎') or contains(@placeholder,'山田 太郎') or contains(@placeholder,'山田　太郎') or contains(@placeholder,'山田花子') or contains(@placeholder,'山田 花子') or contains(@placeholder,'山田　花子')]",
            ).send_keys(l[1][0] + l[1][1])
        except:
            logging.error('pass')

        # 名前のカナ入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][2] + l[1][3])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][2] + l[1][3])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][2] + l[1][3])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][2] + l[1][3])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='name-kana' or @name='your-kana' or @name='your-name-kana' or @name='your-furigana' or @name='フリガナ' or contains(@placeholder,'フリガナ') or contains(@placeholder,'ヤマダタロウ') or contains(@placeholder,'ヤマダ タロウ') or contains(@placeholder,'ヤマダ　タロウ') or contains(@placeholder,'ヤマダハナコ') or contains(@placeholder,'ヤマダ ハナコ') or contains(@placeholder,'ヤマダ　ハナコ')]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@name='name-kana' or @name='your-kana' or @name='your-name-kana' or @name='your-furigana' or @name='フリガナ' or contains(@placeholder,'フリガナ') or contains(@placeholder,'ヤマダタロウ') or contains(@placeholder,'ヤマダ タロウ') or contains(@placeholder,'ヤマダ　タロウ') or contains(@placeholder,'ヤマダハナコ') or contains(@placeholder,'ヤマダ ハナコ') or contains(@placeholder,'ヤマダ　ハナコ')]",
            ).send_keys(l[1][2] + l[1][3])
        except:
            logging.error('pass')

        # 名前のかな入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][4] + l[1][5])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][4] + l[1][5])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][4] + l[1][5])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][4] + l[1][5])
        except:
            logging.error('pass')

        # 姓名の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][1])
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][0])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][1])
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][0])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][1])
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'名前') or contains(text(),'氏名')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][0])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][1])
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'名前') or contains(text(),'氏名')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][0])
        except:
            logging.error('pass')

        # セイメイの入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][3])
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][2])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][3])
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][2])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][3])
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'フリガナ') or contains(text(),'カナ')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][2])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][3])
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'フリガナ') or contains(text(),'カナ')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][2])
        except:
            logging.error('pass')

        # せいめいの入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][5])
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][4])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][5])
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][4])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][5])
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'ふりがな') or contains(text(),'かな')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][4])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][5])
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'ふりがな') or contains(text(),'かな')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][4])
        except:
            logging.error('pass')

        # 姓の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='last-name' or @name='lastname' or @name='name_sei' or @name='name-sei' or @placeholder='姓' or @placeholder='山田' or @placeholder='例：山田' or @placeholder='例）山田']",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@name='last-name' or @name='lastname' or @name='name_sei' or @name='name-sei' or @placeholder='姓' or @placeholder='山田' or @placeholder='例：山田' or @placeholder='例）山田']",
            ).send_keys(l[1][0])
        except:
            logging.error('pass')

        # 名の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='first-name' or @name='firstname' or @name='name_mei' or @name='name-mei' or @placeholder='名' or @placeholder='太郎' or @placeholder='例：太郎' or @placeholder='例）太郎' or @placeholder='花子' or @placeholder='例：花子' or @placeholder='例）花子']",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@name='first-name' or @name='firstname' or @name='name_mei' or @name='name-mei' or @placeholder='名' or @placeholder='太郎' or @placeholder='例：太郎' or @placeholder='例）太郎' or @placeholder='花子' or @placeholder='例：花子' or @placeholder='例）花子']",
            ).send_keys(l[1][1])
        except:
            logging.error('pass')

        # 姓のカナ入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='last-name-kana' or @placeholder='セイ' or @placeholder='ヤマダ' or @placeholder='例）ヤマダ' or @placeholder='例：ヤマダ']",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@name='last-name-kana' or @placeholder='セイ' or @placeholder='ヤマダ' or @placeholder='例）ヤマダ' or @placeholder='例：ヤマダ']",
            ).send_keys(l[1][2])
        except:
            logging.error('pass')

        # 名のカナ入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='first-name-kana' or @placeholder='メイ' or @placeholder='タロウ' or @placeholder='例）タロウ' or @placeholder='例：タロウ' or @placeholder='ハナコ' or @placeholder='例）ハナコ' or @placeholder='例：ハナコ']",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@name='first-name-kana' or @placeholder='メイ' or @placeholder='タロウ' or @placeholder='例）タロウ' or @placeholder='例：タロウ' or @placeholder='ハナコ' or @placeholder='例）ハナコ' or @placeholder='例：ハナコ']",
            ).send_keys(l[1][3])
        except:
            logging.error('pass')

        # 姓のかな入力
        try:
            self.driver.find_element(By.XPATH, "//input[@placeholder='せい']").send_keys(
                l[1][4]
            )
        except:
            logging.error('pass')

        # 名のかな入力
        try:
            self.driver.find_element(By.XPATH, "//input[@placeholder='めい']").send_keys(
                l[1][5]
            )
        except:
            logging.error('pass')

        # メールアドレスの入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'メールアドレス')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'メールアドレス')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'メールアドレス')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'メールアドレス')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'メールアドレス')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'メールアドレス')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'メールアドレス')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@type='email' or @type='mail' or @name='email' or @name='e_mail' or @name='mail' or @name='Email' or @name='EMAIL' or @name='mailaddress' or @name='mailaddr' or @name='mailAdd' or @name='form_email' or @name='メールアドレス' or @id='email' or contains(@placeholder,'@') or contains(@placeholder,'メールアドレス')]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@type='email' or @type='mail' or @name='email' or @name='e_mail' or @name='mail' or @name='Email' or @name='EMAIL' or @name='mailaddress' or @name='mailaddr' or @name='mailAdd' or @name='form_email' or @name='メールアドレス' or @id='email' or contains(@placeholder,'@') or contains(@placeholder,'メールアドレス')]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        # メールアドレス確認の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'メールアドレス')]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'メールアドレス')]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'メールアドレス')]]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'メールアドレス')]]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'メールアドレス')]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'メールアドレス')]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'メールアドレス')]]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'メールアドレス')]]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'メールアドレス') and contains(text(),'確認')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'メールアドレス') and contains(text(),'確認')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'メールアドレス') and contains(text(),'確認')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'メールアドレス') and contains(text(),'確認')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'メールアドレス') and contains(text(),'確認')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'メールアドレス') and contains(text(),'確認')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'メールアドレス') and contains(text(),'確認')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'メールアドレス') and contains(text(),'確認')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='mailconfirm' or @name='email_confirm' or @name='mail_address_confirm' or @name='mail-address-confirm' or @name='email-confirmation' or @name='email_confirmation' or @name='mail2' or @name='email2' or @name='email02']",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@name='mailconfirm' or @name='email_confirm' or @name='mail_address_confirm' or @name='mail-address-confirm' or @name='email-confirmation' or @name='email_confirmation' or @name='mail2' or @name='email2' or @name='email02']",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "(//input[@type='email' or @type='mail' or @name='email' or @name='e_mail' or @name='mail' or @name='Email' or @name='EMAIL' or @name='mailaddress' or @name='mailaddr' or @name='mailAdd' or @name='form_email' or @name='メールアドレス' or @id='email' or contains(@placeholder,'@') or contains(@placeholder,'メールアドレス')])[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "(//input[@type='email' or @type='mail' or @name='email' or @name='e_mail' or @name='mail' or @name='Email' or @name='EMAIL' or @name='mailaddress' or @name='mailaddr' or @name='mailAdd' or @name='form_email' or @name='メールアドレス' or @id='email' or contains(@placeholder,'@') or contains(@placeholder,'メールアドレス')])[2]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//input[contains(@placeholder,'メールアドレス') and contains(@placeholder,'確認')]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[contains(@placeholder,'メールアドレス') and contains(@placeholder,'確認')]",
            ).send_keys(l[1][6])
        except:
            logging.error('pass')

        # 会社名の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'社名') or contains(text(),'法人')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'社名') or contains(text(),'法人')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][7])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'社名') or contains(text(),'法人')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'社名') or contains(text(),'法人')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][7])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'社名') or contains(text(),'法人')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'社名') or contains(text(),'法人')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][7])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'社名') or contains(text(),'法人')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'社名') or contains(text(),'法人')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][7])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='company' or @name='Company' or @name='COMPANY' or @name='your-company' or @name='company_name' or @name='corporate' or @name='corporate_name' or @name='社名' or @name='御社名' or @name='会社名' or @name='企業名' or contains(@placeholder,'株式会社') or contains(@placeholder,'社名')]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@name='company' or @name='Company' or @name='COMPANY' or @name='your-company' or @name='company_name' or @name='corporate' or @name='corporate_name' or @name='社名' or @name='御社名' or @name='会社名' or @name='企業名' or contains(@placeholder,'株式会社') or contains(@placeholder,'社名')]",
            ).send_keys(l[1][7])
        except:
            logging.error('pass')

        # 部署名の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='department' or @name='your-department' or contains(@name,'部署') or contains(@placeholder,'部')]",
            ).send_keys(l[1][8])
        except:
            logging.error('pass')

        # サイトURLの入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='url' or @name='URL' or @type='url' or contains(@placeholder,'http')]",
            ).send_keys(l[1][9])
        except:
            logging.error('pass')

        # 電話番号の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'電話')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'電話')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][10] + l[1][11] + l[1][12])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'電話')]/following-sibling::td[1]//input[3]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'電話')]/following-sibling::td[1]//input[3]",
            ).send_keys(l[1][12])
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'電話')]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'電話')]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][11])
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'電話')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'電話')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][10])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'電話')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'電話')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][10] + l[1][11] + l[1][12])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'電話')]]/following-sibling::td[1]//input[3]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'電話')]]/following-sibling::td[1]//input[3]",
            ).send_keys(l[1][12])
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'電話')]]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'電話')]]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][11])
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'電話')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'電話')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][10])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'電話')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'電話')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][10] + l[1][11] + l[1][12])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'電話')]/following-sibling::dd[1]//input[3]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'電話')]/following-sibling::dd[1]//input[3]",
            ).send_keys(l[1][12])
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'電話')]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'電話')]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][11])
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'電話')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'電話')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][10])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'電話')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'電話')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][10] + l[1][11] + l[1][12])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'電話')]]/following-sibling::dd[1]//input[3]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'電話')]]/following-sibling::dd[1]//input[3]",
            ).send_keys(l[1][12])
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'電話')]]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'電話')]]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][11])
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'電話')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'電話')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][10])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@type='tel' or @name='tel' or @name='contact_tel' or @name='phone' or @name='form_tel' or @name='電話番号' or @name='denwa-bangou' or contains(@placeholder,'電話番号')]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@type='tel' or @name='tel' or @name='contact_tel' or @name='phone' or @name='form_tel' or @name='電話番号' or @name='denwa-bangou' or contains(@placeholder,'電話番号')]",
            ).send_keys(l[1][10] + l[1][11] + l[1][12])
        except:
            logging.error('pass')

        # 電話番号の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='tel3' or @name='tel-3' or @name='tel03' or @name='tel_3' or @name='tel_03']",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@name='tel3' or @name='tel-3' or @name='tel03' or @name='tel_3' or @name='tel_03']",
            ).send_keys(l[1][12])
            self.driver.find_element(
                By.XPATH,
                "//input[@name='tel2' or @name='tel-2' or @name='tel02' or @name='tel_2' or @name='tel_02']",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@name='tel2' or @name='tel-2' or @name='tel02' or @name='tel_2' or @name='tel_02']",
            ).send_keys(l[1][11])
            self.driver.find_element(
                By.XPATH,
                "//input[@name='tel1' or @name='tel-1' or @name='tel01' or @name='tel_1' or @name='tel_01']",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[@name='tel1' or @name='tel-1' or @name='tel01' or @name='tel_1' or @name='tel_01']",
            ).send_keys(l[1][10])
        except:
            logging.error('pass')

        # 郵便番号の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'郵便')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'郵便')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][13] + l[1][14])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'郵便')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'郵便')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][13] + l[1][14])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'郵便')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'郵便')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][13] + l[1][14])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'郵便')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'郵便')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][13] + l[1][14])
        except:
            logging.error('pass')
        try:
            self.driver.find_element(
                By.XPATH,
                "//input[contains(@placeholder,'郵便番号') or @name='zipcode' or @name='your-zipcode' or @name='郵便番号']",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[contains(@placeholder,'郵便番号') or @name='zipcode' or @name='your-zipcode' or @name='郵便番号']",
            ).send_keys(l[1][13] + l[1][14])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'郵便')]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'郵便')]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][14])
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'郵便')]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[contains(text(),'郵便')]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][13])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'郵便')]]/following-sibling::td[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'郵便')]]/following-sibling::td[1]//input[2]",
            ).send_keys(l[1][14])
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'郵便')]]/following-sibling::td[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//th[*[contains(text(),'郵便')]]/following-sibling::td[1]//input[1]",
            ).send_keys(l[1][13])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'郵便')]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'郵便')]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][14])
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'郵便')]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[contains(text(),'郵便')]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][13])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'郵便')]]/following-sibling::dd[1]//input[2]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'郵便')]]/following-sibling::dd[1]//input[2]",
            ).send_keys(l[1][14])
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'郵便')]]/following-sibling::dd[1]//input[1]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//dt[*[contains(text(),'郵便')]]/following-sibling::dd[1]//input[1]",
            ).send_keys(l[1][13])
        except:
            logging.error('pass')
        try:
            self.driver.find_element(
                By.XPATH,
                "//input[contains(@placeholder,'郵便番号') or @name='zipcode' or @name='your-zipcode' or @name='郵便番号']",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[contains(@placeholder,'郵便番号') or @name='zipcode' or @name='your-zipcode' or @name='郵便番号']",
            ).send_keys(l[1][13] + l[1][14])
        except:
            logging.error('pass')

        try:
            self.driver.find_element(
                By.XPATH,
                "//input[contains(@name,'zip2') or contains(@name,'zip02') or contains(@name,'zipcode2') or contains(@name,'zipcode02') or contains(@name,'postCode2')]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[contains(@name,'zip2') or contains(@name,'zip02') or contains(@name,'zipcode2') or contains(@name,'zipcode02') or contains(@name,'postCode2')]",
            ).send_keys(l[1][14])
            self.driver.find_element(
                By.XPATH,
                "//input[contains(@name,'zip1') or contains(@name,'zip01') or contains(@name,'zipcode1') or contains(@name,'zipcode01') or contains(@name,'postCode1')]",
            ).clear()
            self.driver.find_element(
                By.XPATH,
                "//input[contains(@name,'zip1') or contains(@name,'zip01') or contains(@name,'zipcode1') or contains(@name,'zipcode01') or contains(@name,'postCode1')]",
            ).send_keys(l[1][13])
        except:
            logging.error('pass')

        # 住所の入力
        try:
            self.driver.find_element(By.XPATH, "//option[text()='東京都']").click()
        except:
            logging.error('pass')

        # try:    #住所の入力
        #     self.driver.find_element(By.XPATH,"//input[@name='title' or @name='subject' or @name='your-subject']").send_keys(l[1][15])
        # except:
        #     logging.error('pass')

        # 件名の入力
        try:
            self.driver.find_element(
                By.XPATH,
                "//input[@name='title' or @name='subject' or @name='your-subject' or contains(@name,'件名')]",
            ).send_keys(l[1][18])
        except:
            logging.error('pass')

        # 本文の入力
        try:
            self.driver.find_element(By.XPATH, "//textarea[position()=last()]").send_keys(
                l[1][19]
            )
        except:
            logging.error('pass')

        # チェックボックスのクリック
        try:
            self.driver.find_element(
                By.XPATH, "//input[@type='checkbox' and position()=last()]"
            ).click()
        except:
            logging.error('pass')
        
        if is_submit:
            success = self.submitForm()
            
            # Uncomment if you want this feature
            """ # If submission was successful, close the tab
            if success:
                current_window = self.driver.current_window_handle
                all_windows = self.driver.window_handles
                
                # Only close if there's more than one tab open
                if len(all_windows) > 1:
                    self.driver.close()
                    # Switch to the first available window
                    remaining_windows = [w for w in all_windows if w != current_window]
                    if remaining_windows:
                        self.driver.switch_to.window(remaining_windows[0])
                    logging.info("Closed successful submission tab")
            else:
                logging.info("Keeping failed submission tab open for review") """
                
                
            return success
        
        return False

    def submitForm(self) -> bool:
        xpath_variants = [
            "//input[@type='submit']",
            "//input[@type='button']",
            "//input[@type='image']",
            "//input[contains(@value,'送信') or contains(@value,'確認') or contains(@value,'申し込み') or contains(@value,'登録') or contains(@value,'エントリー') or contains(@value,'Submit') or contains(@value,'Confirm') or contains(@value,'Send')]",
            "//button[@type='submit']",
            "//button[contains(text(),'送信') or contains(text(),'確認') or contains(text(),'申し込み') or contains(text(),'登録') or contains(text(),'エントリー') or contains(text(),'Submit') or contains(text(),'Confirm') or contains(text(),'Send')]",
            "//button[.//span[contains(text(),'送信') or contains(text(),'確認')]]",
            "//button[.//div[contains(text(),'送信') or contains(text(),'確認')]]",
            "//div[contains(@class,'submit') and (contains(text(),'送信') or contains(text(),'確認'))]",
            "//a[contains(@class,'submit') and contains(text(),'送信')]",
            "//a[contains(text(),'申し込み')]",
        ]
        original_url = self.driver.current_url
        original_windows = self.driver.window_handles[:]
        for xpath in xpath_variants:
            try:
                logging.info(f"Attempting to find submit element with xpath: {xpath}")
                element = WebDriverWait(self.driver, self.CLICK_WAIT).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                # Debug: Check what we found
                logging.info(f"Found submit element with xpath: {xpath}")
                logging.info(f"Element type before click: {type(element)}, tag: {element.tag_name if hasattr(element, 'tag_name') else 'N/A'}")
                logging.info(f"Element attributes: {dir(element) if hasattr(element, '__dir__') else 'No dir available'}")
                logging.info(f"Element string representation: {str(element)[:200]}...")

                # Validate that we got a proper WebElement
                if not hasattr(element, 'is_displayed'):
                    logging.error(f"CRITICAL: WebDriverWait returned non-WebElement: {type(element)}, value: {element}")
                    logging.error(f"Element attributes: {dir(element) if hasattr(element, '__dir__') else 'No dir available'}")
                    continue

                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", element
                )
                time.sleep(0.2)
                try:
                    element.click()
                except (ElementClickInterceptedException, ElementNotInteractableException):
                    self.driver.execute_script("arguments[0].click();", element)
                time.sleep(1)

                # Debug: Check element type before passing to confirm_submission
                logging.info(f"Element type after click: {type(element)}")
                logging.info(f"Element still has is_displayed: {hasattr(element, 'is_displayed')}")

                if self.confirm_submission(original_url, original_windows, element):
                    return True
            except (TimeoutException, WebDriverException) as e:
                logging.warning(f"Failed to find submit element with xpath '{xpath}': {type(e).__name__}: {e}")
                continue
        return False

    def confirm_submission(
        self,
        initial_url: str,
        initial_windows: list[str],
        submit_element,
    ) -> bool:
        # Debug logging to catch the type issue
        logging.info(f"confirm_submission called with submit_element type: {type(submit_element)}")
        logging.info(f"submit_element value: {submit_element}")
        logging.info(f"submit_element attributes: {dir(submit_element) if hasattr(submit_element, '__dir__') else 'No dir available'}")
        
        # Early validation - if submit_element is not a WebElement, return False immediately
        if not hasattr(submit_element, 'is_displayed'):
            logging.error(f"submit_element is {type(submit_element)}, value: {submit_element}")
            logging.error(f"submit_element attributes: {dir(submit_element) if hasattr(submit_element, '__dir__') else 'No dir available'}")
            return False
        confirmation_texts = [
            "ありがとうございました",
            "送信完了",
            "送信されました",
            "登録が完了しました",
            "完了しました",
            "Thank you",
            "Your message has been sent",
            "Submission successful",
            "Success",
            "Form submitted",
            "確認しました",
            "受付完了",
            "送信成功",
        ]
        tag_variants = ["p", "div", "span", "h1", "h2", "section"]

        # --- URL change
        try:
            WebDriverWait(self.driver, 5).until(
                lambda d: d.current_url != initial_url
            )
            return True
        except TimeoutException:
            pass

        end_time = time.time() + self.CONFIRM_TIMEOUT
        while time.time() < end_time:
            # --- success message in DOM
            for tag in tag_variants:
                for msg in confirmation_texts:
                    xpath = f"//{tag}[contains(text(),'{msg}')]"
                    if self.driver.find_elements(By.XPATH, xpath):
                        return True

            # --- modal / overlay
            if self.driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'modal') or contains(@class,'overlay')][contains(text(),'送信') or contains(text(),'Thank you')]",
            ):
                return True

            # --- new window / tab
            if len(self.driver.window_handles) > len(initial_windows):
                return True

            # --- JS alert
            try:
                alert = self.driver.switch_to.alert
                alert.accept()
                return True
            except NoAlertPresentException:
                pass

            # --- submit element state
            try:
                if EC.staleness_of(submit_element)(self.driver):
                    return True
            except StaleElementReferenceException:
                return True
            try:
                # Check if submit_element is actually a WebElement
                logging.info(f"About to check submit_element.is_displayed() - type: {type(submit_element)}")
                if not hasattr(submit_element, 'is_displayed'):
                    logging.error(f"submit_element is not a WebElement, got type: {type(submit_element)}, value: {submit_element}")
                    logging.error(f"submit_element attributes: {dir(submit_element) if hasattr(submit_element, '__dir__') else 'No dir available'}")
                    return False

                logging.info(f"Calling submit_element.is_displayed() and is_enabled()")
                is_displayed = submit_element.is_displayed()
                is_enabled = submit_element.is_enabled()
                logging.info(f"Element state - displayed: {is_displayed}, enabled: {is_enabled}")
                
                if not is_displayed or not is_enabled:
                    return True
            except StaleElementReferenceException:
                return True
            except AttributeError as e:
                logging.error(f"AttributeError in confirm_submission: {e}, submit_element type: {type(submit_element)}")
                return False

            time.sleep(1)
        return False
