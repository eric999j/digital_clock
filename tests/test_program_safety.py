import os
import sys
import tempfile
import unittest
from pathlib import Path

from core.program_safety import check_program_rule


def _rule(command: str, arguments: str = '', **extra: object) -> dict:
    return {'type': 'program', 'command': command, 'arguments': arguments,
            'start_hour': 9, 'end_hour': 9, **extra}


class TestProgramConfigChecks(unittest.TestCase):
    def test_valid_existing_program_passes(self) -> None:
        check = check_program_rule(_rule(sys.executable, '-V'))
        self.assertEqual(check.errors, ())
        self.assertTrue(check.ok)

    def test_missing_program_is_error(self) -> None:
        check = check_program_rule(_rule('definitely_missing_tool_xyz'))
        self.assertTrue(check.errors)
        self.assertFalse(check.ok)

    def test_invalid_paths_arguments_and_schedule_are_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cases = [
                _rule('  '),
                _rule(sys.executable, working_dir=os.path.join(tmp, 'missing')),
                _rule(sys.executable, 'a\nb'),
                _rule(sys.executable, 'a' * 5000),
                _rule(sys.executable, start_hour=10, end_hour=9),
                _rule(sys.executable, weekdays=[0, 7]),
            ]
            for rule in cases:
                with self.subTest(rule=rule):
                    self.assertTrue(check_program_rule(rule).errors)

    @unittest.skipUnless(sys.platform == 'win32', '副檔名限制僅適用 Windows')
    def test_unsupported_extension_is_error_on_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'note.txt'
            path.write_text('x', encoding='utf-8')
            self.assertTrue(check_program_rule(_rule(str(path))).errors)

    def test_command_content_is_not_claimed_safe_or_unsafe(self) -> None:
        """安全決策在 UI 的完整命令確認，不由可繞過的內容掃描做出。"""
        check = check_program_rule(_rule(sys.executable, 'anything'))
        self.assertEqual(check.blocked, ())
        self.assertEqual(check.warnings, ())


if __name__ == '__main__':
    unittest.main()
