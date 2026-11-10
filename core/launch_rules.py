"""整點啟動規則的共用定義：規則型別、識別鍵、顯示文字與合併。

規則仍存放於 config 的 ``hourly_web_reminder.url_rules``，舊版只有 ``url`` 的規則視為網頁規則。
"""
import json
from typing import Any

from core.url_validator import is_safe_url

RULE_URL = 'url'
RULE_PROGRAM = 'program'
TRIGGER_STARTUP = 'startup'

_WEEKDAY_NAMES = ('一', '二', '三', '四', '五', '六', '日')
_BACKUP_FORMAT = 'digital-clock-hourly-launch'
_BACKUP_VERSION = 1


def _validate_backup(data: Any) -> tuple[list[dict[str, Any]], bool]:
    """驗證備份結構，回傳規則與上班日設定。"""
    if not isinstance(data, dict) or data.get('format') != _BACKUP_FORMAT:
        raise ValueError('不是整點啟動規則備份。')
    if type(data.get('version')) is not int or data['version'] != _BACKUP_VERSION:
        raise ValueError('不支援的備份版本。')
    rules = data.get('url_rules')
    work_days_only = data.get('work_days_only')
    if not isinstance(rules, list) or type(work_days_only) is not bool:
        raise ValueError('備份缺少有效的規則清單或上班日設定。')
    for index, rule in enumerate(rules, 1):
        if not isinstance(rule, dict):
            raise ValueError(f'第 {index} 條規則格式錯誤。')
        if rule.get('type', RULE_URL) not in (RULE_URL, RULE_PROGRAM):
            raise ValueError(f'第 {index} 條規則的類型無效。')
        target_key = 'command' if rule_type(rule) == RULE_PROGRAM else 'url'
        target = rule.get(target_key)
        if not isinstance(target, str) or not target.strip():
            raise ValueError(f'第 {index} 條規則缺少啟動目標。')
        if target_key == 'url' and not is_safe_url(target):
            raise ValueError(f'第 {index} 條規則的網址無效。')
        if rule.get('trigger', '') not in ('', TRIGGER_STARTUP):
            raise ValueError(f'第 {index} 條規則的觸發方式無效。')
        for key in ('arguments', 'working_dir', 'name'):
            if key in rule and not isinstance(rule[key], str):
                raise ValueError(f'第 {index} 條規則的 {key} 格式錯誤。')
        if 'enabled' in rule and type(rule['enabled']) is not bool:
            raise ValueError(f'第 {index} 條規則的啟用狀態無效。')
        if not is_startup_rule(rule) or 'start_hour' in rule or 'end_hour' in rule:
            start, end = rule.get('start_hour'), rule.get('end_hour')
            if type(start) is not int or type(end) is not int or not 0 <= start <= end <= 23:
                raise ValueError(f'第 {index} 條規則的時段無效。')
        if 'weekdays' in rule:
            days = rule['weekdays']
            if not isinstance(days, list) or any(type(day) is not int or not 0 <= day <= 6 for day in days):
                raise ValueError(f'第 {index} 條規則的星期設定無效。')
    return rules, work_days_only


def encode_rules_backup(rules: list[dict[str, Any]], work_days_only: bool) -> str:
    """將規則及上班日設定序列化為版本化備份。"""
    data = {'format': _BACKUP_FORMAT, 'version': _BACKUP_VERSION,
            'work_days_only': work_days_only, 'url_rules': rules}
    _validate_backup(data)
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def decode_rules_backup(text: str) -> tuple[list[dict[str, Any]], bool]:
    """讀取規則備份；程式規則一律停用，須經確認後啟用。"""
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise ValueError('JSON 格式錯誤。') from error
    rules, work_days_only = _validate_backup(data)
    return [dict(rule, enabled=False) if rule_type(rule) == RULE_PROGRAM else rule for rule in rules], work_days_only


def is_startup_rule(rule: dict[str, Any]) -> bool:
    """規則是否為「主程式啟動時執行」（非整點時段）。"""
    return rule.get('trigger') == TRIGGER_STARTUP


def is_rule_enabled(rule: dict[str, Any]) -> bool:
    """規則是否啟用；缺少 enabled 欄位的舊規則視為啟用。"""
    return rule.get('enabled', True) is not False


def rule_type(rule: dict[str, Any]) -> str:
    """回傳規則型別；缺少 type 欄位的舊規則視為網頁。"""
    return RULE_PROGRAM if rule.get('type') == RULE_PROGRAM else RULE_URL


def rule_target(rule: dict[str, Any]) -> str:
    """回傳規則的啟動目標（網址或程式路徑），已去除前後空白。"""
    key = 'command' if rule_type(rule) == RULE_PROGRAM else 'url'
    return str(rule.get(key, '')).strip()


def rule_key(rule: dict[str, Any]) -> tuple[str, ...]:
    """回傳規則去重用的識別鍵（同一目標在同一小時只啟動一次）。"""
    if rule_type(rule) == RULE_PROGRAM:
        return (RULE_PROGRAM, rule_target(rule), str(rule.get('arguments', '')).strip())
    return (RULE_URL, rule_target(rule))


def format_weekdays(weekdays: list[int] | None) -> str:
    """將星期清單（0=週一）轉成簡短中文；None 或空清單回傳空字串（沿用全域設定）。"""
    if not weekdays:
        return ''
    days = sorted(set(weekdays))
    if days == list(range(7)):
        return '每天'
    if days == list(range(5)):
        return '週一至週五'
    return '週' + '、'.join(_WEEKDAY_NAMES[d] for d in days if 0 <= d <= 6)


def describe_rule(rule: dict[str, Any]) -> str:
    """產生清單顯示文字，例如 ``09:00–09:00  週一至週五  [程式] python.exe a.py``。"""
    if is_startup_rule(rule):
        parts = ['程式啟動時']
    else:
        start, end = rule.get('start_hour', 0), rule.get('end_hour', 23)
        parts = [f"{start:02d}:00–{end:02d}:00"]
        days = format_weekdays(rule.get('weekdays'))
        if days:
            parts.append(days)
    if rule_type(rule) == RULE_PROGRAM:
        command = rule_target(rule)
        arguments = str(rule.get('arguments', '')).strip()
        name = str(rule.get('name', '')).strip()
        label = f"{name} — " if name else ""
        parts.append(f"[程式] {label}{command} {arguments}".rstrip())
    else:
        parts.append(f"[網頁] {rule_target(rule)}")
    return '  '.join(parts)


def merge_rules(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """將 incoming 併入 existing，略過時段、目標與星期皆相同的重複規則。

    Returns:
        (合併後清單, 實際新增的筆數)
    """
    def identity(rule: dict[str, Any]) -> tuple[Any, ...]:
        return (
            rule_key(rule), is_startup_rule(rule), rule.get('start_hour'), rule.get('end_hour'),
            tuple(sorted(rule.get('weekdays') or [])),
        )

    merged = list(existing)
    seen = {identity(r) for r in merged}
    added = 0
    for rule in incoming:
        if identity(rule) in seen:
            continue
        seen.add(identity(rule))
        merged.append(rule)
        added += 1
    return merged, added
