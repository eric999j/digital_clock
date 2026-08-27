"""休假排程設定視窗。"""
import tkinter as tk
from collections.abc import Callable
from datetime import date, datetime, timedelta
from tkinter import ttk

from ui.theme_utils import apply_themed_ttk_style, themed_error


class VacationScheduleWindow(tk.Toplevel):
    """新增休假排程的彈出視窗。"""

    def __init__(
        self,
        parent: tk.Tk,
        callback: Callable[[str, str, str], None],
        theme: dict[str, str] | None = None,
        geometry: str = "360x260",
    ) -> None:
        """
        初始化休假排程視窗。

        Args:
            parent: 父視窗
            callback: 新增排程的回調函數 `(start_iso, end_iso, note)`
            theme: 主題配色
            geometry: 視窗幾何設定
        """
        super().__init__(parent)
        self.callback = callback
        self.theme = theme or {'bg': '#F0F0F0', 'fg': '#000000'}
        self.transient(parent)
        self.title("新增休假排程")
        self.geometry(geometry)
        self.resizable(False, False)
        # 不使用 grab_set，讓主時鐘仍可接收拖曳事件

        try:
            self._setup_style()
            self._apply_theme()
            self._create_widgets()
            self._populate_options()
        except Exception as e:
            themed_error(parent, f"無法建立休假排程視窗：{e}", self.theme, title="錯誤")
            self.destroy()

    def _apply_theme(self) -> None:
        self.config(bg=self.theme['bg'])

    def _show_error(self, msg: str, title: str = "錯誤") -> None:
        """以主題樣式顯示錯誤視窗。"""
        themed_error(self, msg, self.theme, title=title)

    def _setup_style(self) -> None:
        """套用共用主題化 ttk 樣式（以 ``Vacation.`` 為前綴）。"""
        apply_themed_ttk_style('Vacation', self.theme)

    def _create_widgets(self) -> None:
        frame = ttk.Frame(self, padding="10", style='Vacation.TFrame')
        frame.pack(fill=tk.BOTH, expand=True)

        today = date.today()
        tomorrow = today + timedelta(days=1)

        # 開始日期
        start_frame = ttk.LabelFrame(frame, text="開始日期", padding="5", style='Vacation.TLabelframe')
        start_frame.pack(fill=tk.X, pady=5)

        self.start_year_var = tk.StringVar(value=str(today.year))
        self.start_month_var = tk.StringVar(value=f"{today.month:02d}")
        self.start_day_var = tk.StringVar(value=f"{today.day:02d}")

        self._add_date_row(
            start_frame,
            self.start_year_var,
            self.start_month_var,
            self.start_day_var,
            row_attr='start',
        )

        # 結束日期
        end_frame = ttk.LabelFrame(frame, text="結束日期", padding="5", style='Vacation.TLabelframe')
        end_frame.pack(fill=tk.X, pady=5)

        self.end_year_var = tk.StringVar(value=str(tomorrow.year))
        self.end_month_var = tk.StringVar(value=f"{tomorrow.month:02d}")
        self.end_day_var = tk.StringVar(value=f"{tomorrow.day:02d}")

        self._add_date_row(
            end_frame,
            self.end_year_var,
            self.end_month_var,
            self.end_day_var,
            row_attr='end',
        )

        # 備註
        note_frame = ttk.LabelFrame(frame, text="備註（選填）", padding="5", style='Vacation.TLabelframe')
        note_frame.pack(fill=tk.X, pady=5)
        self.note_entry = ttk.Entry(note_frame, style='Vacation.TEntry')
        self.note_entry.pack(fill=tk.X, expand=True)

        # 按鈕
        btn_frame = ttk.Frame(frame, style='Vacation.TFrame')
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="新增", command=self._on_submit, style='Vacation.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy, style='Vacation.TButton').pack(side=tk.RIGHT)

    def _add_date_row(
        self,
        parent: ttk.LabelFrame,
        year_var: tk.StringVar,
        month_var: tk.StringVar,
        day_var: tk.StringVar,
        row_attr: str,
    ) -> None:
        """建立年 / 月 / 日 Combobox 列。"""
        ttk.Label(parent, text="年:", style='Vacation.TLabel').pack(side=tk.LEFT)
        year_cb = ttk.Combobox(parent, textvariable=year_var, width=5, state="readonly", style='Vacation.TCombobox')
        year_cb.pack(side=tk.LEFT, padx=2)

        ttk.Label(parent, text="月:", style='Vacation.TLabel').pack(side=tk.LEFT)
        month_cb = ttk.Combobox(parent, textvariable=month_var, width=3, state="readonly", style='Vacation.TCombobox')
        month_cb.pack(side=tk.LEFT, padx=2)

        ttk.Label(parent, text="日:", style='Vacation.TLabel').pack(side=tk.LEFT)
        day_cb = ttk.Combobox(parent, textvariable=day_var, width=3, state="readonly", style='Vacation.TCombobox')
        day_cb.pack(side=tk.LEFT, padx=2)

        setattr(self, f'{row_attr}_year_cb', year_cb)
        setattr(self, f'{row_attr}_month_cb', month_cb)
        setattr(self, f'{row_attr}_day_cb', day_cb)

    def _populate_options(self) -> None:
        """填入年月日下拉選項。"""
        today = date.today()
        years = [str(y) for y in range(today.year, today.year + 5)]
        months = [f"{m:02d}" for m in range(1, 13)]
        days = [f"{d:02d}" for d in range(1, 32)]
        for cb_attr in ('start_year_cb', 'end_year_cb'):
            getattr(self, cb_attr)['values'] = years
        for cb_attr in ('start_month_cb', 'end_month_cb'):
            getattr(self, cb_attr)['values'] = months
        for cb_attr in ('start_day_cb', 'end_day_cb'):
            getattr(self, cb_attr)['values'] = days

    def _on_submit(self) -> None:
        """驗證輸入並回呼。"""
        try:
            start = self._build_date(
                self.start_year_var.get(),
                self.start_month_var.get(),
                self.start_day_var.get(),
                label="開始日期",
            )
            end = self._build_date(
                self.end_year_var.get(),
                self.end_month_var.get(),
                self.end_day_var.get(),
                label="結束日期",
            )
        except ValueError as e:
            self._show_error(str(e))
            return

        if end < start:
            self._show_error("結束日期不可早於開始日期。")
            return

        today = date.today()
        if end < today:
            self._show_error("結束日期不可早於今天。")
            return

        note = self.note_entry.get().strip()

        try:
            self.callback(start.isoformat(), end.isoformat(), note)
        except ValueError as e:
            self._show_error(str(e))
            return
        except Exception as e:
            self._show_error(f"發生錯誤：{e}")
            return

        self.destroy()

    @staticmethod
    def _build_date(year: str, month: str, day: str, label: str) -> date:
        """從 Combobox 字串組出 date；解析失敗時拋出 ValueError。"""
        try:
            return datetime(int(year), int(month), int(day)).date()
        except (TypeError, ValueError) as e:
            raise ValueError(f"{label}無效：{e}") from e
