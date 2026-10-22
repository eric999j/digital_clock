"""事件常數定義，統一管理所有事件名稱。"""


class Events:
    """事件名稱常數類別。"""

    # Pomodoro 相關事件
    POMODORO_PHASE_CHANGE = 'pomodoro_phase_change'
    POMODORO_TICK = 'pomodoro_tick'
    POMODORO_PHASE_COMPLETE = 'pomodoro_phase_complete'

    # 提醒相關事件
    REMINDER_DUE = 'reminder_due'
    REMINDER_ADDED = 'reminder_added'
    REMINDER_DELETED = 'reminder_deleted'
    REMINDER_UPDATED = 'reminder_updated'
    REMINDER_PAUSE_TOGGLED = 'reminder_pause_toggled'
    REMINDER_SNOOZED = 'reminder_snoozed'

    # 倒數計時器事件
    COUNTDOWN_STARTED = 'countdown_started'
    COUNTDOWN_TICK = 'countdown_tick'
    COUNTDOWN_PAUSE_TOGGLED = 'countdown_pause_toggled'
    COUNTDOWN_FINISHED = 'countdown_finished'
    COUNTDOWN_CANCELLED = 'countdown_cancelled'

    # 多時區顯示事件
    TIMEZONES_UPDATED = 'timezones_updated'

    # 整點網頁提醒事件
    HOURLY_WEB_DUE = 'hourly_web_due'
    HOURLY_WEB_UPDATED = 'hourly_web_updated'
    HOURLY_WEB_PAUSE_TOGGLED = 'hourly_web_pause_toggled'

    # 休假模式事件
    VACATION_TOGGLED = 'vacation_toggled'

    # 休假排程事件
    VACATION_SCHEDULE_ADDED = 'vacation_schedule_added'
    VACATION_SCHEDULE_DELETED = 'vacation_schedule_deleted'
    VACATION_SCHEDULE_UPDATED = 'vacation_schedule_updated'

    # UI 開窗請求（由 ClockLogic 發出，UI Observer 處理）
    OPEN_REMINDER_WINDOW = 'open_reminder_window'
    OPEN_HOURLY_WEB_WINDOW = 'open_hourly_web_window'
    OPEN_VACATION_SCHEDULE_WINDOW = 'open_vacation_schedule_window'
    OPEN_COUNTDOWN_WINDOW = 'open_countdown_window'

    # 系統快捷鍵事件
    SCREENSHOT_TRIGGERED = 'screenshot_triggered'
