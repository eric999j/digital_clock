"""
提醒視窗工具：支援主 UI 執行緒中的非阻塞視窗，以及舊版獨立程序入口。
"""
import logging
import re
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from collections.abc import Callable
from tkinter import messagebox

from ui.theme_utils import (
    BUTTON_BG,
    BUTTON_FG,
    BUTTON_HOVER_BG,
    BUTTON_HOVER_FG,
    BUTTON_PRESSED_BG,
    compute_separator_color,
)

logger = logging.getLogger(__name__)

# 匹配 http/https URL 的正規表達式
_URL_PATTERN = re.compile(r'(https?://[^\s<>\"\']+)')


def _open_url(url: str) -> None:
    """在預設瀏覽器中開啟 URL。"""
    webbrowser.open(url)


def _has_url(message: str) -> bool:
    """檢查訊息中是否包含 URL。"""
    return bool(_URL_PATTERN.search(message))


# Markdown 行內語法模式（順序：*** > ** > __ > * > _ > ` > [](url) > URL）
_INLINE_MD_PATTERN = re.compile(
    r'(?P<bold_italic>\*\*\*[^*\n]+?\*\*\*)'
    r'|(?P<bold>\*\*[^*\n]+?\*\*)'
    r'|(?P<bold_u>__[^_\n]+?__)'
    r'|(?P<italic>\*[^*\n]+?\*)'
    r'|(?P<italic_u>_[^_\n]+?_)'
    r'|(?P<code>`[^\n`]+?`)'
    r'|(?P<link>\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^)\n]+)\))'
    r'|(?P<url>https?://[^\s<>"\' ]+)'
)
_HEADER_RE = re.compile(r'^(#{1,6})\s+(.*)')
_HR_RE = re.compile(r'^[-*_]{3,}\s*$')
_LIST_RE = re.compile(r'^(\s*)([-*+]|\d+\.)\s+(.*)')


def _code_bg_color(bg: str) -> str:
    """依主題亮暗計算 code 區塊背景色。"""
    try:
        r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        adj = 35 if brightness < 128 else -35
        return (f"#{max(0, min(255, r + adj)):02x}"
                f"{max(0, min(255, g + adj)):02x}"
                f"{max(0, min(255, b + adj)):02x}")
    except Exception:
        return '#f0f0f0'


def _configure_md_tags(
    text_widget: tk.Text,
    sys_font: str,
    actual_bg: str,
    actual_fg: str,
    link_color: str,
) -> None:
    """設置 Markdown 渲染所需的所有 tag。"""
    text_widget.tag_configure('bold', font=(sys_font, 11, 'bold'))
    text_widget.tag_configure('italic', font=(sys_font, 11, 'italic'))
    text_widget.tag_configure('bold_italic', font=(sys_font, 11, 'bold italic'))
    text_widget.tag_configure('h1', font=(sys_font, 16, 'bold'))
    text_widget.tag_configure('h2', font=(sys_font, 14, 'bold'))
    text_widget.tag_configure('h3', font=(sys_font, 13, 'bold'))
    text_widget.tag_configure('h4', font=(sys_font, 12, 'bold'))
    text_widget.tag_configure('h5', font=(sys_font, 11, 'bold'))
    text_widget.tag_configure('h6', font=(sys_font, 11, 'bold italic'))
    text_widget.tag_configure(
        'code',
        font=('Courier New', 10),
        background=_code_bg_color(actual_bg),
        foreground=actual_fg,
    )
    text_widget.tag_configure('hr', foreground='gray')


def _insert_inline_md(
    text_widget: tk.Text,
    text: str,
    link_color: str,
) -> None:
    """將含有 Markdown 行內語法的文字插入 Text 元件。"""
    last = 0
    for m in _INLINE_MD_PATTERN.finditer(text):
        if m.start() > last:
            text_widget.insert(tk.END, text[last:m.start()])
        gd = m.lastgroup
        raw = m.group()
        if gd == 'bold_italic':
            text_widget.insert(tk.END, raw[3:-3], 'bold_italic')
        elif gd in ('bold', 'bold_u'):
            text_widget.insert(tk.END, raw[2:-2], 'bold')
        elif gd in ('italic', 'italic_u'):
            text_widget.insert(tk.END, raw[1:-1], 'italic')
        elif gd == 'code':
            text_widget.insert(tk.END, raw[1:-1], 'code')
        elif gd == 'link':
            link_text = m.group('link_text')
            link_url = m.group('link_url')
            tag = f"md_link_{m.start()}"
            text_widget.tag_configure(tag, foreground=link_color, underline=True)
            text_widget.tag_bind(tag, "<Enter>", lambda e, w=text_widget: w.configure(cursor="hand2"))
            text_widget.tag_bind(tag, "<Leave>", lambda e, w=text_widget: w.configure(cursor="arrow"))
            text_widget.tag_bind(tag, "<Button-1>", lambda e, u=link_url: _open_url(u))
            text_widget.insert(tk.END, link_text, tag)
        elif gd == 'url':
            tag = f"url_{m.start()}"
            text_widget.tag_configure(tag, foreground=link_color, underline=True)
            text_widget.tag_bind(tag, "<Enter>", lambda e, w=text_widget: w.configure(cursor="hand2"))
            text_widget.tag_bind(tag, "<Leave>", lambda e, w=text_widget: w.configure(cursor="arrow"))
            text_widget.tag_bind(tag, "<Button-1>", lambda e, u=raw: _open_url(u))
            text_widget.insert(tk.END, raw, tag)
        last = m.end()
    if last < len(text):
        text_widget.insert(tk.END, text[last:])


def _insert_message(
    text_widget: tk.Text,
    message: str,
    link_color: str,
    sys_font: str = "Microsoft JhengHei UI",
    actual_bg: str = "#ffffff",
    actual_fg: str = "#000000",
) -> None:
    """將訊息以 Markdown 格式插入 Text 元件，支援標題、清單、行內格式與超連結。"""
    _configure_md_tags(text_widget, sys_font, actual_bg, actual_fg, link_color)
    lines = message.split('\n')
    for i, line in enumerate(lines):
        if i > 0:
            text_widget.insert(tk.END, '\n')
        header_m = _HEADER_RE.match(line)
        if header_m:
            level = min(len(header_m.group(1)), 6)
            text_widget.insert(tk.END, header_m.group(2), f'h{level}')
            continue
        if _HR_RE.match(line):
            text_widget.insert(tk.END, '─' * 32, 'hr')
            continue
        list_m = _LIST_RE.match(line)
        if list_m:
            indent, marker, content = list_m.group(1), list_m.group(2), list_m.group(3)
            bullet = '•' if not marker[0].isdigit() else f'{marker}'
            text_widget.insert(tk.END, f'{indent}{bullet} ')
            _insert_inline_md(text_widget, content, link_color)
            continue
        _insert_inline_md(text_widget, line, link_color)


def _estimate_display_lines(message: str, chars_per_line: int = 38) -> int:
    """估算訊息在給定字元寬度下的視覺行數（中文字符算 2 單位）。"""
    total = 0
    for line in (message.splitlines() or ['']):
        weight = sum(2 if ord(c) > 127 else 1 for c in line)
        total += max(1, (weight + chars_per_line - 1) // chars_per_line)
    return total


def _position_popup(popup: tk.Toplevel, parent: tk.Misc | None) -> None:
    """智慧定位 popup：優先靠近主視窗、放不下時退回螢幕中央並確保完整可見。"""
    try:
        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()

        target_x: int | None = None
        target_y: int | None = None
        if parent is not None:
            try:
                px = parent.winfo_rootx()
                py = parent.winfo_rooty()
                pw = parent.winfo_width()
                ph = parent.winfo_height()
                if pw > 1 and ph > 1:
                    target_x = px + (pw - w) // 2
                    target_y = py + ph + 12  # 顯示在主視窗下方，避開時鐘本體
                    if target_y + h > sh - 8:
                        target_y = max(8, py - h - 12)  # 空間不足改放在上方
            except tk.TclError:
                target_x = target_y = None

        if target_x is None or target_y is None:
            target_x = (sw - w) // 2
            target_y = (sh - h) // 2

        # clamp 到螢幕內，避免時鐘靠邊時 popup 跑出可視範圍
        target_x = max(8, min(target_x, sw - w - 8))
        target_y = max(8, min(target_y, sh - h - 8))
        popup.geometry(f"+{target_x}+{target_y}")
    except tk.TclError as e:
        logger.debug("Popup positioning failed: %s", e)


def _themed_button(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None],
    bg: str,
    fg: str,
    sys_font: str,
    is_default: bool = False,
) -> tk.Button:
    """建立統一風格的按鈕（灰底黑字，不套用主題），確保任何主題下都清晰可辨。

    ``bg`` / ``fg`` 參數保留以維持既有 API，實際不再使用。
    """
    _ = bg, fg  # signature 相容
    weight = 'bold' if is_default else 'normal'
    return tk.Button(
        parent,
        text=text,
        width=8,
        font=(sys_font, 10, weight),
        relief='flat',
        borderwidth=1,
        cursor='hand2',
        command=command,
        bg=BUTTON_BG,
        fg=BUTTON_FG,
        activebackground=BUTTON_HOVER_BG,
        activeforeground=BUTTON_HOVER_FG,
        highlightthickness=1,
        highlightbackground=BUTTON_PRESSED_BG,
    )


def show_reminder_popup_window(
    parent: tk.Misc,
    message: str,
    theme: dict[str, str] | None = None,
    title: str = "提醒",
    ok_text: str = "關閉",
) -> tk.Toplevel | None:
    """在主 UI 執行緒建立非阻塞提醒視窗。

    Args:
        parent: 主視窗。
        message: 提醒內容。
        theme: 可選的主題顏色。
        title: 視窗標題。
        ok_text: 確認按鈕文字。

    Returns:
        建立成功的 Toplevel；建立失敗時回傳 None。
    """
    # 系統字型
    try:
        sys_font = tkfont.nametofont("TkDefaultFont").actual()['family']
    except Exception:
        sys_font = "Microsoft JhengHei UI"

    bg = theme['bg'] if theme else None
    fg = theme['fg'] if theme else None

    sep_color = compute_separator_color(bg)

    # 標題圖示與超連結顏色（依主題明暗自動選色，取代原本硬編碼白名單）
    from ui.theme_utils import is_dark_theme
    icon_char = {
        "提醒": "🔔", "成功": "✓", "錯誤": "✕", "設定錯誤": "⚠", "警告": "⚠",
        "確認": "?", "確認刪除": "🗑", "番茄鐘": "🍅",
    }.get(title, "🔔")
    link_color = '#74B9FF' if is_dark_theme(bg) else '#0066CC'

    try:
        popup = tk.Toplevel(parent)
        popup.title(title)
        popup.attributes("-topmost", True)
        popup.transient(parent)
        popup.resizable(False, False)
        if bg:
            popup.configure(bg=bg)

        # 外層容器
        outer = tk.Frame(popup, padx=22, pady=18)
        if bg:
            outer.configure(bg=bg)
        outer.pack(fill=tk.BOTH, expand=True)
        actual_bg = outer.cget('bg')
        actual_fg = fg or 'black'

        # ── 標題列（圖示 + 標題文字）──
        header = tk.Frame(outer, bg=actual_bg)
        header.pack(fill=tk.X)
        tk.Label(
            header, text=icon_char,
            font=(sys_font, 15), bg=actual_bg, fg=actual_fg,
        ).pack(side=tk.LEFT)
        tk.Label(
            header, text=f"  {title}",
            font=(sys_font, 12, 'bold'), bg=actual_bg, fg=actual_fg,
        ).pack(side=tk.LEFT)

        # ── 分隔線 ──
        tk.Frame(outer, bg=sep_color, height=1).pack(fill=tk.X, pady=(10, 12))

        # ── 訊息內容 ──
        if message:
            display_lines = min(max(2, _estimate_display_lines(message)), 10)
            text_frame = tk.Frame(outer, bg=actual_bg)
            text_frame.pack(fill=tk.BOTH, expand=True)
            scrollbar = tk.Scrollbar(text_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            text_widget = tk.Text(
                text_frame,
                wrap=tk.WORD,
                width=36,
                height=display_lines,
                font=(sys_font, 11),
                borderwidth=0,
                highlightthickness=0,
                cursor="arrow",
                bg=actual_bg,
                fg=actual_fg,
                yscrollcommand=scrollbar.set,
            )
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=text_widget.yview)
            _insert_message(text_widget, message, link_color, sys_font, actual_bg, actual_fg)
            text_widget.bind("<Key>", lambda e: "break")
            # 允許 Ctrl+C 複製、Ctrl+A 全選（比 <Key> 更具體，優先觸發）
            text_widget.bind("<Control-c>", lambda e: text_widget.event_generate("<<Copy>>") or "break")
            text_widget.bind("<Control-a>", lambda e: (
                text_widget.tag_add(tk.SEL, "1.0", tk.END),
                text_widget.mark_set(tk.INSERT, tk.END),
                "break",
            )[-1])
            text_widget.configure(insertwidth=0)

        # ── 按鈕列 ──
        btn_area = tk.Frame(outer, bg=actual_bg)
        btn_area.pack(fill=tk.X, pady=(14, 0))
        btn = _themed_button(btn_area, ok_text, popup.destroy, actual_bg, actual_fg, sys_font, is_default=True)
        btn.pack(side=tk.RIGHT)
        popup.bind('<Return>', lambda e: popup.destroy())
        popup.bind('<Escape>', lambda e: popup.destroy())

        _position_popup(popup, parent)
        popup.lift()
        return popup
    except tk.TclError as e:
        logger.warning("Unable to create reminder popup: %s", e)
        return None


def show_confirm_popup_window(
    parent: tk.Misc,
    message: str,
    yes_callback: Callable[[], None],
    theme: dict[str, str] | None = None,
    title: str = "確認",
    yes_text: str = "是",
    no_text: str = "否",
) -> tk.Toplevel | None:
    """以主題樣式顯示確認對話框（非阻塞），點擊確認後執行 yes_callback。"""
    try:
        sys_font = tkfont.nametofont("TkDefaultFont").actual()['family']
    except Exception:
        sys_font = "Microsoft JhengHei UI"

    bg = theme['bg'] if theme else None
    fg = theme['fg'] if theme else None
    sep_color = compute_separator_color(bg)

    try:
        popup = tk.Toplevel(parent)
        popup.title(title)
        popup.attributes("-topmost", True)
        popup.transient(parent)
        popup.resizable(False, False)
        popup.grab_set()
        if bg:
            popup.configure(bg=bg)

        outer = tk.Frame(popup, padx=22, pady=18)
        if bg:
            outer.configure(bg=bg)
        outer.pack(fill=tk.BOTH, expand=True)
        actual_bg = outer.cget('bg')
        actual_fg = fg or 'black'

        header = tk.Frame(outer, bg=actual_bg)
        header.pack(fill=tk.X)
        icon = "🗑" if "刪除" in title else "?"
        tk.Label(header, text=icon, font=(sys_font, 15), bg=actual_bg, fg=actual_fg).pack(side=tk.LEFT)
        tk.Label(header, text=f"  {title}", font=(sys_font, 12, 'bold'), bg=actual_bg, fg=actual_fg).pack(side=tk.LEFT)

        tk.Frame(outer, bg=sep_color, height=1).pack(fill=tk.X, pady=(10, 12))

        if message:
            text_widget = tk.Text(
                outer, wrap=tk.WORD, width=36, height=1,
                font=(sys_font, 11), borderwidth=0, highlightthickness=0,
                cursor="arrow", bg=actual_bg, fg=actual_fg,
            )
            text_widget.pack(fill=tk.BOTH, expand=True)
            text_widget.insert(tk.END, message)
            text_widget.configure(height=min(max(1, _estimate_display_lines(message)), 8))
            text_widget.bind("<Key>", lambda e: "break")
            text_widget.configure(insertwidth=0)

        btn_area = tk.Frame(outer, bg=actual_bg)
        btn_area.pack(fill=tk.X, pady=(14, 0))

        def on_yes() -> None:
            popup.destroy()
            yes_callback()

        _themed_button(btn_area, yes_text, on_yes, actual_bg, actual_fg, sys_font, is_default=True).pack(side=tk.RIGHT, padx=(4, 0))
        _themed_button(btn_area, no_text, popup.destroy, actual_bg, actual_fg, sys_font).pack(side=tk.RIGHT)

        popup.bind('<Return>', lambda e: on_yes())
        popup.bind('<Escape>', lambda e: popup.destroy())

        _position_popup(popup, parent)
        popup.lift()
        return popup
    except tk.TclError as e:
        logger.warning("Unable to create confirm popup: %s", e)
        return None


def _show_rich_popup(message: str) -> None:
    """顯示含有可點擊超連結的自訂提醒視窗。"""
    root = tk.Tk()
    root.title("提醒")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    frame = tk.Frame(root, padx=20, pady=15)
    frame.pack(fill=tk.BOTH, expand=True)

    text_widget = tk.Text(frame, wrap=tk.WORD, width=50, height=8,
                          font=("Microsoft JhengHei UI", 11),
                          borderwidth=0, highlightthickness=0,
                          background=frame.cget("background"),
                          cursor="arrow")
    text_widget.pack(fill=tk.BOTH, expand=True)

    # 將訊息拆分為普通文字和 URL
    parts = _URL_PATTERN.split(message)
    for idx, part in enumerate(parts):
        if _URL_PATTERN.fullmatch(part):
            tag_name = f"link_{idx}"
            text_widget.tag_configure(tag_name, foreground="blue", underline=True)
            text_widget.tag_bind(tag_name, "<Enter>",
                                 lambda e, w=text_widget: w.configure(cursor="hand2"))
            text_widget.tag_bind(tag_name, "<Leave>",
                                 lambda e, w=text_widget: w.configure(cursor="arrow"))
            url = part
            text_widget.tag_bind(tag_name, "<Button-1>",
                                 lambda e, u=url: _open_url(u))
            text_widget.insert(tk.END, part, tag_name)
        else:
            text_widget.insert(tk.END, part)

    # 保持唯讀但允許滑鼠點擊 tag 事件
    text_widget.bind("<Key>", lambda e: "break")
    text_widget.configure(insertwidth=0)

    btn = tk.Button(frame, text="確定", width=10, command=root.destroy)
    btn.pack(pady=(10, 0))

    # 置中顯示
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")

    root.lift()
    root.focus_force()
    root.mainloop()


def show_reminder_popup(message):
    """
    Shows a reminder message in a separate Tkinter window instance.
    This function is designed to be the target of a multiprocessing.Process.
    """
    try:
        if _has_url(message):
            _show_rich_popup(message)
        else:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            root.lift()
            root.focus_force()
            messagebox.showinfo("提醒", message, parent=root)
            root.destroy()
    except Exception:
        logger.exception("Error in popup process")
