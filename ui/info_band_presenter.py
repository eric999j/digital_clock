"""時鐘下方資訊列的組合、排版與繪製。"""
import logging
import tkinter.font as tkfont
from datetime import datetime
from typing import TYPE_CHECKING

from services.countdown_service import CountdownService

if TYPE_CHECKING:
    from ui.main_window import DigitalClock

logger = logging.getLogger(__name__)


class InfoBandPresenter:
    """將倒數、番茄鐘、待辦與多時區投影到 Canvas。"""

    def __init__(self, ui: "DigitalClock") -> None:
        self.ui = ui

    def fit_font_size(self, available: int) -> int:
        """回傳資訊列可容納的最大字級。"""
        ui = self.ui
        probe = ui._info_probe_font
        if probe is None:
            probe = ui._info_probe_font = tkfont.Font(root=ui.root, font=ui._info_font)
        family = ui._info_font.cget('family')
        size = ui._info_font_size
        probe.configure(family=family, size=size)
        while (
            size > 8
            and max(probe.measure(line) for line in ui._info_lines) > available
        ):
            size -= 1
            probe.configure(size=size)
        return size

    def band_height(self) -> int:
        """計算目前資訊列需要的高度。"""
        ui = self.ui
        if not ui._info_lines:
            return 0
        return len(ui._info_lines) * ui._info_line_px + ui._px(ui.INFO_BAND_PADDING)

    def compose_lines(self, now: datetime | None = None) -> list[str]:
        """依目前狀態組合資訊列文字。"""
        ui = self.ui
        lines: list[str] = []
        if ui._pomodoro_line:
            lines.append(ui._pomodoro_line)
        countdown = ui.logic.countdown_service
        if countdown.is_active:
            name = f"{countdown.label} " if countdown.label else ""
            remaining = CountdownService.format_remaining(countdown.remaining_seconds())
            paused = " (暫停)" if countdown.is_paused else ""
            lines.append(f"{name}倒數 {remaining}{paused}")

        pending = getattr(ui, '_todo_pending', 0)
        if pending > 0 and ui.config.get('todo', {}).get('show_in_info_bar', True):
            lines.append(f"待辦 {pending} 項")

        time_format = ui.config['appearance'].get('time_format', '24h')
        for zone in ui.logic.get_zone_times(now):
            day_hint = {1: " (+1)", -1: " (-1)"}.get(zone.day_offset, "")
            lines.append(
                f"{zone.label} "
                f"{ui._format_time_str(zone.local_time, time_format)}{day_hint}"
            )
        return lines

    def refresh(self, now: datetime | None = None) -> None:
        """重新計算並更新資訊列。"""
        try:
            self.ui._set_info_lines(self.compose_lines(now))
        except Exception as error:
            logger.warning("Error refreshing info lines: %s", error)

    def set_lines(self, lines: list[str]) -> None:
        """套用資訊列，必要時同步調整時鐘視窗高度。"""
        ui = self.ui
        if lines == ui._info_lines:
            return
        if ui._context_menu_open and len(lines) != len(ui._info_lines):
            return
        old_height = ui._info_band_height()
        ui._info_lines = list(lines)
        if ui._info_band_height() != old_height:
            ui._apply_window_size(
                ui.config['window']['width'],
                ui._base_height + ui._info_band_height(),
            )
            ui.root.update_idletasks()
            ui._last_render_state.clear()
            ui._redraw_background()
            ui._update_display_time()
        ui._render_info_band()

    def render(self) -> None:
        """在 Canvas 上繪製資訊列文字與可點擊 tag。"""
        ui = self.ui
        if ui._info_font is None:
            return
        for item in ui._info_items[len(ui._info_lines):]:
            ui.canvas.delete(item)
        del ui._info_items[len(ui._info_lines):]
        if not ui._info_lines:
            return

        theme = ui._get_current_theme()
        fg_color = theme['fg'] if theme else 'white'
        width = ui.config['window']['width']
        size = ui._fit_info_font_size(max(10, width - 16))
        if int(ui._info_font.cget('size')) != size:
            ui._info_font.configure(size=size)

        top = ui._base_height - 2
        for index, line in enumerate(ui._info_lines):
            y = top + index * ui._info_line_px + ui._info_line_px / 2
            if index < len(ui._info_items):
                item = ui._info_items[index]
                ui.canvas.coords(item, width / 2, y)
                ui.canvas.itemconfig(
                    item,
                    text=line,
                    fill=fg_color,
                    font=ui._info_font,
                )
            else:
                ui._info_items.append(ui.canvas.create_text(
                    width / 2,
                    y,
                    text=line,
                    fill=fg_color,
                    font=ui._info_font,
                    anchor='center',
                ))
            ui.canvas.dtag(ui._info_items[index], 'todo_link')
            if line.startswith('待辦 '):
                ui.canvas.addtag_withtag('todo_link', ui._info_items[index])
        ui.canvas.tag_bind(
            'todo_link',
            '<ButtonRelease-1>',
            ui._on_todo_link_click,
        )
        ui.canvas.tag_bind(
            'todo_link',
            '<Enter>',
            lambda _event: ui.canvas.configure(cursor='hand2'),
        )
        ui.canvas.tag_bind(
            'todo_link',
            '<Leave>',
            lambda _event: ui.canvas.configure(cursor=''),
        )
