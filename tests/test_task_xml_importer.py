import os
import tempfile
import unittest
from pathlib import Path

from core.task_xml_importer import TaskImportError, import_task_xml, parse_task_xml

_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def _task_xml(triggers: str, actions: str, uri: str = r"\最新公告") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\r\n'
        f'<Task version="1.2" xmlns="{_NS}">'
        f'<RegistrationInfo><URI>{uri}</URI></RegistrationInfo>'
        f'<Triggers>{triggers}</Triggers><Actions Context="Author">{actions}</Actions></Task>'
    )


_WEEKDAY_TRIGGER = (
    '<CalendarTrigger><StartBoundary>2024-12-10T09:00:00</StartBoundary><Enabled>true</Enabled>'
    '<ScheduleByWeek><DaysOfWeek><Monday /><Tuesday /><Wednesday /><Thursday /><Friday />'
    '</DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek></CalendarTrigger>'
)
_EXEC = (
    '<Exec><Command>C:\\Python313\\python.exe</Command>'
    '<Arguments>C:\\Users\\x\\Daily\\company_news.py</Arguments>'
    '<WorkingDirectory>C:\\Users\\x\\Daily</WorkingDirectory></Exec>'
)


def _utf16(text: str) -> bytes:
    return text.encode('utf-16')  # 含 BOM，與工作排程器匯出格式相同


class TestParseTaskXml(unittest.TestCase):
    def test_weekday_task_becomes_single_program_rule(self):
        result = parse_task_xml(_utf16(_task_xml(_WEEKDAY_TRIGGER, _EXEC)))

        self.assertEqual(result.rules, [{
            'type': 'program',
            'command': 'C:\\Python313\\python.exe',
            'arguments': 'C:\\Users\\x\\Daily\\company_news.py',
            'working_dir': 'C:\\Users\\x\\Daily',
            'start_hour': 9,
            'end_hour': 9,
            'weekdays': [0, 1, 2, 3, 4],
            'name': '最新公告',
        }])

    def test_utf8_file_is_supported(self):
        text = _task_xml(_WEEKDAY_TRIGGER, _EXEC).replace('UTF-16', 'UTF-8')
        result = parse_task_xml(text.encode('utf-8'))
        self.assertEqual(len(result.rules), 1)

    def test_daily_trigger_runs_every_day(self):
        trigger = (
            '<CalendarTrigger><StartBoundary>2024-12-10T14:00:00</StartBoundary>'
            '<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger>'
        )
        rule = parse_task_xml(_utf16(_task_xml(trigger, _EXEC))).rules[0]
        self.assertEqual(rule['weekdays'], list(range(7)))
        self.assertEqual(rule['start_hour'], 14)

    def test_multiple_triggers_and_actions_produce_cross_product(self):
        trigger2 = _WEEKDAY_TRIGGER.replace('09:00:00', '15:00:00')
        action2 = '<Exec><Command>notepad.exe</Command></Exec>'
        result = parse_task_xml(_utf16(_task_xml(_WEEKDAY_TRIGGER + trigger2, _EXEC + action2)))
        self.assertEqual(len(result.rules), 4)
        self.assertEqual(sorted({r['start_hour'] for r in result.rules}), [9, 15])

    def test_non_zero_minute_is_rounded_with_warning(self):
        trigger = _WEEKDAY_TRIGGER.replace('09:00:00', '09:30:00')
        result = parse_task_xml(_utf16(_task_xml(trigger, _EXEC)))
        self.assertEqual(result.rules[0]['start_hour'], 9)
        self.assertTrue(any('09:30' in w for w in result.warnings))

    def test_disabled_trigger_is_skipped(self):
        disabled = _WEEKDAY_TRIGGER.replace('<Enabled>true</Enabled>', '<Enabled>false</Enabled>')
        with self.assertRaises(TaskImportError):
            parse_task_xml(_utf16(_task_xml(disabled, _EXEC)))

    def test_unsupported_trigger_and_action_are_reported(self):
        triggers = _WEEKDAY_TRIGGER + '<LogonTrigger><Enabled>true</Enabled></LogonTrigger>'
        actions = _EXEC + '<ComHandler><ClassId>{x}</ClassId></ComHandler>'
        result = parse_task_xml(_utf16(_task_xml(triggers, actions)))
        self.assertEqual(len(result.rules), 1)
        self.assertTrue(any('LogonTrigger' in w for w in result.warnings))
        self.assertTrue(any('ComHandler' in w for w in result.warnings))

    def test_repetition_and_interval_warnings(self):
        trigger = _WEEKDAY_TRIGGER.replace(
            '<WeeksInterval>1</WeeksInterval>', '<WeeksInterval>2</WeeksInterval>'
        ).replace('</CalendarTrigger>', '<Repetition><Interval>PT1H</Interval></Repetition></CalendarTrigger>')
        result = parse_task_xml(_utf16(_task_xml(trigger, _EXEC)))
        self.assertTrue(any('2 週' in w for w in result.warnings))
        self.assertTrue(any('重複' in w for w in result.warnings))

    def test_missing_program_reports_warning(self):
        action = '<Exec><Command>C:\\definitely\\missing\\tool.exe</Command></Exec>'
        result = parse_task_xml(_utf16(_task_xml(_WEEKDAY_TRIGGER, action)))
        self.assertTrue(any('找不到程式' in w for w in result.warnings))

    def test_quoted_command_is_unquoted(self):
        action = '<Exec><Command>"C:\\Program Files\\App\\a.exe"</Command></Exec>'
        rule = parse_task_xml(_utf16(_task_xml(_WEEKDAY_TRIGGER, action))).rules[0]
        self.assertEqual(rule['command'], 'C:\\Program Files\\App\\a.exe')

    def test_no_trigger_or_no_action_raises(self):
        with self.assertRaises(TaskImportError):
            parse_task_xml(_utf16(_task_xml('', _EXEC)))
        with self.assertRaises(TaskImportError):
            parse_task_xml(_utf16(_task_xml(_WEEKDAY_TRIGGER, '')))

    def test_invalid_xml_raises(self):
        with self.assertRaises(TaskImportError):
            parse_task_xml(b'<Task><oops>')

    def test_non_task_root_raises(self):
        with self.assertRaises(TaskImportError):
            parse_task_xml(b'<html></html>')

    def test_doctype_is_rejected(self):
        evil = b'<?xml version="1.0"?><!DOCTYPE Task [<!ENTITY a "b">]><Task>&a;</Task>'
        with self.assertRaises(TaskImportError):
            parse_task_xml(evil)

    def test_oversized_payload_is_rejected(self):
        with self.assertRaises(TaskImportError):
            parse_task_xml(b'<Task>' + b' ' * (1024 * 1024) + b'</Task>')


class TestImportTaskXmlFile(unittest.TestCase):
    def test_reads_utf16_file_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'task.xml'
            path.write_bytes(_utf16(_task_xml(_WEEKDAY_TRIGGER, _EXEC)))
            self.assertEqual(len(import_task_xml(path).rules), 1)

    def test_missing_file_raises(self):
        with self.assertRaises(TaskImportError):
            import_task_xml(os.path.join(tempfile.gettempdir(), 'no_such_task_file.xml'))

    @unittest.skipUnless((Path.home() / 'Desktop' / '最新公告.xml').exists(), '桌面無範例檔')
    def test_real_announcement_export(self):
        result = import_task_xml(Path.home() / 'Desktop' / '最新公告.xml')
        self.assertEqual(len(result.rules), 1)
        rule = result.rules[0]
        self.assertEqual((rule['start_hour'], rule['weekdays']), (9, [0, 1, 2, 3, 4]))
        self.assertTrue(rule['command'].endswith('python.exe'))
        self.assertTrue(rule['arguments'].endswith('company_news.py'))


if __name__ == '__main__':
    unittest.main()
