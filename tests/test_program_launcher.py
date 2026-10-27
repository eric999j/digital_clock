import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.program_launcher import LaunchError, launch_program, program_exists


class TestProgramLauncher(unittest.TestCase):
    def test_program_exists_for_real_interpreter(self):
        self.assertTrue(program_exists(sys.executable))
        self.assertTrue(program_exists(f'"{sys.executable}"'))

    def test_program_exists_false_for_missing_or_empty(self):
        self.assertFalse(program_exists(''))
        self.assertFalse(program_exists('definitely_missing_tool_xyz'))

    def test_missing_command_raises_without_spawning(self):
        with patch('core.program_launcher.subprocess.Popen') as popen:
            with self.assertRaises(LaunchError):
                launch_program('definitely_missing_tool_xyz')
            with self.assertRaises(LaunchError):
                launch_program('   ')
        popen.assert_not_called()

    def test_missing_working_dir_raises(self):
        with patch('core.program_launcher.subprocess.Popen') as popen:
            with self.assertRaises(LaunchError):
                launch_program(sys.executable, '', os.path.join(tempfile.gettempdir(), 'no_such_dir_xyz'))
        popen.assert_not_called()

    def test_never_uses_shell(self):
        with patch('core.program_launcher.subprocess.Popen') as popen:
            launch_program(sys.executable, 'a b', tempfile.gettempdir())
        self.assertNotIn('shell', popen.call_args.kwargs)
        self.assertEqual(popen.call_args.kwargs['cwd'], tempfile.gettempdir())

    def test_popen_failure_is_wrapped(self):
        with patch('core.program_launcher.subprocess.Popen', side_effect=OSError('denied')):
            with self.assertRaises(LaunchError):
                launch_program(sys.executable)

    def test_launches_real_process_with_arguments_and_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out.txt'
            script = Path(tmp) / 'job.py'
            script.write_text(
                "import os, sys\nopen('out.txt', 'w').write(os.getcwd() + '|' + sys.argv[1])\n",
                encoding='utf-8',
            )
            args = f'"{script}" "hello world"'
            launch_program(sys.executable, args, tmp)

            import time
            for _ in range(100):
                if out.exists() and out.read_text(encoding='utf-8'):
                    break
                time.sleep(0.1)
            cwd, arg = out.read_text(encoding='utf-8').split('|')
            self.assertEqual(os.path.normcase(os.path.realpath(cwd)), os.path.normcase(os.path.realpath(tmp)))
            self.assertEqual(arg, 'hello world')


if __name__ == '__main__':
    unittest.main()
