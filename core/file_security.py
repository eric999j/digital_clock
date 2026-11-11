"""本機檔案權限工具：限制設定檔僅目前使用者可讀寫。"""
import contextlib
import getpass
import logging
import os
import stat
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_ICACLS_TIMEOUT_SEC = 10


def restrict_to_owner(path: Path) -> bool:
    """
    將檔案權限限縮為僅目前使用者可讀寫。

    非 Windows 使用 ``chmod 600``；Windows 以 ``icacls`` 移除繼承並只授權目前使用者。

    Args:
        path: 目標檔案

    Returns:
        是否成功套用（失敗只記錄，不拋出例外）
    """
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
            return True
        except OSError as e:
            logger.warning("Unable to restrict permissions: %s", e)
            return False
    try:
        result = subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"],
            capture_output=True,
            timeout=_ICACLS_TIMEOUT_SEC,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning("Unable to restrict permissions: %s", e)
        return False
    if result.returncode != 0:
        logger.warning("icacls failed with exit code %s", result.returncode)
        return False
    return True


def is_overly_permissive(path: Path) -> bool:
    """非 Windows 時檢查群組／其他人是否有任何權限；Windows 不檢查，回傳 False。"""
    if os.name == "nt":
        return False
    with contextlib.suppress(OSError):
        return bool(path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO))
    return False
