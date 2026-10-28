"""高 DPI 支援：在建立 Tk 視窗前宣告 DPI 感知，並提供像素縮放換算。"""
from __future__ import annotations

import logging
import sys
import tkinter as tk

logger = logging.getLogger(__name__)

_BASE_DPI = 96.0
_MAX_SCALE = 4.0


def enable_dpi_awareness() -> bool:
    """宣告程式為 DPI 感知（僅 Windows），須在建立 ``tk.Tk()`` 之前呼叫。

    未宣告時 Windows 會以點陣圖放大視窗，文字會模糊；原始碼執行與 PyInstaller
    打包後的行為也可能不一致。

    Returns:
        成功設定（或先前已設定）回傳 True；非 Windows 或失敗回傳 False。
    """
    if sys.platform != 'win32':
        return False
    try:
        import ctypes

        try:
            # 1 = PROCESS_SYSTEM_DPI_AWARE；Tk 不處理跨螢幕 DPI 變動，不使用 per-monitor
            result = ctypes.windll.shcore.SetProcessDpiAwareness(1)
            # E_ACCESSDENIED：已由 manifest 或先前呼叫設定過
            return result in (0, -2147024891)
        except (AttributeError, OSError):
            return bool(ctypes.windll.user32.SetProcessDPIAware())
    except Exception as e:
        logger.debug("Enable DPI awareness failed: %s", e)
        return False


def get_scale_factor(root: tk.Misc) -> float:
    """回傳相對 96 DPI 的縮放倍率（僅 Windows；其他平台 Tk 以 points 為單位，回傳 1.0）。"""
    if sys.platform != 'win32':
        return 1.0
    try:
        factor = float(root.winfo_fpixels('1i')) / _BASE_DPI
    except (tk.TclError, ValueError):
        return 1.0
    return min(max(factor, 1.0), _MAX_SCALE)


def scale_px(value: int | float, factor: float) -> int:
    """將 96 DPI 基準的像素值依倍率換算。"""
    return int(round(value * factor))
