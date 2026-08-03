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

logger = logging.getLogger(__name__)

# 匹配 http/https URL 的正規表達式
_URL_PATTERN = re.compile(r'(https?://[^\s<>\"\']+)')


def _open_url(url: str) -> None:
    """在預設瀏覽器中開啟 URL。"""
    webbrowser.open(url)


def _has_url(message: str) -> bool:
    """檢查訊息中是否包含 URL。"""
    return bool(_URL_PATTERN.search(message))


def _insert_message(text_widget: tk.Text, message: str, link_color: str) -> None:
    """將一般文字與 URL 插入文字元件。"""
    parts = _URL_PATTERN.split(message)
    for idx, part in enumerate(parts):
        if _URL_PATTERN.fullmatch(part):
            tag_name = f"link_{idx}"
            text_widget.tag_configure(tag_name, foreground=link_color, underline=True)
            text_widget.tag_bind(
                tag_name,
                "<Enter>",
                lambda e, w=text_widget: w.configure(cursor="hand2"),
            )
            text_widget.tag_bind(
                tag_name,
                "<Leave>",
                lambda e, w=text_widget: w.configure(cursor="arrow"),
            )
            text_widget.tag_bind(tag_name, "<Button-1>", lambda e, u=part: _open_url(u))
            text_widget.insert(tk.END, part, tag_name)
        else:
            text_widget.insert(tk.END, part)


def _estimate_display_lines(message: str, chars_per_line: int = 38) -> int:
    """估算訊息在給定字元寬度下的視覺行數（中文字符算 2 單位）。"""
    total = 0
    for line in (message.splitlines() or ['']):
        weight = sum(2 if ord(c) > 127 else 1 for c in line)
        total += max(1, (weight + chars_per_line - 1) // chars_per_line)
    return total


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

    # 分隔線顏色（依背景亮暗微調）
    sep_color = "#cccccc"
    if bg:
        try:
            r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            adj = 45
            if brightness < 128:
                sep_color = f"#{min(255,r+adj):02x}{min(255,g+adj):02x}{min(255,b+adj):02x}"
            else:
                sep_color = f"#{max(0,r-adj):02x}{max(0,g-adj):02x}{max(0,b-adj):02x}"
        except Exception:
            pass

    # 標題圖示與超連結顏色
    icon_char = {"提醒": "🔔", "成功": "✓", "錯誤": "✕", "設定錯誤": "⚠", "警告": "⚠"}.get(title, "ℹ")
    dark_bgs = {'#1e3a5f', '#2c3e50', '#1c1c1c', '#3a1a08', '#2d1b10', '#6b4226'}
    link_color = '#74B9FF' if (bg and bg.lower() in dark_bgs) else '#0066CC'

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
            text_widget = tk.Text(
                outer,
                wrap=tk.WORD,
                width=36,
                height=1,
                font=(sys_font, 11),
                borderwidth=0,
                highlightthickness=0,
                cursor="arrow",
                bg=actual_bg,
                fg=actual_fg,
            )
            text_widget.pack(fill=tk.BOTH, expand=True)
            _insert_message(text_widget, message, link_color)
            text_widget.configure(height=min(max(1, _estimate_display_lines(message)), 6))
            text_widget.bind("<Key>", lambda e: "break")
            text_widget.configure(insertwidth=0)

        # ── 按鈕列 ──
        btn_area = tk.Frame(outer, bg=actual_bg)
        btn_area.pack(fill=tk.X, pady=(14, 0))
        btn = tk.Button(
            btn_area,
            text=ok_text,
            width=8,
            font=(sys_font, 10),
            relief='groove',
            cursor='hand2',
            command=popup.destroy,
            bg=actual_bg,
            fg=actual_fg,
            activebackground=actual_fg,
            activeforeground=actual_bg,
        )
        btn.pack(side=tk.RIGHT)
        popup.bind('<Return>', lambda e: popup.destroy())

        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        popup.geometry(f"+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}")
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
    sep_color = "#cccccc"
    if bg:
        try:
            r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            adj = 45
            if brightness < 128:
                sep_color = f"#{min(255,r+adj):02x}{min(255,g+adj):02x}{min(255,b+adj):02x}"
            else:
                sep_color = f"#{max(0,r-adj):02x}{max(0,g-adj):02x}{max(0,b-adj):02x}"
        except Exception:
            pass

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
        tk.Label(header, text="?", font=(sys_font, 15), bg=actual_bg, fg=actual_fg).pack(side=tk.LEFT)
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

        tk.Button(
            btn_area, text=yes_text, width=8,
            font=(sys_font, 10), relief='groove', cursor='hand2',
            command=on_yes,
            bg=actual_bg, fg=actual_fg,
            activebackground=actual_fg, activeforeground=actual_bg,
        ).pack(side=tk.RIGHT, padx=(4, 0))
        tk.Button(
            btn_area, text=no_text, width=8,
            font=(sys_font, 10), relief='groove', cursor='hand2',
            command=popup.destroy,
            bg=actual_bg, fg=actual_fg,
            activebackground=actual_fg, activeforeground=actual_bg,
        ).pack(side=tk.RIGHT)

        popup.bind('<Return>', lambda e: on_yes())
        popup.bind('<Escape>', lambda e: popup.destroy())

        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        popup.geometry(f"+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}")
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
