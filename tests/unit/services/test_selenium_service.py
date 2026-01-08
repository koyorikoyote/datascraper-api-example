import unittest
from unittest.mock import patch, MagicMock, call
import os
import tempfile
import subprocess
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.common.exceptions import WebDriverException

from src.services.selenium import SeleniumService
from src.utils.constants import StatusConst
from src.utils.legacy_selenium_contact import LegacySeleniumContact


class TestSeleniumService(unittest.TestCase):
    """Unit tests for the SeleniumService class."""

    @patch('src.services.selenium.webdriver.Remote')
    @patch('src.services.selenium.subprocess.Popen')
    @patch('src.services.selenium.tempfile.mkdtemp')
    def setUp(self, mock_mkdtemp, mock_popen, mock_remote):
        """Set up test fixtures."""
        # Mock the tempfile.mkdtemp to return a predictable path
        mock_mkdtemp.return_value = '/tmp/test-selenium-profile'
        
        # Mock the webdriver.Remote to return a mock driver
        self.mock_driver = MagicMock()
        mock_remote.return_value = self.mock_driver
        
        # Create the service with headless=True (default)
        self.service = SeleniumService(headless=True)
        
        # Reset mocks for the actual tests
        mock_mkdtemp.reset_mock()
        mock_popen.reset_mock()
        mock_remote.reset_mock()

    @patch('src.services.selenium.webdriver.Remote')
    def test_create_driver_headless(self, mock_remote):
        """Test _create_driver method with headless=True."""
        # Setup
        mock_driver = MagicMock()
        mock_remote.return_value = mock_driver
        
        # Execute
        driver = self.service._create_driver()
        
        # Assert
        self.assertEqual(driver, mock_driver)
        mock_remote.assert_called_once()
        
        # Check that the options include headless
        options = mock_remote.call_args[1]['options']
        self.assertIn('--headless', options.arguments)
        self.assertIn('--disable-gpu', options.arguments)
        self.assertIn('--no-sandbox', options.arguments)
        self.assertIn('--disable-dev-shm-usage', options.arguments)
        self.assertIn(f'--user-data-dir={self.service._profile_dir}', options.arguments)

    @patch('src.services.selenium.webdriver.Remote')
    @patch('src.services.selenium.subprocess.Popen')
    @patch('src.services.selenium.tempfile.mkdtemp')
    def test_create_driver_headed(self, mock_mkdtemp, mock_popen, mock_remote):
        """Test _create_driver method with headless=False."""
        # Setup
        mock_mkdtemp.return_value = '/tmp/test-selenium-profile'
        mock_driver = MagicMock()
        mock_remote.return_value = mock_driver
        
        # Save original environment
        original_display = os.environ.get('DISPLAY')
        
        try:
            # Remove DISPLAY from environment to test Xvfb startup
            if 'DISPLAY' in os.environ:
                del os.environ['DISPLAY']
            
            # Create service with headless=False
            service = SeleniumService(headless=False)
            
            # Assert Xvfb was started
            mock_popen.assert_called_once_with(
                ["Xvfb", ":99", "-screen", "0", "1920x1080x24"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            
            # Assert DISPLAY was set
            self.assertEqual(os.environ.get('DISPLAY'), ':99')
            
            # Reset the driver mock for the next call
            mock_remote.reset_mock()
            
            # Execute
            driver = service._create_driver()
            
            # Assert
            self.assertEqual(driver, mock_driver)
            mock_remote.assert_called_once()
            
            # Check that the options do NOT include headless
            options = mock_remote.call_args[1]['options']
            self.assertNotIn('--headless', options.arguments)
            
        finally:
            # Restore original environment
            if original_display is not None:
                os.environ['DISPLAY'] = original_display
            elif 'DISPLAY' in os.environ:
                del os.environ['DISPLAY']

    def test_is_session_valid_true(self):
        """Test _is_session_valid when session is valid."""
        # Setup
        self.mock_driver.current_url = 'http://example.com'
        
        # Execute
        result = self.service._is_session_valid()
        
        # Assert
        self.assertTrue(result)

    def test_is_session_valid_false(self):
        """Test _is_session_valid when session is invalid."""
        # Setup
        self.mock_driver.current_url = MagicMock(side_effect=WebDriverException())
        
        # Execute
        result = self.service._is_session_valid()
        
        # Assert
        self.assertFalse(result)

    @patch('src.services.selenium.SeleniumService._create_driver')
    def test_ensure_valid_session_when_valid(self, mock_create_driver):
        """Test _ensure_valid_session when session is already valid."""
        # Setup
        self.mock_driver.current_url = 'http://example.com'
        
        # Execute
        self.service._ensure_valid_session()
        
        # Assert
        mock_create_driver.assert_not_called()

    @patch('src.services.selenium.SeleniumService._create_driver')
    def test_ensure_valid_session_when_invalid(self, mock_create_driver):
        """Test _ensure_valid_session when session is invalid."""
        # Setup
        self.mock_driver.current_url = MagicMock(side_effect=WebDriverException())
        new_mock_driver = MagicMock()
        mock_create_driver.return_value = new_mock_driver
        
        # Execute
        self.service._ensure_valid_session()
        
        # Assert
        self.mock_driver.quit.assert_called_once()
        mock_create_driver.assert_called_once()
        self.assertEqual(self.service.driver, new_mock_driver)

    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    def test_get_html_content_success(self, mock_ensure_valid_session):
        """Test get_html_content method with successful retrieval."""
        # Setup
        self.mock_driver.page_source = '<html><body>Test content</body></html>'
        
        # Execute
        result = self.service.get_html_content('http://example.com')
        
        # Assert
        mock_ensure_valid_session.assert_called_once()
        self.mock_driver.get.assert_called_once_with('http://example.com')
        self.assertEqual(result, '<html><body>Test content</body></html>')
        
    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    def test_get_html_content_retry(self, mock_ensure_valid_session):
        """Test get_html_content method with retry."""
        # Setup
        # First attempt fails, second succeeds
        self.mock_driver.get.side_effect = [WebDriverException("Test exception"), None]
        self.mock_driver.page_source = '<html><body>Test content</body></html>'
        
        # Execute
        result = self.service.get_html_content('http://example.com', max_retries=2)
        
        # Assert
        self.assertEqual(mock_ensure_valid_session.call_count, 2)
        self.assertEqual(self.mock_driver.get.call_count, 2)
        self.assertEqual(result, '<html><body>Test content</body></html>')
        
    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    def test_get_html_content_empty(self, mock_ensure_valid_session):
        """Test get_html_content method with empty page source."""
        # Setup
        self.mock_driver.page_source = ''
        
        # Execute
        result = self.service.get_html_content('http://example.com')
        
        # Assert
        mock_ensure_valid_session.assert_called_once()
        self.mock_driver.get.assert_called_once_with('http://example.com')
        self.assertEqual(result, '')

    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.BeautifulSoup')
    def test_get_text_content_success(self, mock_bs, mock_ensure_valid_session):
        """Test get_text_content method with successful retrieval."""
        # Setup
        self.mock_driver.page_source = '<html><body>Test content</body></html>'
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        mock_soup.get_text.return_value = 'Test content'
        
        # Execute
        result = self.service.get_text_content('http://example.com')
        
        # Assert
        mock_ensure_valid_session.assert_called_once()
        self.mock_driver.get.assert_called_once_with('http://example.com')
        mock_bs.assert_called_once_with('<html><body>Test content</body></html>', 'html.parser')
        self.assertEqual(result, 'Test content')
        
    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.BeautifulSoup')
    def test_get_text_content_retry(self, mock_bs, mock_ensure_valid_session):
        """Test get_text_content method with retry."""
        # Setup
        # First attempt fails, second succeeds
        self.mock_driver.get.side_effect = [WebDriverException("Test exception"), None]
        self.mock_driver.page_source = '<html><body>Test content</body></html>'
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        mock_soup.get_text.return_value = 'Test content'
        
        # Execute
        result = self.service.get_text_content('http://example.com', max_retries=2)
        
        # Assert
        self.assertEqual(mock_ensure_valid_session.call_count, 2)
        self.assertEqual(self.mock_driver.get.call_count, 2)
        self.assertEqual(result, 'Test content')
        
    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.BeautifulSoup')
    def test_get_text_content_empty(self, mock_bs, mock_ensure_valid_session):
        """Test get_text_content method with empty text content."""
        # Setup
        self.mock_driver.page_source = '<html><body></body></html>'
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        mock_soup.get_text.return_value = ''
        
        # Execute
        result = self.service.get_text_content('http://example.com')
        
        # Assert
        mock_ensure_valid_session.assert_called_once()
        self.mock_driver.get.assert_called_once_with('http://example.com')
        self.assertEqual(result, '')

    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.BeautifulSoup')
    def test_get_all_possible_links_success(self, mock_bs, mock_ensure_valid_session):
        """Test get_all_possible_links method with successful retrieval."""
        # Setup
        self.mock_driver.page_source = '<html><body><a href="/page1">Link 1</a></body></html>'
        
        # Create a mock BeautifulSoup object
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        
        # Mock the find_all method for different elements
        mock_a_tag = MagicMock()
        mock_a_tag.__getitem__.side_effect = lambda key: '/page1' if key == 'href' else None
        mock_soup.find_all.side_effect = lambda tag, **kwargs: [mock_a_tag] if tag == 'a' else []
        
        # Execute
        result = self.service.get_all_possible_links('http://example.com')
        
        # Assert
        mock_ensure_valid_session.assert_called_once()
        self.mock_driver.get.assert_called_once_with('http://example.com')
        self.assertEqual(result, ['http://example.com/page1'])
        
    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.BeautifulSoup')
    def test_get_all_possible_links_retry(self, mock_bs, mock_ensure_valid_session):
        """Test get_all_possible_links method with retry."""
        # Setup
        # First attempt fails, second succeeds
        self.mock_driver.get.side_effect = [WebDriverException("Test exception"), None]
        self.mock_driver.page_source = '<html><body><a href="/page1">Link 1</a></body></html>'
        
        # Create a mock BeautifulSoup object
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        
        # Mock the find_all method for different elements
        mock_a_tag = MagicMock()
        mock_a_tag.__getitem__.side_effect = lambda key: '/page1' if key == 'href' else None
        mock_soup.find_all.side_effect = lambda tag, **kwargs: [mock_a_tag] if tag == 'a' else []
        
        # Execute
        result = self.service.get_all_possible_links('http://example.com', max_retries=2)
        
        # Assert
        self.assertEqual(mock_ensure_valid_session.call_count, 2)
        self.assertEqual(self.mock_driver.get.call_count, 2)
        self.assertEqual(result, ['http://example.com/page1'])
        
    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.BeautifulSoup')
    def test_get_all_possible_links_empty(self, mock_bs, mock_ensure_valid_session):
        """Test get_all_possible_links method with no links found."""
        # Setup
        self.mock_driver.page_source = '<html><body>No links here</body></html>'
        
        # Create a mock BeautifulSoup object
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        
        # Mock the find_all method to return empty lists
        mock_soup.find_all.return_value = []
        
        # Execute
        result = self.service.get_all_possible_links('http://example.com')
        
        # Assert
        mock_ensure_valid_session.assert_called_once()
        self.mock_driver.get.assert_called_once_with('http://example.com')
        self.assertEqual(result, [])

    def test_dict_to_row(self):
        """Test _dict_to_row method."""
        # Setup
        test_dict = {
            'last': 'Doe',
            'first': 'John',
            'email': 'john.doe@example.com',
            # Missing other fields
        }
        
        # Execute
        result = self.service._dict_to_row(test_dict)
        
        # Assert
        expected = [
            'Doe', 'John',  # last, first
            '', '',         # last_kana, first_kana
            '', '',         # last_hira, first_hira
            'john.doe@example.com',  # email
            '', '', '',     # company, department, url
            '', '', '',     # phone1, phone2, phone3
            '', '',         # zip1, zip2
            '', '', '',     # address1, address2, address3
            '', '',         # subject, body
        ]
        self.assertEqual(result, expected)

    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.LegacySeleniumContact')
    def test_send_contact_success(self, mock_legacy_contact_class, mock_ensure_valid_session):
        """Test send_contact method with successful contact."""
        # Setup
        mock_legacy_contact = MagicMock()
        mock_legacy_contact_class.return_value = mock_legacy_contact
        mock_legacy_contact.contact_sending_process.return_value = True
        
        company_list = [
            {
                'properties': {
                    'domain': 'example.com',
                    'name': 'Example Company'
                }
            }
        ]
        
        contact_template = {
            'last': 'Doe',
            'first': 'John',
            'email': 'john.doe@example.com'
        }
        
        # Execute
        result = self.service.send_contact(company_list, contact_template)
        
        # Assert
        mock_ensure_valid_session.assert_called_once()
        mock_legacy_contact_class.assert_called_once_with(driver=self.mock_driver)
        mock_legacy_contact.contact_sending_process.assert_called_once()
        
        # Check that the company status was updated to SUCCESS
        self.assertEqual(result[0]['properties']['status'], StatusConst.SUCCESS)
        
    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.LegacySeleniumContact')
    def test_send_contact_retry_success(self, mock_legacy_contact_class, mock_ensure_valid_session):
        """Test send_contact method with retry that succeeds."""
        # Setup
        mock_legacy_contact = MagicMock()
        mock_legacy_contact_class.return_value = mock_legacy_contact
        # First attempt fails, second succeeds
        mock_legacy_contact.contact_sending_process.side_effect = [False, True]
        
        company_list = [
            {
                'properties': {
                    'domain': 'example.com',
                    'name': 'Example Company'
                }
            }
        ]
        
        contact_template = {
            'last': 'Doe',
            'first': 'John',
            'email': 'john.doe@example.com'
        }
        
        # Execute
        result = self.service.send_contact(company_list, contact_template, max_retries=2)
        
        # Assert
        self.assertEqual(mock_ensure_valid_session.call_count, 2)
        self.assertEqual(mock_legacy_contact_class.call_count, 2)
        self.assertEqual(mock_legacy_contact.contact_sending_process.call_count, 2)
        
        # Check that the company status was updated to SUCCESS
        self.assertEqual(result[0]['properties']['status'], StatusConst.SUCCESS)

    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.LegacySeleniumContact')
    def test_send_contact_failure(self, mock_legacy_contact_class, mock_ensure_valid_session):
        """Test send_contact method with failed contact after all retries."""
        # Setup
        mock_legacy_contact = MagicMock()
        mock_legacy_contact_class.return_value = mock_legacy_contact
        # All attempts fail
        mock_legacy_contact.contact_sending_process.return_value = False
        
        company_list = [
            {
                'properties': {
                    'domain': 'example.com',
                    'name': 'Example Company'
                }
            }
        ]
        
        contact_template = {
            'last': 'Doe',
            'first': 'John',
            'email': 'john.doe@example.com'
        }
        
        # Execute
        result = self.service.send_contact(company_list, contact_template, max_retries=2)
        
        # Assert
        self.assertEqual(mock_ensure_valid_session.call_count, 2)
        self.assertEqual(mock_legacy_contact_class.call_count, 2)
        self.assertEqual(mock_legacy_contact.contact_sending_process.call_count, 2)
        
        # Check that the company status was updated to FAILED
        self.assertEqual(result[0]['properties']['status'], StatusConst.FAILED)

    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.LegacySeleniumContact')
    def test_send_contact_exception(self, mock_legacy_contact_class, mock_ensure_valid_session):
        """Test send_contact method when an exception occurs in all retries."""
        # Setup
        mock_legacy_contact = MagicMock()
        mock_legacy_contact_class.return_value = mock_legacy_contact
        # All attempts raise exceptions
        mock_legacy_contact.contact_sending_process.side_effect = [
            Exception("Test exception 1"),
            Exception("Test exception 2")
        ]
        
        company_list = [
            {
                'properties': {
                    'domain': 'example.com',
                    'name': 'Example Company'
                }
            }
        ]
        
        contact_template = {
            'last': 'Doe',
            'first': 'John',
            'email': 'john.doe@example.com'
        }
        
        # Execute
        result = self.service.send_contact(company_list, contact_template, max_retries=2)
        
        # Assert
        self.assertEqual(mock_ensure_valid_session.call_count, 2)
        self.assertEqual(mock_legacy_contact_class.call_count, 2)
        self.assertEqual(mock_legacy_contact.contact_sending_process.call_count, 2)
        
        # Check that the company status was updated to FAILED
        self.assertEqual(result[0]['properties']['status'], StatusConst.FAILED)
        
    @patch('src.services.selenium.SeleniumService._ensure_valid_session')
    @patch('src.services.selenium.LegacySeleniumContact')
    def test_send_contact_missing_properties(self, mock_legacy_contact_class, mock_ensure_valid_session):
        """Test send_contact method with missing company properties."""
        # Setup
        mock_legacy_contact = MagicMock()
        mock_legacy_contact_class.return_value = mock_legacy_contact
        
        # Company with missing domain
        company_list = [
            {
                'properties': {
                    'name': 'Example Company'
                }
            }
        ]
        
        contact_template = {
            'last': 'Doe',
            'first': 'John',
            'email': 'john.doe@example.com'
        }
        
        # Execute
        result = self.service.send_contact(company_list, contact_template)
        
        # Assert
        mock_ensure_valid_session.assert_called_once()
        mock_legacy_contact_class.assert_not_called()
        mock_legacy_contact.contact_sending_process.assert_not_called()
        
        # Check that the company status was updated to FAILED
        self.assertEqual(result[0]['properties']['status'], StatusConst.FAILED)

    def test_cleanup(self):
        """Test _cleanup method."""
        # Setup
        self.service._xvfb_proc = MagicMock()
        
        # Execute
        self.service._cleanup()
        
        # Assert
        self.mock_driver.quit.assert_called_once()
        self.service._xvfb_proc.terminate.assert_called_once()

    def test_context_manager(self):
        """Test the context manager protocol."""
        # Setup
        mock_cleanup = MagicMock()
        self.service._cleanup = mock_cleanup
        
        # Execute
        with self.service as service:
            # Assert
            self.assertEqual(service, self.service)
        
        # Assert cleanup was called
        mock_cleanup.assert_called_once()


if __name__ == '__main__':
    unittest.main()
