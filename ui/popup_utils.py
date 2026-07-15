"""
提醒視窗工具：支援主 UI 執行緒中的非阻塞視窗，以及舊版獨立程序入口。
"""
import logging
import re
import tkinter as tk
import webbrowser
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


def show_reminder_popup_window(
    parent: tk.Misc,
    message: str,
    theme: dict[str, str] | None = None,
) -> tk.Toplevel | None:
    """在主 UI 執行緒建立非阻塞提醒視窗。

    Args:
        parent: 主視窗。
        message: 提醒內容。
        theme: 可選的主題顏色。

    Returns:
        建立成功的 Toplevel；建立失敗時回傳 None。
    """
    colors = theme or {'bg': '#F0F0F0', 'fg': '#000000'}
    try:
        popup = tk.Toplevel(parent)
        popup.title("提醒")
        popup.attributes("-topmost", True)
        popup.transient(parent)
        popup.resizable(False, False)
        popup.configure(bg=colors['bg'])

        frame = tk.Frame(popup, padx=18, pady=14, bg=colors['bg'])
        frame.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(
            frame,
            wrap=tk.WORD,
            width=50,
            height=8,
            font=("Microsoft JhengHei UI", 11),
            borderwidth=0,
            highlightthickness=0,
            background=colors['bg'],
            foreground=colors['fg'],
            cursor="arrow",
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        link_color = '#74B9FF' if colors['bg'].lower() in {'#1e3a5f', '#2c3e50', '#1c1c1c', '#3a1a08', '#2d1b10', '#6b4226'} else '#0000EE'
        _insert_message(text_widget, message, link_color)
        text_widget.bind("<Key>", lambda e: "break")
        text_widget.configure(insertwidth=0)

        close_button = tk.Button(
            frame,
            text="關閉",
            width=10,
            command=popup.destroy,
            bg=colors['bg'],
            fg=colors['fg'],
            activebackground=colors['fg'],
            activeforeground=colors['bg'],
        )
        close_button.pack(pady=(10, 0))

        parent.update_idletasks()
        popup.update_idletasks()
        width = popup.winfo_width()
        height = popup.winfo_height()
        x = max(0, parent.winfo_x() + parent.winfo_width() - width)
        y = parent.winfo_y() - height - 8
        if y < 0:
            y = parent.winfo_y() + parent.winfo_height() + 8
        popup.geometry(f"+{x}+{max(0, y)}")
        popup.lift()
        return popup
    except tk.TclError as e:
        logger.warning("Unable to create reminder popup: %s", e)
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
