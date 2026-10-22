import unittest
from unittest.mock import patch

from ui import popup_utils


class OpenUrlSafetyTests(unittest.TestCase):
    def test_http_and_https_are_opened(self) -> None:
        for url in ("http://example.com", "  https://example.com/a?b=1  "):
            with patch("ui.popup_utils.webbrowser.open") as mock_open:
                popup_utils._open_url(url)
                mock_open.assert_called_once_with(url.strip())

    def test_dangerous_urls_are_rejected(self) -> None:
        bad = (
            "file:///C:/payload.exe",
            "C:\\path\\evil.exe",
            "javascript:alert(1)",
            "ms-msdt:/id PCWDiagnostic",
            "https://example.com/\r\nx",
            "",
        )
        for url in bad:
            with patch("ui.popup_utils.webbrowser.open") as mock_open:
                popup_utils._open_url(url)
                mock_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
