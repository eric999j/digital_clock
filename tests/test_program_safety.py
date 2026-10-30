import os
import sys
import tempfile
import unittest
from pathlib import Path

from core.program_safety import check_program_rule, scan_text


def _rule(command: str, arguments: str = '', **extra) -> dict:
    return {'type': 'program', 'command': command, 'arguments': arguments,
            'start_hour': 9, 'end_hour': 9, **extra}


class TestProgramConfigChecks(unittest.TestCase):
    def test_valid_existing_program_passes(self):
        check = check_program_rule(_rule(sys.executable, '-V'))
        self.assertEqual((check.errors, check.blocked), ((), ()))
        self.assertTrue(check.ok)

    def test_missing_program_is_config_error_not_safety_block(self):
        check = check_program_rule(_rule('definitely_missing_tool_xyz'))
        self.assertTrue(check.errors)
        self.assertEqual(check.blocked, ())
        self.assertFalse(check.ok)

    def test_blank_command_is_error(self):
        self.assertTrue(check_program_rule(_rule('  ')).errors)

    def test_missing_working_dir_is_error(self):
        check = check_program_rule(_rule(sys.executable, working_dir=os.path.join(tempfile.gettempdir(), 'no_dir_xyz')))
        self.assertTrue(any('起始目錄' in e for e in check.errors))

    def test_control_characters_are_rejected(self):
        self.assertTrue(any('控制字元' in e for e in check_program_rule(_rule(sys.executable, 'a\nb')).errors))

    def test_overlong_arguments_are_rejected(self):
        self.assertTrue(any('過長' in e for e in check_program_rule(_rule(sys.executable, 'a' * 5000)).errors))

    def test_invalid_hours_and_weekdays_are_errors(self):
        bad_hours = {**_rule(sys.executable), 'start_hour': 10, 'end_hour': 9}
        bad_days = _rule(sys.executable, weekdays=[0, 7])
        self.assertTrue(any('時段' in e for e in check_program_rule(bad_hours).errors))
        self.assertTrue(any('星期' in e for e in check_program_rule(bad_days).errors))

    @unittest.skipUnless(sys.platform == 'win32', '副檔名限制僅適用 Windows')
    def test_unsupported_extension_is_error_on_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'note.txt'
            path.write_text('x', encoding='utf-8')
            self.assertTrue(any('不支援' in e for e in check_program_rule(_rule(str(path))).errors))


class TestProgramSafetyChecks(unittest.TestCase):
    def test_destructive_programs_are_blocked_regardless_of_arguments(self):
        for command in ('shutdown.exe', 'format.com', 'diskpart', r'C:\Windows\System32\bcdedit.exe'):
            with self.subTest(command=command):
                self.assertTrue(check_program_rule(_rule(command)).blocked)

    def test_dangerous_arguments_are_blocked(self):
        for arguments in ('/c rd /s /q C:\\', 'format c: /q', 'reg delete HKLM\\Software /f',
                          'vssadmin delete shadows /all', 'rm -rf /', 'dd if=/dev/zero of=/dev/sda'):
            with self.subTest(arguments=arguments):
                self.assertTrue(check_program_rule(_rule(sys.executable, arguments)).blocked)

    def test_interpreters_get_a_warning(self):
        check = check_program_rule(_rule('cmd', '/c echo hi'))
        self.assertTrue(any('命令直譯器' in w for w in check.warnings))
        self.assertEqual(check.blocked, ())

    def test_batch_file_content_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'bad.bat'
            bad.write_text('@echo off\nrd /s /q D:\\data\n', encoding='utf-8')
            good = Path(tmp) / 'good.bat'
            good.write_text('@echo off\necho hello\n', encoding='utf-8')
            self.assertTrue(check_program_rule(_rule(str(bad))).blocked)
            self.assertEqual(check_program_rule(_rule(str(good))).blocked, ())

    def test_utf16_batch_file_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad16.bat'
            path.write_bytes('shutdown /s /t 0\r\n'.encode('utf-16'))
            self.assertTrue(check_program_rule(_rule(str(path))).blocked)

    def test_script_passed_as_argument_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'job.py'
            bad.write_text("import shutil\nshutil.rmtree('/')\n", encoding='utf-8')
            good = Path(tmp) / 'ok.py'
            good.write_text("print('graceful shutdown complete')\n", encoding='utf-8')
            self.assertTrue(check_program_rule(_rule(sys.executable, 'job.py', working_dir=tmp)).blocked)
            self.assertTrue(check_program_rule(_rule(sys.executable, f'"{bad}"')).blocked)
            self.assertEqual(check_program_rule(_rule(sys.executable, str(good))).blocked, ())

    def test_oversized_script_only_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'big.py'
            path.write_text('#' * (300 * 1024), encoding='utf-8')
            check = check_program_rule(_rule(sys.executable, str(path)))
            self.assertEqual(check.blocked, ())
            self.assertTrue(any('過大' in w for w in check.warnings))

    def test_scan_text_ignores_harmless_mentions(self):
        self.assertEqual(scan_text('graceful shutdown and format string'), [])
        self.assertIn('fork bomb', scan_text('%0|%0'))


if __name__ == '__main__':
    unittest.main()
