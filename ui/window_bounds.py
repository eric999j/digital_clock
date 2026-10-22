"""視窗邊界工具：計算可視區域並將視窗位置限制在其中。"""
import ctypes
import logging
import sys
import tkinter as tk

logger = logging.getLogger(__name__)

# (left, top, right, bottom)
Bounds = tuple[int, int, int, int]


def clamp_position(x: int, y: int, width: int, height: int, bounds: Bounds) -> tuple[int, int]:
    """
    將視窗左上角座標限制在邊界內，使整個視窗都在可視範圍。

    視窗比邊界大時以左/上緣對齊，確保時鐘仍可見。

    Args:
        x: 視窗左上角 x
        y: 視窗左上角 y
        width: 視窗寬度
        height: 視窗高度
        bounds: 可視範圍 (left, top, right, bottom)

    Returns:
        限制後的 (x, y)
    """
    left, top, right, bottom = bounds
    max_x = max(left, right - width)
    max_y = max(top, bottom - height)
    return min(max(x, left), max_x), min(max(y, top), max_y)


def get_screen_bounds(root: tk.Misc) -> Bounds:
    """
    取得可視區域；Windows 上涵蓋多螢幕的虛擬桌面，其餘平台使用主螢幕。

    Args:
        root: 任一 tkinter 元件，用於查詢主螢幕尺寸

    Returns:
        (left, top, right, bottom)
    """
    if sys.platform == "win32":
        try:
            get_metric = ctypes.windll.user32.GetSystemMetrics
            # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN
            left, top, width, height = (get_metric(i) for i in (76, 77, 78, 79))
            if width > 0 and height > 0:
                return left, top, left + width, top + height
        except (AttributeError, OSError) as e:
            logger.debug("Virtual screen query failed: %s", e)
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
