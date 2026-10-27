"""整點啟動規則的共用定義：規則型別、識別鍵、顯示文字與合併。

規則仍存放於 config 的 ``hourly_web_reminder.url_rules``，舊版只有 ``url`` 的規則視為網頁規則。
"""
from typing import Any

RULE_URL = 'url'
RULE_PROGRAM = 'program'

_WEEKDAY_NAMES = ('一', '二', '三', '四', '五', '六', '日')


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
            rule_key(rule), rule.get('start_hour'), rule.get('end_hour'),
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
