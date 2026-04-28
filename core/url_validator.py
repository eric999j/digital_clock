"""URL 驗證工具，用於避免危險 scheme（如 file://、javascript:）被開啟。"""
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = frozenset({"http", "https"})


def is_safe_url(url: str | None) -> bool:
    """
    檢查 URL 是否為允許的 scheme（http/https）且具有 host。

    Args:
        url: 待驗證的 URL 字串

    Returns:
        True 表示安全可開啟；False 表示應拒絕。
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except (ValueError, AttributeError):
        return False
    return parsed.scheme.lower() in ALLOWED_SCHEMES and bool(parsed.netloc)
