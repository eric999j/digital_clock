"""UI 主題共用工具：色彩計算、ttk 樣式套用、統一錯誤 popup。

集中三個設定視窗（reminder / vacation / hourly_web）之前重複的樣式與錯誤處理邏輯，
避免各視窗一份幾乎相同的實作。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


_DEFAULT_BG = '#F0F0F0'
_DEFAULT_FG = '#000000'


def compute_brightness(color: str | None) -> float | None:
    """回傳 #RRGGBB 顏色的亮度（0–255）；解析失敗回傳 None。"""
    if not color or not color.startswith('#') or len(color) < 7:
        return None
    try:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
    except ValueError:
        return None
    return (r * 299 + g * 587 + b * 114) / 1000


def is_dark_theme(bg: str | None) -> bool:
    """依背景色亮度判斷是否為暗色主題（<128 視為暗）。"""
    brightness = compute_brightness(bg)
    if brightness is None:
        return False
    return brightness < 128


def _shift_channel(value: int, delta: int) -> int:
    return max(0, min(255, value + delta))


def shift_color(color: str | None, delta: int) -> str:
    """將 #RRGGBB 各通道加上 delta（可正可負），回傳新色；解析失敗回傳原字串。"""
    if not color or not color.startswith('#') or len(color) < 7:
        return color or _DEFAULT_BG
    try:
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    except ValueError:
        return color
    return (
        f"#{_shift_channel(r, delta):02x}"
        f"{_shift_channel(g, delta):02x}"
        f"{_shift_channel(b, delta):02x}"
    )


def compute_separator_color(bg: str | None) -> str:
    """依主題背景亮暗計算細分隔線顏色（暗色略亮、亮色略暗）。"""
    brightness = compute_brightness(bg)
    if brightness is None:
        return '#cccccc'
    return shift_color(bg, 45 if brightness < 128 else -45)


# 按鈕不套用主題，使用系統中性色系，確保任何主題下按鈕文字都清晰可辨識。
BUTTON_BG = '#F0F0F0'
BUTTON_FG = '#000000'
BUTTON_HOVER_BG = '#D9D9D9'
BUTTON_HOVER_FG = '#000000'
BUTTON_PRESSED_BG = '#BFBFBF'


def button_palette() -> dict[str, str]:
    """回傳按鈕統一色彩配置（非主題化，灰底黑字）。"""
    return {
        'bg': BUTTON_BG,
        'fg': BUTTON_FG,
        'hover_bg': BUTTON_HOVER_BG,
        'hover_fg': BUTTON_HOVER_FG,
        'pressed_bg': BUTTON_PRESSED_BG,
    }


def apply_themed_ttk_style(prefix: str, theme: dict[str, str] | None) -> None:
    """建立一組帶前綴的 ttk 樣式，讓所有設定視窗共享一致外觀。

    Args:
        prefix: 樣式名稱前綴（例如 ``'Reminder'``, ``'Vacation'``, ``'HourlyWeb'``）。
        theme: ``{'bg': ..., 'fg': ...}``；若為 None 使用預設淺色配色。
    """
    style = ttk.Style()
    bg = (theme or {}).get('bg') or _DEFAULT_BG
    fg = (theme or {}).get('fg') or _DEFAULT_FG

    style.configure(f'{prefix}.TFrame', background=bg)
    style.configure(f'{prefix}.TLabelframe', background=bg, foreground=fg)
    style.configure(f'{prefix}.TLabelframe.Label', background=bg, foreground=fg)
    style.configure(f'{prefix}.TLabel', background=bg, foreground=fg)
    style.configure(f'{prefix}.TCheckbutton', background=bg, foreground=fg)
    style.configure(f'{prefix}.TCombobox', fieldbackground='white', foreground='black')
    style.configure(f'{prefix}.TEntry', fieldbackground='white', foreground='black')

    # 按鈕維持系統中性色（灰底黑字），不套用主題，避免任何主題下文字對比不足
    style.configure(f'{prefix}.TButton', background=BUTTON_BG, foreground=BUTTON_FG, borderwidth=1)
    style.map(
        f'{prefix}.TButton',
        relief=[('pressed', 'sunken'), ('!pressed', 'raised')],
        background=[('active', BUTTON_HOVER_BG), ('pressed', BUTTON_PRESSED_BG)],
        foreground=[('active', BUTTON_HOVER_FG), ('pressed', BUTTON_FG)],
    )


def themed_error(
    parent: tk.Misc,
    message: str,
    theme: dict[str, str] | None = None,
    title: str = "錯誤",
    ok_text: str = "確定",
) -> tk.Toplevel | None:
    """統一的主題化錯誤/警告 popup，取代散落各處的 messagebox.showerror。"""
    from ui.popup_utils import show_reminder_popup_window
    return show_reminder_popup_window(parent, message, theme, title=title, ok_text=ok_text)


def themed_info(
    parent: tk.Misc,
    message: str,
    theme: dict[str, str] | None = None,
    title: str = "提醒",
    ok_text: str = "關閉",
) -> tk.Toplevel | None:
    """統一的主題化資訊 popup。"""
    from ui.popup_utils import show_reminder_popup_window
    return show_reminder_popup_window(parent, message, theme, title=title, ok_text=ok_text)


def themed_confirm(
    parent: tk.Misc,
    message: str,
    yes_callback: 'Callable[[], None]',
    theme: dict[str, str] | None = None,
    title: str = "確認",
    yes_text: str = "是",
    no_text: str = "否",
) -> tk.Toplevel | None:
    """統一的主題化確認 popup。"""
    from ui.popup_utils import show_confirm_popup_window
    return show_confirm_popup_window(
        parent, message, yes_callback, theme,
        title=title, yes_text=yes_text, no_text=no_text,
    )
