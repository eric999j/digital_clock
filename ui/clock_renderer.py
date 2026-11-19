"""Canvas 時鐘繪製器，與視窗控制及事件處理分離。"""
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ui.main_window import DigitalClock

logger = logging.getLogger(__name__)


class ClockRenderer:
    """擁有時鐘 Canvas item 的建立、佈局與繪製。"""

    def __init__(self, ui: "DigitalClock") -> None:
        self.ui = ui

    def redraw_background(self) -> None:
        """依目前 Canvas 尺寸更新背景。"""
        ui = self.ui
        if ui._background_item is None:
            return
        width = max(1, ui.canvas.winfo_width())
        height = max(1, ui.canvas.winfo_height())
        radius = min(ui._px(ui.CORNER_RADIUS), width // 2, height // 2)
        ui.canvas.coords(
            ui._background_item,
            *self.rounded_rect_points(0, 0, width, height, radius),
        )

    @staticmethod
    def rounded_rect_points(
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
    ) -> list[int]:
        """產生圓角矩形 Canvas 多邊形座標。"""
        return [
            x1 + radius, y1, x1 + radius, y1, x2 - radius, y1, x2 - radius, y1,
            x2, y1, x2, y1 + radius, x2, y1 + radius, x2, y2 - radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x2 - radius, y2,
            x1 + radius, y2, x1 + radius, y2, x1, y2, x1, y2 - radius,
            x1, y2 - radius, x1, y1 + radius, x1, y1 + radius, x1, y1,
        ]

    def draw_rounded_rect(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        **kwargs: Any,
    ) -> int:
        """在 Canvas 建立圓角背景。"""
        return self.ui.canvas.create_polygon(
            *self.rounded_rect_points(x1, y1, x2, y2, radius),
            smooth=True,
            **kwargs,
        )

    def render_clock(
        self,
        text1: str,
        text2: str | None = None,
        progress: float = 0.0,
    ) -> None:
        """只更新有變化的 Canvas 文字 item。"""
        ui = self.ui
        text_len = len(text1)
        if len(ui._canvas_items) != text_len:
            for item in ui._canvas_items:
                try:
                    ui.canvas.delete(item['main'], item['sub'])
                except Exception as error:
                    logger.debug("Canvas item delete failed: %s", error)
            ui._canvas_items.clear()
            for _ in range(text_len):
                ui._canvas_items.append({
                    'main': ui.canvas.create_text(0, 0, anchor='center'),
                    'sub': ui.canvas.create_text(0, 0, anchor='center'),
                    'last_main_char': '',
                    'last_sub_char': '',
                })
            ui._last_render_state.clear()

        theme = ui.config['themes'].get(ui.config['appearance']['theme'])
        fg_color = theme['fg'] if theme else 'white'
        font_family = ui.config['appearance']['font_family']
        font_size = ui.config['appearance']['font_size']
        info_band_h = ui._info_band_height()
        layout_key = (
            f"{text_len}_{font_family}_{font_size}_{ui.root.winfo_width()}_"
            f"{ui.root.winfo_height()}_{info_band_h}"
        )
        layout_changed = ui._last_render_state.get('layout_key') != layout_key
        if layout_changed:
            try:
                ui._anim_font.configure(family=font_family, size=font_size)
            except Exception as error:
                logger.debug("Animation font configure failed: %s", error)
            total_width = ui._anim_font.measure(text1)
            ui._render_params = {
                'start_x': (ui.canvas.winfo_width() - total_width) / 2,
                'center_y': ui._base_height / 2,
                'line_height': font_size * 1.1,
                'font': (font_family, font_size),
            }
            ui._last_render_state['layout_key'] = layout_key

        params = ui._render_params
        current_x = params['start_x']
        was_animating = ui._last_render_state.get('was_animating', False)
        is_animating = text2 is not None
        if (
            not is_animating
            and not was_animating
            and not layout_changed
            and ui._last_render_state.get('last_static_text') == text1
            and ui._last_render_state.get('last_fg_color') == fg_color
        ):
            return

        for index in range(text_len):
            char1 = text1[index]
            char2 = text2[index] if text2 else None
            item = ui._canvas_items[index]
            char_width = ui._measure_char_width(char1, font_family, font_size)
            center_x = current_x + char_width / 2
            if char2 is not None and char1 != char2:
                y_offset = progress * params['line_height']
                ui.canvas.coords(item['main'], center_x, params['center_y'] - y_offset)
                ui.canvas.coords(
                    item['sub'],
                    center_x,
                    params['center_y'] + params['line_height'] - y_offset,
                )
                ui.canvas.itemconfig(item['sub'], state='normal')
                if item['last_main_char'] != char1:
                    ui.canvas.itemconfig(
                        item['main'], text=char1, fill=fg_color, font=params['font'],
                    )
                    item['last_main_char'] = char1
                if item['last_sub_char'] != char2:
                    ui.canvas.itemconfig(
                        item['sub'], text=char2, fill=fg_color, font=params['font'],
                    )
                    item['last_sub_char'] = char2
            elif (
                layout_changed
                or ui._last_render_state.get(f'static_{index}') != char1
                or was_animating
            ):
                ui.canvas.coords(item['main'], center_x, params['center_y'])
                ui.canvas.itemconfig(
                    item['main'],
                    text=char1,
                    fill=fg_color,
                    font=params['font'],
                    state='normal',
                )
                ui.canvas.itemconfig(item['sub'], state='hidden')
                item['last_main_char'] = char1
                ui._last_render_state[f'static_{index}'] = char1
            current_x += char_width

        ui._last_render_state['was_animating'] = is_animating
        if is_animating:
            ui._last_render_state['last_static_text'] = None
        else:
            ui._last_render_state['last_static_text'] = text1
            ui._last_render_state['last_fg_color'] = fg_color

    def measure_char_width(
        self,
        char: str,
        font_family: str,
        font_size: int,
    ) -> int:
        """使用 renderer 所屬視窗的字寬快取。"""
        ui = self.ui
        cache_key = (font_family, font_size, char)
        cached = ui._char_width_cache.get(cache_key)
        if cached is not None:
            return cached
        width = ui._anim_font.measure(char)
        if len(ui._char_width_cache) >= ui._char_width_cache_limit:
            ui._char_width_cache.clear()
        ui._char_width_cache[cache_key] = width
        return width
