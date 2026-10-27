"""以不經 shell 的方式啟動外部程式，供整點啟動與設定視窗測試共用。"""
import logging
import os
import shlex
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)


class LaunchError(Exception):
    """程式無法啟動（路徑不存在、起始目錄無效、系統拒絕等）。"""


def program_exists(command: str) -> bool:
    """檢查程式是否為存在的檔案，或可在 PATH 中找到（支援環境變數展開）。"""
    expanded = os.path.expandvars(command.strip().strip('"'))
    return bool(expanded) and (os.path.isfile(expanded) or shutil.which(expanded) is not None)


def _build_args(command: str, arguments: str) -> str | list[str]:
    """組出 Popen 參數：Windows 保留原始命令列字串，其餘平台以 shlex 切分。"""
    if sys.platform == "win32":
        line = subprocess.list2cmdline([command])
        return f"{line} {arguments}" if arguments else line
    return [command, *shlex.split(arguments)]


def launch_program(command: str, arguments: str = "", working_dir: str = "") -> None:
    """啟動程式但不等待結束；不使用 shell，參數不會被 shell 解讀。

    Args:
        command: 程式路徑或 PATH 中的可執行檔名稱（支援環境變數展開）
        arguments: 命令列參數字串
        working_dir: 起始目錄；空字串表示沿用目前目錄

    Raises:
        LaunchError: 無法啟動時
    """
    command = os.path.expandvars(command.strip().strip('"'))
    arguments = os.path.expandvars((arguments or "").strip())
    cwd = os.path.expandvars((working_dir or "").strip().strip('"')) or None

    if not command:
        raise LaunchError("未指定程式路徑")
    if not program_exists(command):
        raise LaunchError(f"找不到程式：{command}")
    if cwd and not os.path.isdir(cwd):
        raise LaunchError(f"起始目錄不存在：{cwd}")

    kwargs: dict = {"cwd": cwd}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(_build_args(command, arguments), **kwargs)  # noqa: S603 - 不使用 shell
    except (OSError, ValueError) as e:
        raise LaunchError(f"無法啟動 {command}：{e}") from e
    logger.info("Launched program: %s %s", command, arguments)
