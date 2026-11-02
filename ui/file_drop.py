"""檔案拖放支援：透過選用套件 tkinterdnd2 讓 tkinter 元件接收從檔案總管拖入的檔案。"""
import logging
import tkinter as tk
from collections.abc import Callable

logger = logging.getLogger(__name__)


def enable_file_drop(widgets: list[tk.Misc], on_drop: Callable[[list[str]], None]) -> bool:
    """讓指定元件接受檔案拖入。

    tkinterdnd2 未安裝或載入失敗時不影響其他功能，回傳 False（呼叫端仍可用按鈕匯入）。

    Args:
        widgets: 要註冊為放置目標的元件（子元件需各自註冊才會收到事件）
        on_drop: 收到檔案時以路徑清單呼叫

    Returns:
        是否成功啟用拖放。
    """
    if not widgets:
        return False
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD

        TkinterDnD._require(widgets[0])

        def handle_drop(event: tk.Event) -> str:
            on_drop(list(event.widget.tk.splitlist(event.data)))
            return event.action

        for widget in widgets:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>', handle_drop)
    except Exception as e:
        logger.info("檔案拖放功能不可用：%s", e)
        return False
    return True
