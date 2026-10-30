"""整點啟動「程式」規則的設定驗證與簡易安全檢查。

這不是防毒或沙箱，只攔下「明顯會破壞系統」的做法（格式化、關機、遞迴刪除、
修改開機設定等），避免設定錯誤或匯入的規則一觸發就造成無法復原的後果。

- ``errors``：設定不正確（找不到程式、起始目錄不存在…），無法執行。
- ``blocked``：安全檢查未通過，一律拒絕執行。
- ``warnings``：可以執行，但需讓使用者知道。
"""
import codecs
import os
import re
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_WINDOWS_EXTENSIONS = frozenset({'.exe', '.bat', '.cmd', '.com'})
_SCRIPT_EXTENSIONS = frozenset({'.bat', '.cmd', '.ps1', '.py', '.pyw', '.sh', '.vbs', '.js'})
_BATCH_EXTENSIONS = frozenset({'.bat', '.cmd'})
_MAX_ARGUMENT_LENGTH = 4096
_MAX_SCAN_BYTES = 256 * 1024
_MAX_SCRIPT_ARGS = 5

# 本身就會破壞系統的程式，無論參數為何一律拒絕。
_BLOCKED_PROGRAMS = frozenset({
    'format', 'diskpart', 'bcdedit', 'bcdboot', 'bootsect', 'shutdown', 'logoff',
    'mkfs', 'fdisk', 'parted', 'wipefs', 'shred', 'sdelete', 'sdelete64',
    'reboot', 'halt', 'poweroff',
})

# 命令直譯器的行為完全取決於參數，需提醒使用者。
_INTERPRETERS = frozenset({
    'cmd', 'powershell', 'pwsh', 'wscript', 'cscript', 'mshta', 'rundll32', 'regsvr32',
    'bash', 'sh', 'zsh',
})

# (樣式, 說明)：同時用於檢查參數與批次檔／腳本內容。
_DANGEROUS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), label)
    for pattern, label in (
        (r'\bformat(\.com)?\s+[a-z]:', '格式化磁碟'),
        (r'\b(rd|rmdir)\b[^\n&|]*\s/s\b', '遞迴刪除資料夾 (rd /s)'),
        (r'\b(del|erase)\b[^\n&|]*\s/s\b', '遞迴刪除檔案 (del /s)'),
        (r'\bremove-item\b[^\n]*-recurse', '遞迴刪除 (Remove-Item -Recurse)'),
        (r'\brm\s+(-\w*r\w*f|-\w*f\w*r|--recursive)', '遞迴強制刪除 (rm -rf)'),
        (r'rmtree\(\s*r?[\'"](?:[a-z]:[\\/]?|/)[\'"]', '刪除整個磁碟根目錄'),
        (r'\bshutdown(\.exe)?\s+[-/]', '關機或重新啟動'),
        (r'\b(stop|restart)-computer\b', '關機或重新啟動'),
        (r'\bdiskpart\b', '磁碟分割工具 (diskpart)'),
        (r'\bbcdedit\b', '修改開機設定 (bcdedit)'),
        (r'\breg(\.exe)?\s+delete\b', '刪除登錄機碼 (reg delete)'),
        (r'\bvssadmin\b[^\n]*\bdelete\b', '刪除系統還原點 (vssadmin delete)'),
        (r'\bcipher(\.exe)?\s+/w', '覆寫磁碟可用空間 (cipher /w)'),
        (r'\bmkfs(\.\w+)?\b', '建立檔案系統 (mkfs)'),
        (r'\bdd\s+if=', '直接寫入磁碟 (dd)'),
        (r'\b(format-volume|clear-disk|remove-partition|initialize-disk)\b', '磁碟格式化或分割操作'),
        (r':\(\)\s*\{\s*:\|:&\s*\};:', 'fork bomb'),
        (r'%0\s*\|\s*%0', 'fork bomb'),
        (r'\btaskkill\b[^\n]*\b(csrss|wininit|winlogon|lsass|services|smss)\.exe', '終止關鍵系統程序'),
    )
)


@dataclass(frozen=True)
class RuleCheck:
    """程式規則的檢查結果。"""

    errors: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """沒有設定錯誤也沒有安全疑慮時才允許執行。"""
        return not self.errors and not self.blocked


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


def scan_text(text: str) -> list[str]:
    """回傳文字中命中的危險樣式說明（去重、保留順序）。"""
    found: list[str] = []
    for pattern, label in _DANGEROUS_PATTERNS:
        if pattern.search(text) and label not in found:
            found.append(label)
    return found


def _referenced_scripts(resolved: str | None, arguments: str, cwd: str) -> list[str]:
    """找出會被執行的腳本檔：程式本身是批次檔，或參數中指向存在的腳本。"""
    scripts: list[str] = []
    if resolved and Path(resolved).suffix.lower() in _BATCH_EXTENSIONS:
        scripts.append(resolved)
    try:
        tokens = shlex.split(arguments, posix=sys.platform != 'win32')
    except ValueError:
        tokens = arguments.split()
    base = cwd or os.getcwd()
    for token in tokens[:_MAX_SCRIPT_ARGS]:
        path = os.path.expandvars(token.strip('"\''))
        if not os.path.isabs(path):
            path = os.path.join(base, path)
        if Path(path).suffix.lower() in _SCRIPT_EXTENSIONS and os.path.isfile(path) and path not in scripts:
            scripts.append(path)
    return scripts


def _read_script(path: str) -> tuple[str, bool]:
    """讀取腳本前 ``_MAX_SCAN_BYTES`` 位元組；回傳 (內容, 是否被截斷)。"""
    with open(path, 'rb') as f:
        data = f.read(_MAX_SCAN_BYTES + 1)
    truncated = len(data) > _MAX_SCAN_BYTES
    data = data[:_MAX_SCAN_BYTES]
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode('utf-16', errors='replace'), truncated
    return data.decode('utf-8', errors='replace'), truncated


def _check_config(rule: dict[str, Any], resolved: str | None, command: str, arguments: str, cwd: str) -> list[str]:
    errors: list[str] = []
    if not command:
        errors.append("未指定程式路徑。")
    elif resolved is None:
        errors.append(f"找不到程式：{command}")
    elif sys.platform == 'win32':
        if Path(resolved).suffix.lower() not in _WINDOWS_EXTENSIONS:
            errors.append("不支援的程式類型（僅限 .exe、.bat、.cmd、.com）。")
    elif not os.access(resolved, os.X_OK):
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
    if weekdays and not all(isinstance(d, int) and 0 <= d <= 6 for d in weekdays):
        errors.append("星期設定不正確。")
    return errors


def _check_safety(
    resolved: str | None, command: str, arguments: str, cwd: str,
) -> tuple[list[str], list[str]]:
    blocked: list[str] = []
    warnings: list[str] = []

    name = Path(resolved or command).stem.lower()
    if name in _BLOCKED_PROGRAMS:
        blocked.append(f"「{name}」會直接影響系統（關機、格式化或磁碟操作）。")
    if name in _INTERPRETERS:
        warnings.append(f"「{name}」是命令直譯器，實際行為取決於參數內容，請確認無誤。")

    for label in scan_text(arguments):
        blocked.append(f"參數含有危險操作：{label}")

    for script in _referenced_scripts(resolved, arguments, cwd):
        try:
            text, truncated = _read_script(script)
        except OSError:
            warnings.append(f"無法讀取腳本進行檢查：{script}")
            continue
        for label in scan_text(text):
            blocked.append(f"腳本 {os.path.basename(script)} 含有危險操作：{label}")
        if truncated:
            warnings.append(f"腳本 {os.path.basename(script)} 過大，僅檢查前 {_MAX_SCAN_BYTES // 1024} KB。")
    return blocked, warnings


def check_program_rule(rule: dict[str, Any]) -> RuleCheck:
    """檢查程式規則的設定是否正確，並做簡易安全檢查。

    Args:
        rule: 整點啟動規則（``type=program``，含 ``command``、``arguments``、``working_dir`` 等）

    Returns:
        檢查結果；僅在 ``ok`` 為 True 時才應允許使用者執行。
    """
    command = str(rule.get('command', '')).strip().strip('"')
    arguments = str(rule.get('arguments', '')).strip()
    cwd = str(rule.get('working_dir', '')).strip().strip('"')
    resolved = _resolve_command(command)

    errors = _check_config(rule, resolved, command, arguments, cwd)
    blocked, warnings = _check_safety(resolved, command, arguments, os.path.expandvars(cwd))
    return RuleCheck(tuple(errors), tuple(blocked), tuple(warnings))
