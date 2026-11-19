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


def position_popup_outside(
    pointer_x: int,
    pointer_y: int,
    popup_width: int,
    popup_height: int,
    obstacle: Bounds,
    screen: Bounds,
) -> tuple[int, int]:
    """
    在障礙視窗外、可視區域內選擇最靠近指標的彈出選單位置。

    Args:
        pointer_x: 指標螢幕座標 x
        pointer_y: 指標螢幕座標 y
        popup_width: 彈出選單寬度
        popup_height: 彈出選單高度
        obstacle: 時鐘視窗邊界 (left, top, right, bottom)
        screen: 可視螢幕範圍 (left, top, right, bottom)

    Returns:
        彈出選單的左上角座標
    """
    obstacle_left, obstacle_top, obstacle_right, obstacle_bottom = obstacle
    screen_left, screen_top, screen_right, screen_bottom = screen
    width = max(1, popup_width)
    height = max(1, popup_height)
    gap = 1

    candidates = (
        (
            max(screen_left, obstacle_right + gap),
            clamp_position(pointer_x, pointer_y, width, height, screen)[1],
        ),
        (
            min(screen_right - width, obstacle_left - gap - width),
            clamp_position(pointer_x, pointer_y, width, height, screen)[1],
        ),
        (
            clamp_position(pointer_x, pointer_y, width, height, screen)[0],
            max(screen_top, obstacle_bottom + gap),
        ),
        (
            clamp_position(pointer_x, pointer_y, width, height, screen)[0],
            min(screen_bottom - height, obstacle_top - gap - height),
        ),
    )

    def is_valid(position: tuple[int, int]) -> bool:
        x, y = position
        right, bottom = x + width, y + height
        inside_screen = (
            x >= screen_left
            and y >= screen_top
            and right <= screen_right
            and bottom <= screen_bottom
        )
        outside_obstacle = (
            right <= obstacle_left
            or x >= obstacle_right
            or bottom <= obstacle_top
            or y >= obstacle_bottom
        )
        return inside_screen and outside_obstacle

    valid = [position for position in candidates if is_valid(position)]
    if valid:
        return min(
            valid,
            key=lambda position: (
                (position[0] - pointer_x) ** 2
                + (position[1] - pointer_y) ** 2
            ),
        )

    # 螢幕或時鐘尺寸沒有完整無重疊空間時，退回重疊面積最小的位置。
    def overlap_area(position: tuple[int, int]) -> int:
        x, y = position
        overlap_width = max(
            0,
            min(x + width, obstacle_right) - max(x, obstacle_left),
        )
        overlap_height = max(
            0,
            min(y + height, obstacle_bottom) - max(y, obstacle_top),
        )
        return overlap_width * overlap_height

    clamped = [clamp_position(x, y, width, height, screen) for x, y in candidates]
    return min(
        clamped,
        key=lambda position: (
            overlap_area(position),
            (position[0] - pointer_x) ** 2
            + (position[1] - pointer_y) ** 2,
        ),
    )


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
