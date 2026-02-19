import sys
import unittest
from unittest.mock import MagicMock

# Mock dependencies before importing bot_logic
sys.modules['wavelink'] = MagicMock()
sys.modules['discord'] = MagicMock()

import bot_logic

class TestSecurity(unittest.TestCase):
    """
    Security-focused tests for bot_logic.py.
    """

    def test_ssrf_blocking(self):
        """
        Verify that validate_query blocks requests to local network and cloud metadata services.
        """
        dangerous_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "https://169.254.169.254/user-data",
            "http://127.0.0.1:8080/admin",
            "http://localhost:3000",
            "http://0.0.0.0:80",
            "http://[::1]:80",
        ]

        for url in dangerous_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError) as cm:
                    bot_logic.validate_query(url)
                self.assertIn("Access to", str(cm.exception))

    def test_valid_urls_allowed(self):
        """
        Verify that safe URLs are still allowed.
        """
        safe_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://google.com",
            "https://soundcloud.com/artist/track",
        ]

        for url in safe_urls:
            with self.subTest(url=url):
                try:
                    result = bot_logic.validate_query(url)
                    self.assertEqual(result, url)
                except ValueError as e:
                    self.fail(f"Safe URL {url} was blocked: {e}")

    def test_file_protocol_blocking(self):
        """
        Verify that file:// protocol is blocked (LFI protection).
        """
        dangerous_urls = [
            "file:///etc/passwd",
            "FILE:///C:/Windows/System32/drivers/etc/hosts",
        ]

        for url in dangerous_urls:
             with self.subTest(url=url):
                with self.assertRaises(ValueError) as cm:
                    bot_logic.validate_query(url)
                self.assertIn("protocol is not supported", str(cm.exception))

    def test_ssrf_blocking_case_insensitive(self):
        """
        Verify that SSRF blocking works regardless of scheme case.
        """
        dangerous_urls = [
            "HTTP://169.254.169.254/latest/meta-data/",
            "Https://localhost:3000",
        ]

        for url in dangerous_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError) as cm:
                    bot_logic.validate_query(url)
                self.assertIn("Access to", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
