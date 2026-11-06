"""整點啟動程式規則的可執行性驗證。

本模組不宣稱能判斷任意程式是否安全；使用者啟用或手動執行規則時，
UI 會顯示完整指令並要求確認。這裡只驗證可客觀判定的設定錯誤。
"""
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_WINDOWS_EXTENSIONS = frozenset({'.exe', '.bat', '.cmd', '.com'})
_MAX_ARGUMENT_LENGTH = 4096


@dataclass(frozen=True)
class RuleCheck:
    """程式規則的驗證結果。"""

    errors: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """沒有設定錯誤時即可執行。"""
        return not self.errors


def _resolve_command(command: str) -> str | None:
    """回傳實際的程式檔案路徑；找不到回傳 None。"""
    expanded = os.path.expandvars(command.strip().strip('"'))
    if not expanded:
        return None
    if os.path.isfile(expanded):
        return expanded
    return shutil.which(expanded)


def _has_control_chars(*values: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for value in values for ch in value)


def check_program_rule(rule: dict[str, Any]) -> RuleCheck:
    """驗證程式規則是否可執行，不對程式內容做啟發式安全判斷。"""
    command = str(rule.get('command', '')).strip().strip('"')
    arguments = str(rule.get('arguments', '')).strip()
    cwd = str(rule.get('working_dir', '')).strip().strip('"')
    resolved = _resolve_command(command)
    errors: list[str] = []
    if not command:
        errors.append("未指定程式路徑。")
    elif resolved is None:
        errors.append(f"找不到程式：{command}")
    elif sys.platform == 'win32' and Path(resolved).suffix.lower() not in _WINDOWS_EXTENSIONS:
        errors.append("不支援的程式類型（僅限 .exe、.bat、.cmd、.com）。")
    elif sys.platform != 'win32' and not os.access(resolved, os.X_OK):
        errors.append("此檔案沒有執行權限。")
    if cwd and not os.path.isdir(os.path.expandvars(cwd)):
        errors.append(f"起始目錄不存在：{cwd}")
    if len(arguments) > _MAX_ARGUMENT_LENGTH:
        errors.append(f"參數過長（上限 {_MAX_ARGUMENT_LENGTH} 字元）。")
    if _has_control_chars(command, arguments, cwd):
        errors.append("路徑或參數含有不合法的控制字元。")
    start, end = rule.get('start_hour', 0), rule.get('end_hour', 23)
    if not (isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= 23):
        errors.append("時段設定不正確。")
    weekdays = rule.get('weekdays')
    if weekdays and not all(isinstance(day, int) and 0 <= day <= 6 for day in weekdays):
        errors.append("星期設定不正確。")
    return RuleCheck(errors=tuple(errors))
