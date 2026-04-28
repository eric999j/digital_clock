"""URL 驗證器測試。"""
import unittest

from core.url_validator import is_safe_url


class TestUrlValidator(unittest.TestCase):
    def test_http_allowed(self):
        self.assertTrue(is_safe_url("http://example.com"))

    def test_https_allowed(self):
        self.assertTrue(is_safe_url("https://example.com/path?q=1"))

    def test_https_uppercase_scheme(self):
        self.assertTrue(is_safe_url("HTTPS://example.com"))

    def test_whitespace_trimmed(self):
        self.assertTrue(is_safe_url("  https://example.com  "))

    def test_file_scheme_rejected(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"))

    def test_javascript_scheme_rejected(self):
        self.assertFalse(is_safe_url("javascript:alert(1)"))

    def test_ftp_rejected(self):
        self.assertFalse(is_safe_url("ftp://example.com"))

    def test_empty_string_rejected(self):
        self.assertFalse(is_safe_url(""))

    def test_none_rejected(self):
        self.assertFalse(is_safe_url(None))

    def test_non_string_rejected(self):
        self.assertFalse(is_safe_url(12345))

    def test_missing_host_rejected(self):
        self.assertFalse(is_safe_url("https://"))

    def test_relative_path_rejected(self):
        self.assertFalse(is_safe_url("/path/only"))

    def test_plain_text_rejected(self):
        self.assertFalse(is_safe_url("not a url"))


if __name__ == '__main__':
    unittest.main()
