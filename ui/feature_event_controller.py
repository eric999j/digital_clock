"""DigitalClock 功能事件與視窗協調控制器。"""
import logging
import tkinter as tk
from typing import Any

from core.url_validator import is_safe_url
from services.countdown_service import CountdownService
from ui.window_controller import WindowController

logger = logging.getLogger(__name__)


class FeatureEventController:
    """處理功能服務送入 UI 的事件，保留 DigitalClock 既有方法介面。"""

    def _on_pomodoro_phase_change(self, phase: str, *args) -> None:
        self.update_pomodoro_display(phase, None)

    def _on_pomodoro_tick(self, phase: str, remaining: int, *args) -> None:
        self.update_pomodoro_display(phase, remaining)

    def _on_pomodoro_pause_toggled(self, is_paused: bool, *args) -> None:
        self.update_pomodoro_display(self.logic.pomodoro.phase, None)

    def _on_pomodoro_phase_complete(self, new_phase: str, *args) -> None:
        from ui.popup_utils import show_reminder_popup_window

        phase_map = {
            "FOCUS": "專注",
            "SHORT_BREAK": "短休息",
            "LONG_BREAK": "長休息",
            "IDLE": "就緒",
        }
        phase_text = phase_map.get(new_phase, new_phase)
        theme = self._get_current_theme()
        self.root.after_idle(
            lambda: show_reminder_popup_window(
                self.root,
                f"階段結束，進入 {phase_text}",
                theme,
                title="番茄鐘",
                ok_text="確定",
            )
        )

    def _on_reminder_due(self, reminder: dict[str, Any], *args) -> None:
        from ui.popup_utils import show_reminder_popup_window

        self.config["reminders"] = self.logic.get_config().get("reminders", [])
        display_text = (
            reminder.get("message")
            or reminder.get("title", "")
            or "提醒時間到了"
        )
        reminder_title = reminder.get("title") or "提醒"
        theme = self._get_current_theme()
        popup = show_reminder_popup_window(
            self.root,
            display_text,
            theme,
            title=reminder_title,
            snooze_minutes=self.logic.get_snooze_options(),
            on_snooze=lambda minutes, r=reminder: self.logic.snooze_reminder(
                r, minutes
            ),
        )
        if popup is not None:
            self._reminder_popups.append(popup)
            popup.bind(
                "<Destroy>",
                lambda event, window=popup: self._forget_reminder_popup(window),
                add="+",
            )
            while len(self._reminder_popups) > 5:
                oldest = self._reminder_popups.pop(0)
                if oldest.winfo_exists():
                    oldest.destroy()

    def _forget_reminder_popup(self, popup: tk.Toplevel) -> None:
        """從目前的提醒視窗清單移除已關閉的視窗。"""
        if popup in self._reminder_popups:
            self._reminder_popups.remove(popup)

    def _on_reminder_snoozed(self, *args) -> None:
        """稍後提醒後同步提醒清單並刷新選單。"""
        self.config["reminders"] = self.logic.get_config().get("reminders", [])
        self._update_reminder_menu()

    def _on_countdown_changed(self, *args) -> None:
        """倒數狀態變更時刷新資訊列。"""
        self._refresh_info_lines()

    def _on_countdown_finished(
        self,
        label: str = "",
        total_seconds: int = 0,
        *args,
    ) -> None:
        """倒數結束後響鈴並顯示提醒。"""
        from ui.popup_utils import show_reminder_popup_window

        self._refresh_info_lines()
        try:
            self.root.bell()
        except tk.TclError:
            logger.debug("Bell is not available")
        name = f"「{label}」" if label else ""
        duration = CountdownService.format_remaining(total_seconds)
        theme = self._get_current_theme()
        self.root.after_idle(
            lambda: show_reminder_popup_window(
                self.root,
                f"{name}倒數 {duration} 結束了",
                theme,
                title="倒數計時",
                ok_text="確定",
            )
        )

    def _on_timezones_updated(self, *args) -> None:
        """同步多時區設定並刷新資訊列。"""
        self.config["timezones"] = self.logic.get_config().get("timezones", {})
        self._refresh_info_lines()

    def _on_open_countdown_window(self, *args) -> None:
        """開啟自訂倒數視窗。"""
        self._get_window_controller().open_countdown()

    def _on_screenshot_triggered(self, *args: Any) -> None:
        """截圖時暫時隱藏時鐘。"""
        if self.logic.is_hidden:
            return

        self.logic.is_hidden = True
        self.root.withdraw()
        hide_duration = self.config.get("system", {}).get(
            "hide_duration_ms", 2000
        )
        try:
            duration_ms = max(100, int(hide_duration))
        except (TypeError, ValueError):
            duration_ms = 2000
        self.root.after(duration_ms, self._restore_after_screenshot)

    def _restore_after_screenshot(self) -> None:
        """恢復截圖前隱藏的時鐘。"""
        try:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.logic.is_hidden = False
        except tk.TclError:
            logger.debug(
                "Clock window was already destroyed before screenshot restore"
            )

    def _get_current_theme(self) -> dict[str, str] | None:
        """取得目前套用的主題配色字典。"""
        return self.config["themes"].get(
            self.config["appearance"]["theme"]
        )

    def _show_themed_info(self, message: str) -> None:
        """以目前主題顯示非阻塞通知。"""
        from ui.popup_utils import show_reminder_popup_window

        theme = self._get_current_theme()
        self.root.after_idle(
            lambda: show_reminder_popup_window(
                self.root, message, theme, title="成功", ok_text="確定"
            )
        )

    def _on_reminder_added(self, *args) -> None:
        self.config["reminders"] = self.logic.get_config().get("reminders", [])
        self._show_themed_info("提醒已設定成功！")
        self._update_reminder_menu()

    def _on_reminder_updated(self, *args) -> None:
        self.config["reminders"] = self.logic.get_config().get("reminders", [])
        self._show_themed_info("提醒已更新！")
        self._update_reminder_menu()

    def _on_reminder_deleted(self, *args) -> None:
        self.config["reminders"] = self.logic.get_config().get("reminders", [])
        self._show_themed_info("提醒已刪除。")
        self._update_reminder_menu()

    def _on_hourly_web_updated(self, *args) -> None:
        fresh = self.logic.get_config()
        self.config["hourly_web_reminder"] = fresh.get(
            "hourly_web_reminder", {}
        )
        self.config["reminders"] = fresh.get("reminders", [])
        self.config["vacation_schedules"] = fresh.get(
            "vacation_schedules", []
        )
        self._show_themed_info("整點啟動設定已更新！")

    def _on_hourly_web_pause_toggled(
        self,
        is_paused: bool,
        *args,
    ) -> None:
        self._sync_pause_config()
        label = "啟動" if is_paused else "暫停"
        try:
            self.hourly_web_menu.entryconfigure(1, label=label)
        except Exception as e:
            logger.warning("Error updating hourly web menu: %s", e)

    def _on_reminder_pause_toggled(
        self,
        is_paused: bool,
        *args,
    ) -> None:
        self._sync_pause_config()
        label = "啟動" if is_paused else "暫停"
        try:
            self.reminder_menu.entryconfigure(1, label=label)
        except Exception as e:
            logger.warning("Error updating reminder menu: %s", e)

    def _sync_pause_config(self) -> None:
        """同步服務直接儲存的暫停狀態。"""
        fresh = self.logic.get_config()
        for key in (
            "pause_sources",
            "vacation_sources",
            "reminder_paused",
            "on_vacation",
            "on_vacation_source",
            "vacation_previous_state",
        ):
            if key in fresh:
                self.config[key] = fresh[key]
            else:
                self.config.pop(key, None)
        self.config["hourly_web_reminder"] = fresh.get(
            "hourly_web_reminder", {}
        )

    def _on_vacation_toggled(
        self,
        is_vacation: bool,
        *args,
    ) -> None:
        fresh = self.logic.get_config()
        for key in (
            "on_vacation",
            "on_vacation_source",
            "vacation_previous_state",
            "reminder_paused",
            "hourly_web_reminder",
        ):
            if key in fresh:
                self.config[key] = fresh[key]
            else:
                self.config.pop(key, None)
        self._update_vacation_menu()

    def _on_vacation_schedule_added(self, *args) -> None:
        self._show_themed_info("勿擾排程已新增！")
        self._update_vacation_menu()

    def _on_vacation_schedule_deleted(self, *args) -> None:
        self._show_themed_info("勿擾排程已刪除。")
        self._update_vacation_menu()

    def _on_vacation_schedule_updated(self, *args) -> None:
        self._update_vacation_menu()

    def _on_open_reminder_window(
        self,
        reminder_to_edit: dict[str, Any] | None = None,
        *args,
    ) -> None:
        """開啟設定提醒的視窗。"""
        self._get_window_controller().open_reminder(reminder_to_edit)

    def _on_open_hourly_web_window(self, *args) -> None:
        """開啟整點啟動設定視窗。"""
        self._get_window_controller().open_hourly()

    def _live_todo_window(self) -> tk.Toplevel | None:
        """回傳仍存在的待辦視窗，否則 None。"""
        window = getattr(self, "_todo_window", None)
        try:
            return (
                window
                if window is not None and window.winfo_exists()
                else None
            )
        except tk.TclError:
            return None

    def _live_notification_window(self) -> tk.Toplevel | None:
        """回傳仍存在的通知中心視窗，否則 None。"""
        window = getattr(self, "_notification_window", None)
        try:
            return (
                window
                if window is not None and window.winfo_exists()
                else None
            )
        except tk.TclError:
            return None

    def _on_open_notification_center(self, *args) -> None:
        """開啟通知中心；已開啟時只帶到前景。"""
        self._get_window_controller().open_notification_center()

    def _on_notifications_changed(self, *args) -> None:
        """通知清單變動時同步開啟中的視窗。"""
        window = self._live_notification_window()
        if window is not None:
            window.refresh()

    def _on_open_todo_window(self, *args) -> None:
        """開啟待辦事項視窗；已開啟時只帶到前景。"""
        self._get_window_controller().open_todo()

    def _save_todo_window_geometry(self, size: str) -> None:
        """待辦視窗關閉時記住視窗大小。"""
        self.config["ui_behavior"]["todo_window_geometry"] = size
        self._schedule_current_config_save()

    def _on_todo_updated(
        self,
        pending: int | None = None,
        *args,
    ) -> None:
        """待辦變更後更新資訊列。"""
        self._todo_pending = (
            pending
            if isinstance(pending, int)
            else self.logic.todo_service.pending_count()
        )
        self._refresh_info_lines()

    def _on_todo_remind_toggled(self, enabled: bool, *args) -> None:
        """同步待辦提醒開關。"""
        self.config.setdefault("todo", {})["remind_enabled"] = bool(enabled)

    def _on_todo_due(
        self,
        items: list[dict[str, Any]],
        *args,
    ) -> None:
        """顯示今日到期與逾期待辦提醒。"""
        from ui.popup_utils import show_reminder_popup_window

        show_reminder_popup_window(
            self.root,
            self._format_todo_due_message(items),
            self._get_current_theme(),
            title="待辦提醒",
            ok_text="確定",
        )

    @staticmethod
    def _format_todo_due_message(
        items: list[dict[str, Any]],
        limit: int = 15,
    ) -> str:
        """將到期待辦組成 Markdown 訊息。"""
        plain = str.maketrans(
            {
                "*": "＊",
                "_": "＿",
                "`": "｀",
                "[": "［",
                "]": "］",
            }
        )

        def line(item: dict[str, Any]) -> str:
            text = str(item.get("text", "")).translate(plain)
            if is_safe_url(item.get("link")):
                text = f"[{text}]({item['link']})"
            return f"- {text}（截止 {item.get('due_date', '')}）"

        sections: list[str] = []
        shown = 0
        for status, title in (
            ("overdue", "逾期"),
            ("today", "今日到期"),
        ):
            group = [i for i in items if i.get("status") == status]
            if not group:
                continue
            lines = [f"**{title}（{len(group)} 項）**"]
            for item in group:
                if shown >= limit:
                    break
                lines.append(line(item))
                shown += 1
            sections.append("\n".join(lines))
        if len(items) > shown:
            sections.append(f"…還有 {len(items) - shown} 項，請到待辦視窗查看")
        return "\n\n".join(sections)

    def _on_open_vacation_schedule_window(
        self,
        schedule_to_edit: dict[str, Any] | None = None,
        *args,
    ) -> None:
        """開啟新增或編輯休假排程視窗。"""
        self._get_window_controller().open_vacation_schedule(schedule_to_edit)

    def _on_open_calendar_sync_window(self, *args) -> None:
        """開啟行事曆同步設定視窗。"""
        self._get_window_controller().open_calendar_sync()

    def _get_window_controller(self) -> WindowController:
        """取得功能視窗控制器，支援未完整初始化的測試替身。"""
        controller = getattr(self, "_window_controller", None)
        if controller is None:
            controller = WindowController(self)
            self._window_controller = controller
        return controller

    def _save_calendar_sync_settings(
        self,
        enabled: bool,
        ics_url: str,
        refresh_minutes: int,
        lead_minutes: int,
        show_in_meeting: bool = True,
    ) -> None:
        """儲存行事曆設定，並只同步該區塊。"""
        self.logic.update_calendar_sync_settings(
            enabled,
            ics_url,
            refresh_minutes,
            lead_minutes,
            show_in_meeting,
        )
        self.config["calendar_sync"] = self.logic.get_config().get(
            "calendar_sync", {}
        )

    def _show_calendar_popup(self, message: str, title: str) -> None:
        from ui.popup_utils import show_reminder_popup_window

        theme = self._get_current_theme()

        def show() -> None:
            self._calendar_popup_after_id = None
            self._calendar_popup = show_reminder_popup_window(
                self.root, message, theme, title=title, ok_text="確定"
            )

        self._calendar_popup_after_id = self.root.after_idle(show)

    def _on_calendar_event_upcoming(
        self,
        summary: str = "",
        minutes: int = 0,
        *args,
    ) -> None:
        name = f"「{summary}」" if summary else "行事曆事件"
        self._show_calendar_popup(
            f"{name}約 {minutes} 分鐘後開始，將自動進入勿擾模式",
            "行事曆預告",
        )

    def _on_calendar_event_started(
        self,
        summary: str = "",
        *args,
    ) -> None:
        self._close_calendar_popup()
        if not self.config.get("calendar_sync", {}).get(
            "show_in_meeting", True
        ):
            return
        self._show_calendar_popup("會議中...", "行事曆")

    def _on_calendar_event_ended(self, *args) -> None:
        self._close_calendar_popup()

    def _close_calendar_popup(self) -> None:
        """關閉仍存在的行事曆預告或會議視窗。"""
        after_id = getattr(self, "_calendar_popup_after_id", None)
        self._calendar_popup_after_id = None
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                logger.debug("Calendar popup scheduling already completed")

        popup = getattr(self, "_calendar_popup", None)
        self._calendar_popup = None
        try:
            if popup is not None and popup.winfo_exists():
                popup.destroy()
        except tk.TclError:
            logger.debug("Calendar popup already destroyed")

    def _open_vacation_schedule_editor(
        self,
        schedule: dict[str, Any],
    ) -> None:
        """排程選單關閉後開啟編輯視窗。"""
        self.root.after_idle(
            lambda: self._on_open_vacation_schedule_window(schedule)
        )
