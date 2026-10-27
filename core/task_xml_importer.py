"""匯入 Windows 工作排程器匯出的任務 XML，轉成整點啟動規則。

支援每日／每週的 CalendarTrigger 搭配 Exec 動作；其餘設定會略過並回報警告。
"""
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.launch_rules import RULE_PROGRAM
from core.program_launcher import program_exists

logger = logging.getLogger(__name__)

MAX_XML_BYTES = 1024 * 1024
_DAY_INDEX = {
    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
    'Friday': 4, 'Saturday': 5, 'Sunday': 6,
}
_TIME_RE = re.compile(r'T(\d{2}):(\d{2})')


class TaskImportError(ValueError):
    """XML 無法解析或不是工作排程器任務檔。"""


@dataclass
class ImportResult:
    """匯入結果：規則清單與不影響匯入的警告訊息。"""
    rules: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _child(elem: ET.Element, name: str) -> ET.Element | None:
    return next((c for c in elem if _local(c.tag) == name), None)


def _text(elem: ET.Element, name: str) -> str:
    child = _child(elem, name)
    return (child.text or '').strip() if child is not None else ''


def _parse_root(data: bytes) -> ET.Element:
    # 去掉 NUL 後即可同時檢查 UTF-8 / UTF-16；任務檔不需要 DOCTYPE，拒絕以避免實體展開攻擊
    if b'<!DOCTYPE' in data.replace(b'\x00', b'').upper():
        raise TaskImportError("不支援含 DOCTYPE 宣告的 XML")
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        raise TaskImportError(f"XML 格式錯誤：{e}") from e


def _parse_trigger(trigger: ET.Element, warnings: list[str]) -> tuple[int, list[int]] | None:
    """回傳 (整點, 星期清單)；不支援時回傳 None 並記錄警告。"""
    kind = _local(trigger.tag)
    if kind != 'CalendarTrigger':
        warnings.append(f"略過不支援的觸發條件：{kind}")
        return None
    if _text(trigger, 'Enabled').lower() == 'false':
        warnings.append("略過已停用的觸發條件")
        return None

    match = _TIME_RE.search(_text(trigger, 'StartBoundary'))
    if not match:
        warnings.append("略過缺少開始時間的觸發條件")
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if minute:
        warnings.append(f"{hour:02d}:{minute:02d} 已調整為整點 {hour:02d}:00")

    by_week, by_day = _child(trigger, 'ScheduleByWeek'), _child(trigger, 'ScheduleByDay')
    if by_week is not None:
        days_elem = _child(by_week, 'DaysOfWeek')
        weekdays = sorted(
            _DAY_INDEX[_local(d.tag)] for d in (days_elem if days_elem is not None else [])
            if _local(d.tag) in _DAY_INDEX
        )
        if not weekdays:
            warnings.append("略過未指定星期的每週觸發條件")
            return None
        interval = _text(by_week, 'WeeksInterval')
        if interval not in ('', '1'):
            warnings.append(f"每 {interval} 週的間隔已視為每週")
    elif by_day is not None:
        weekdays = list(range(7))
        interval = _text(by_day, 'DaysInterval')
        if interval not in ('', '1'):
            warnings.append(f"每 {interval} 天的間隔已視為每天")
    else:
        warnings.append("略過不支援的排程類型（僅支援每日／每週）")
        return None

    if _child(trigger, 'Repetition') is not None:
        warnings.append("重複執行設定未匯入，僅保留起始整點")
    return hour, weekdays


def _parse_actions(root: ET.Element, warnings: list[str]) -> list[dict[str, str]]:
    actions_elem = _child(root, 'Actions')
    actions: list[dict[str, str]] = []
    for action in (actions_elem if actions_elem is not None else []):
        kind = _local(action.tag)
        if kind != 'Exec':
            warnings.append(f"略過不支援的動作：{kind}")
            continue
        command = _text(action, 'Command').strip('"')
        if not command:
            warnings.append("略過未指定程式的動作")
            continue
        actions.append({
            'command': command,
            'arguments': _text(action, 'Arguments'),
            'working_dir': _text(action, 'WorkingDirectory').strip('"'),
        })
    return actions


def parse_task_xml(data: bytes) -> ImportResult:
    """解析工作排程器任務 XML。

    Raises:
        TaskImportError: 檔案過大、格式錯誤或不是任務檔
    """
    if len(data) > MAX_XML_BYTES:
        raise TaskImportError("檔案過大，不像是工作排程器任務檔")
    root = _parse_root(data)
    if _local(root.tag) != 'Task':
        raise TaskImportError("不是工作排程器匯出的任務 XML")

    result = ImportResult()
    triggers_elem = _child(root, 'Triggers')
    triggers = [
        parsed for t in (triggers_elem if triggers_elem is not None else [])
        if (parsed := _parse_trigger(t, result.warnings)) is not None
    ]
    actions = _parse_actions(root, result.warnings)
    if not triggers:
        raise TaskImportError("找不到可匯入的每日／每週觸發條件")
    if not actions:
        raise TaskImportError("找不到可匯入的「啟動程式」動作")

    registration = _child(root, 'RegistrationInfo')
    name = _text(registration, 'URI').lstrip('\\') if registration is not None else ''

    for hour, weekdays in triggers:
        for action in actions:
            rule: dict[str, Any] = {
                'type': RULE_PROGRAM, **action,
                'start_hour': hour, 'end_hour': hour, 'weekdays': weekdays,
            }
            if name:
                rule['name'] = name
            result.rules.append(rule)

    for rule in result.rules:
        if not program_exists(rule['command']):
            result.warnings.append(f"本機找不到程式：`{rule['command']}`")
            break
    return result


def import_task_xml(path: str | Path) -> ImportResult:
    """讀取並解析工作排程器任務 XML 檔（支援 UTF-16 / UTF-8）。

    Raises:
        TaskImportError: 讀檔失敗或內容不合法
    """
    file_path = Path(path)
    try:
        if file_path.stat().st_size > MAX_XML_BYTES:
            raise TaskImportError("檔案過大，不像是工作排程器任務檔")
        data = file_path.read_bytes()
    except OSError as e:
        raise TaskImportError(f"無法讀取檔案：{e}") from e
    return parse_task_xml(data)
