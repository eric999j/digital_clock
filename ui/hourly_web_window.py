"""整點啟動設定視窗：設定整點自動開啟的網頁或程式，並可匯入工作排程器 XML。"""
import re
import tkinter as tk
import webbrowser
from collections.abc import Callable
from tkinter import filedialog, ttk
from typing import Any

from core.launch_rules import RULE_PROGRAM, RULE_URL, describe_rule, merge_rules, rule_target, rule_type
from core.program_launcher import LaunchError, launch_program, program_exists
from core.program_safety import RuleCheck, check_program_rule
from core.task_xml_importer import TaskImportError, import_task_xml
from core.url_validator import is_safe_url
from ui.theme_utils import (
    apply_themed_ttk_style,
    compute_brightness,
    compute_separator_color,
    get_mono_font_family,
    shift_color,
    themed_confirm,
    themed_error,
    themed_info,
)

_MIN_HEIGHT = 520
_TYPE_LABELS = {'網頁': RULE_URL, '程式': RULE_PROGRAM}
_INVALID_ROW_FG = '#E05A5A'


def _ensure_min_height(geometry: str) -> str:
    """舊設定的視窗高度可能容不下程式規則表單，低於下限時補足。"""
    m = re.fullmatch(r'(\d+)x(\d+)', geometry)
    if not m:
        return geometry
    return f"{m.group(1)}x{max(int(m.group(2)), _MIN_HEIGHT)}"


class HourlyWebWindow(tk.Toplevel):
    """用於設定整點啟動（網頁／程式）的彈出視窗。"""

    def __init__(self, parent: tk.Tk, callback: Callable, theme: dict[str, str] | None = None,
                 current_config: dict[str, Any] | None = None, geometry: str = "560x520") -> None:
        super().__init__(parent)
        self.callback = callback
        self._rules: list[dict[str, Any]] = []
        self._editing_index: int | None = None
        self.theme = theme or {'bg': '#F0F0F0', 'fg': '#000000'}
        self.current_config = current_config or {}
        self.transient(parent)
        self.title("整點啟動設定")
        self.geometry(_ensure_min_height(geometry))
        self.resizable(False, False)
        # 不使用 grab_set，讓主時鐘仍可接收拖曳事件

        try:
            self._setup_style()
            self._apply_theme()
            self._create_widgets()
            self._load_config()
        except Exception as e:
            themed_error(parent, f"無法建立設定視窗：{e}", self.theme, title="錯誤")
            self.destroy()

    def _apply_theme(self) -> None:
        """套用主題配色到視窗。"""
        self.config(bg=self.theme['bg'])

    def _show_error(self, msg: str, title: str = "錯誤") -> None:
        """以主題樣式顯示錯誤視窗。"""
        themed_error(self, msg, self.theme, title=title)

    def _setup_style(self) -> None:
        """套用共用主題化 ttk 樣式（以 ``HourlyWeb.`` 為前綴）。"""
        apply_themed_ttk_style('HourlyWeb', self.theme)

    def _create_widgets(self) -> None:
        outer = ttk.Frame(self, padding="12", style='HourlyWeb.TFrame')
        outer.pack(fill=tk.BOTH, expand=True)

        # 底部按鈕先 pack，確保永遠可見
        btn_frame = ttk.Frame(outer, style='HourlyWeb.TFrame')
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        ttk.Button(btn_frame, text="取消", command=self.destroy,
                   style='HourlyWeb.TButton').pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(btn_frame, text="儲存", command=self._on_submit,
                   style='HourlyWeb.TButton').pack(side=tk.RIGHT)

        self._create_add_form(outer)

        ttk.Label(
            outer,
            text="設定整點自動啟動的網頁或程式（預設僅工作日），支援多組規則；"
                 "也可匯入工作排程器匯出的 XML。",
            wraplength=520, justify=tk.LEFT, style='HourlyWeb.TLabel',
        ).pack(fill=tk.X, pady=(0, 6))

        # 規則清單（佔剩餘空間）
        list_frame = ttk.LabelFrame(outer, text="啟動排程規則", padding="6", style='HourlyWeb.TLabelframe')
        list_frame.pack(fill=tk.BOTH, expand=True)

        list_buttons = ttk.Frame(list_frame, style='HourlyWeb.TFrame')
        list_buttons.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))
        ttk.Button(list_buttons, text="匯入工作排程 XML…", command=self._import_xml,
                   style='HourlyWeb.TButton').pack(side=tk.LEFT)
        ttk.Button(list_buttons, text="刪除選取", command=self._remove_rule,
                   style='HourlyWeb.TButton').pack(side=tk.RIGHT)

        cols = ttk.Frame(list_frame, style='HourlyWeb.TFrame')
        cols.pack(fill=tk.BOTH, expand=True)
        self._rules_listbox = tk.Listbox(
            cols, height=5, selectmode=tk.SINGLE,
            bg='white', fg='black', font=(get_mono_font_family(), 9), activestyle='dotbox',
        )
        self._rules_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rules_listbox.bind('<Double-Button-1>', self._open_selected_rule_url)
        self._rules_listbox.bind('<Button-3>', self._show_rules_context_menu)
        sb = ttk.Scrollbar(cols, orient=tk.VERTICAL, command=self._rules_listbox.yview)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self._rules_listbox.configure(yscrollcommand=sb.set)
        self._apply_rules_listbox_theme()

        self._rules_menu = tk.Menu(self, tearoff=0)
        self._rules_menu.add_command(label="編輯規則", command=self._edit_rule)
        self._rules_menu.add_command(label="刪除此規則", command=self._remove_rule)
        self._rules_menu.configure(
            bg=self.theme.get('bg', '#F0F0F0'),
            fg=self.theme.get('fg', '#000000'),
            activebackground=shift_color(self.theme.get('bg', '#F0F0F0'), -20),
            activeforeground=self.theme.get('fg', '#000000'),
        )

    def _create_add_form(self, outer: ttk.Frame) -> None:
        """新增／編輯規則表單；程式專用欄位（參數）僅在類型為「程式」時顯示。"""
        add_frame = ttk.LabelFrame(outer, text="新增規則", padding="8", style='HourlyWeb.TLabelframe')
        self._form_frame = add_frame
        add_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 6))
        add_frame.columnconfigure(1, weight=1)

        def label(row: int, text: str) -> ttk.Label:
            lbl = ttk.Label(add_frame, text=text, width=6, style='HourlyWeb.TLabel')
            lbl.grid(row=row, column=0, sticky='w', pady=2)
            return lbl

        label(0, "類型:")
        self._type_combo = ttk.Combobox(add_frame, values=list(_TYPE_LABELS), width=7, state="readonly")
        self._type_combo.current(0)
        self._type_combo.grid(row=0, column=1, sticky='w', padx=(0, 4), pady=2)
        self._type_combo.bind('<<ComboboxSelected>>', self._on_type_changed)

        self._target_label = label(1, "URL:")
        self._add_url_entry = ttk.Entry(add_frame, style='HourlyWeb.TEntry')
        self._add_url_entry.grid(row=1, column=1, sticky='ew', padx=(0, 4), pady=2)
        self._target_button = ttk.Button(add_frame, text="測試", command=self._test_target,
                                         style='HourlyWeb.TButton')
        self._target_button.grid(row=1, column=2, sticky='ew', pady=2)

        self._args_widgets = [label(2, "參數:")]
        self._add_args_entry = ttk.Entry(add_frame, style='HourlyWeb.TEntry')
        self._add_args_entry.grid(row=2, column=1, sticky='ew', padx=(0, 4), pady=2)
        test_btn = ttk.Button(add_frame, text="測試", command=self._test_target, style='HourlyWeb.TButton')
        test_btn.grid(row=2, column=2, sticky='ew', pady=2)
        self._args_widgets += [self._add_args_entry, test_btn]

        hour_row = ttk.Frame(add_frame, style='HourlyWeb.TFrame')
        hour_row.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(4, 0))
        hours_values = [f"{h:02d}:00" for h in range(24)]
        ttk.Label(hour_row, text="時段:", width=6, style='HourlyWeb.TLabel').pack(side=tk.LEFT)
        ttk.Label(hour_row, text="從", style='HourlyWeb.TLabel').pack(side=tk.LEFT)
        self._start_combo = ttk.Combobox(hour_row, values=hours_values, width=7, state="readonly")
        self._start_combo.current(8)
        self._start_combo.pack(side=tk.LEFT, padx=4)
        ttk.Label(hour_row, text="到", style='HourlyWeb.TLabel').pack(side=tk.LEFT)
        self._end_combo = ttk.Combobox(hour_row, values=hours_values, width=7, state="readonly")
        self._end_combo.current(17)
        self._end_combo.pack(side=tk.LEFT, padx=4)
        ttk.Label(hour_row, text="（含）", style='HourlyWeb.TLabel').pack(side=tk.LEFT)
        self._submit_btn = ttk.Button(hour_row, text="新增 ＋", command=self._add_rule,
                                      style='HourlyWeb.TButton')
        self._submit_btn.pack(side=tk.RIGHT)
        self._cancel_edit_btn = ttk.Button(hour_row, text="取消編輯", command=self._end_edit,
                                           style='HourlyWeb.TButton')

        self._on_type_changed()

    def _current_type(self) -> str:
        return _TYPE_LABELS.get(self._type_combo.get(), RULE_URL)

    def _on_type_changed(self, _event: tk.Event | None = None) -> None:
        """切換類型時更新欄位標籤，並顯示／隱藏程式專用欄位。"""
        is_program = self._current_type() == RULE_PROGRAM
        self._target_label.configure(text="程式:" if is_program else "URL:")
        self._target_button.configure(
            text="瀏覽…" if is_program else "測試",
            command=self._browse_program if is_program else self._test_target,
        )
        for widget in self._args_widgets:
            if is_program:
                widget.grid()
            else:
                widget.grid_remove()

    def _apply_rules_listbox_theme(self) -> None:
        """讓規則清單在亮/暗主題下都維持可讀對比。"""
        bg = self.theme.get('bg', '#F0F0F0')
        fg = self.theme.get('fg', '#000000')
        brightness = compute_brightness(bg)
        is_dark = brightness is not None and brightness < 128
        list_bg = shift_color(bg, 18 if is_dark else -6)
        select_bg = shift_color(bg, 34 if is_dark else -28)
        border = compute_separator_color(bg)

        self._rules_listbox.configure(
            bg=list_bg,
            fg=fg,
            selectbackground=select_bg,
            selectforeground=fg,
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=border,
        )

    def _load_config(self) -> None:
        url_rules: list[dict] = self.current_config.get('url_rules', [])
        # 自動遷移舊版單一 URL 設定
        if not url_rules:
            url = self.current_config.get('url', '').strip()
            if url:
                url_rules = [{
                    'url': url,
                    'start_hour': self.current_config.get('start_hour', 8),
                    'end_hour': self.current_config.get('end_hour', 17),
                }]
        self._refresh_listbox(url_rules)

    def _refresh_listbox(self, rules: list[dict]) -> None:
        self._rules: list[dict] = list(rules)
        self._rules_listbox.delete(0, tk.END)
        for i, r in enumerate(self._rules):
            self._rules_listbox.insert(tk.END, describe_rule(r))
            # 程式規則未通過設定驗證或安全檢查時以紅色標示，雙擊不會執行
            if rule_type(r) == RULE_PROGRAM and not check_program_rule(r).ok:
                self._rules_listbox.itemconfig(i, foreground=_INVALID_ROW_FG, selectforeground=_INVALID_ROW_FG)

    def _editing_rule(self) -> dict[str, Any] | None:
        """回傳正在編輯的原規則；非編輯模式回傳 None。"""
        idx = self._editing_index
        return self._rules[idx] if idx is not None and idx < len(self._rules) else None

    def _build_rule_from_form(self) -> dict[str, Any] | None:
        """依表單內容建立規則；目標欄位為空回傳 None，內容無效拋出 ValueError。

        編輯時會沿用表單未顯示的欄位（星期、名稱、起始目錄），匯入的規則才不會失真。
        """
        target = self._add_url_entry.get().strip()
        if not target:
            return None
        start_hour = int(self._start_combo.get().split(':')[0])
        end_hour = int(self._end_combo.get().split(':')[0])
        if start_hour > end_hour:
            raise ValueError("結束時間不能早於開始時間。")

        original = self._editing_rule() or {}
        kept: dict[str, Any] = {}
        if original.get('weekdays'):
            kept['weekdays'] = original['weekdays']
        hours = {'start_hour': start_hour, 'end_hour': end_hour}

        if self._current_type() == RULE_PROGRAM:
            command = target.strip('"')
            # 未改動的既有程式路徑不重驗，避免在沒有該程式的機器上無法調整時段
            unchanged = rule_type(original) == RULE_PROGRAM and rule_target(original) == command
            if not unchanged and not program_exists(command):
                raise ValueError(f"找不到程式：{command}")
            if rule_type(original) == RULE_PROGRAM:
                kept.update({k: original[k] for k in ('name', 'working_dir') if original.get(k)})
            rule = {
                'type': RULE_PROGRAM,
                'command': command,
                'arguments': self._add_args_entry.get().strip(),
                **kept,
                **hours,
            }
            blocked = check_program_rule(rule).blocked
            if blocked:
                raise ValueError("安全檢查未通過，無法新增此程式規則：\n" + "\n".join(f"- {m}" for m in blocked))
            return rule
        if not is_safe_url(target):
            raise ValueError("請使用以 http:// 或 https:// 開頭的有效網址。")
        return {'url': target, **kept, **hours}

    def _clear_form(self) -> None:
        for entry in (self._add_url_entry, self._add_args_entry):
            entry.delete(0, tk.END)

    def _set_editing(self, editing: bool) -> None:
        """切換表單的新增／編輯外觀。"""
        self._form_frame.configure(text="編輯規則" if editing else "新增規則")
        self._submit_btn.configure(text="更新 ✓" if editing else "新增 ＋")
        if editing:
            self._cancel_edit_btn.pack(side=tk.RIGHT, padx=(0, 4))
        else:
            self._cancel_edit_btn.pack_forget()

    def _end_edit(self) -> None:
        """離開編輯模式並清空表單。"""
        self._editing_index = None
        self._clear_form()
        self._set_editing(False)

    def _edit_rule(self) -> None:
        """把選取的規則載入表單進行編輯，按「更新」或「儲存」後生效。"""
        sel = self._rules_listbox.curselection()
        if not sel or sel[0] >= len(self._rules):
            return
        rule = self._rules[sel[0]]
        self._clear_form()
        self._editing_index = sel[0]
        is_program = rule_type(rule) == RULE_PROGRAM
        self._type_combo.set('程式' if is_program else '網頁')
        self._on_type_changed()
        self._add_url_entry.insert(0, rule_target(rule))
        if is_program:
            self._add_args_entry.insert(0, str(rule.get('arguments', '')))
        self._start_combo.set(f"{int(rule.get('start_hour', 0)):02d}:00")
        self._end_combo.set(f"{int(rule.get('end_hour', 23)):02d}:00")
        self._set_editing(True)

    def _add_rule(self) -> None:
        """新增規則；編輯模式下則以表單內容取代被編輯的規則。"""
        try:
            rule = self._build_rule_from_form()
        except ValueError as e:
            self._show_error(str(e))
            return
        if rule is None:
            self._show_error("請輸入網址或程式路徑。")
            return
        self._apply_form_rule(rule)
        self._end_edit()

    def _apply_form_rule(self, rule: dict[str, Any]) -> None:
        rules = list(self._rules)
        if self._editing_rule() is not None:
            rules[self._editing_index] = rule
        else:
            rules.append(rule)
        self._refresh_listbox(rules)

    def _remove_rule(self) -> None:
        sel = self._rules_listbox.curselection()
        if not sel:
            return
        rules = list(self._rules)
        del rules[sel[0]]
        self._refresh_listbox(rules)
        if self._editing_index is not None:
            self._end_edit()

    def _show_rules_context_menu(self, event: tk.Event) -> None:
        """在規則列上按右鍵顯示刪除選單。"""
        if self._rules_listbox.size() == 0:
            return

        index = self._rules_listbox.nearest(event.y)
        bbox = self._rules_listbox.bbox(index)
        if not bbox:
            return
        item_top = bbox[1]
        item_bottom = item_top + bbox[3]
        if not (item_top <= event.y <= item_bottom):
            return

        self._rules_listbox.selection_clear(0, tk.END)
        self._rules_listbox.selection_set(index)
        self._rules_listbox.activate(index)

        try:
            self._rules_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._rules_menu.grab_release()

    def _open_selected_rule_url(self, _event: tk.Event | None) -> None:
        """雙擊規則：網頁直接開啟；程式須通過設定驗證與安全檢查並經使用者確認才執行。"""
        sel = self._rules_listbox.curselection()
        if not sel:
            return

        idx = sel[0]
        if idx >= len(self._rules):
            return
        if rule_type(self._rules[idx]) == RULE_PROGRAM:
            self._run_program_rule(self._rules[idx])
            return

        url = rule_target(self._rules[idx])
        if not is_safe_url(url):
            self._show_error("此規則的網址無效，請先編輯為 http:// 或 https:// 開頭。")
            return

        try:
            webbrowser.open(url)
        except Exception as e:
            self._show_error(f"無法開啟網頁：{e}")

    @staticmethod
    def _format_issues(header: str, issues: tuple[str, ...]) -> str:
        return header + "\n" + "\n".join(f"- {issue}" for issue in issues)

    def _run_program_rule(self, rule: dict[str, Any]) -> None:
        """依序做設定驗證、安全檢查、使用者確認，全部通過才啟動程式。"""
        check = check_program_rule(rule)
        if check.errors:
            self._show_error(self._format_issues("此程式規則設定不正確，無法執行：", check.errors))
            return
        if check.blocked:
            self._show_error(
                self._format_issues("安全檢查未通過，已拒絕執行：", check.blocked), title="已拒絕執行",
            )
            return

        self._confirm_launch(rule, check)

    def _confirm_launch(self, rule: dict[str, Any], check: RuleCheck) -> None:
        command = rule_target(rule)
        arguments = str(rule.get('arguments', '')).strip()
        working_dir = str(rule.get('working_dir', '')).strip()
        lines = ["檢查通過，確定要執行以下程式嗎？", "", f"程式：{command}"]
        if arguments:
            lines.append(f"參數：{arguments}")
        if working_dir:
            lines.append(f"起始目錄：{working_dir}")
        if check.warnings:
            lines += ["", *(f"注意：{w}" for w in check.warnings)]
        themed_confirm(
            self, "\n".join(lines), lambda: self._launch_checked(rule), self.theme,
            title="確認執行", yes_text="執行", no_text="取消",
        )

    def _launch_checked(self, rule: dict[str, Any]) -> None:
        try:
            launch_program(rule_target(rule), rule.get('arguments', ''), rule.get('working_dir', ''))
        except LaunchError as e:
            self._show_error(str(e))

    def _browse_program(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="選擇程式",
            filetypes=[("可執行檔", "*.exe *.bat *.cmd *.com"), ("所有檔案", "*.*")],
        )
        if path:
            self._add_url_entry.delete(0, tk.END)
            self._add_url_entry.insert(0, path)

    def _test_target(self) -> None:
        target = self._add_url_entry.get().strip()
        if self._current_type() == RULE_PROGRAM:
            rule = {
                'type': RULE_PROGRAM,
                'command': target.strip('"'),
                'arguments': self._add_args_entry.get().strip(),
                'working_dir': (self._editing_rule() or {}).get('working_dir', ''),
            }
            self._run_program_rule(rule)
            return

        if not target:
            self._show_error("請先輸入網頁網址。")
            return
        if not is_safe_url(target):
            self._show_error("請使用以 http:// 或 https:// 開頭的有效網址。")
            return
        try:
            webbrowser.open(target)
        except Exception as e:
            self._show_error(f"無法開啟網頁：{e}")

    def _import_xml(self) -> None:
        """匯入工作排程器 XML，規則加入清單（按「儲存」後才寫入設定）。"""
        path = filedialog.askopenfilename(
            parent=self, title="匯入工作排程器 XML",
            filetypes=[("工作排程器 XML", "*.xml"), ("所有檔案", "*.*")],
        )
        if not path:
            return
        try:
            result = import_task_xml(path)
        except TaskImportError as e:
            self._show_error(f"匯入失敗：{e}")
            return

        merged, added = merge_rules(self._rules, result.rules)
        self._refresh_listbox(merged)
        skipped = len(result.rules) - added
        summary = f"已匯入 {added} 條規則"
        if skipped:
            summary += f"（{skipped} 條重複已略過）"
        lines = [summary + "，按「儲存」後生效。", *(f"- {w}" for w in result.warnings)]
        for rule in result.rules:
            if rule_type(rule) == RULE_PROGRAM:
                for issue in check_program_rule(rule).blocked:
                    lines.append(f"- 未通過安全檢查（將不會執行）：{rule_target(rule)}：{issue}")
        themed_info(self, "\n".join(lines), self.theme, title="匯入結果", ok_text="確定")

    def _on_submit(self) -> None:
        rules = list(self._rules)
        try:
            pending = self._build_rule_from_form()
        except ValueError as e:
            self._show_error(str(e))
            return
        if pending is not None:
            self._apply_form_rule(pending)
            rules = list(self._rules)
        self.callback(rules)
        self.destroy()
