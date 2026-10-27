import unittest

from core.launch_rules import describe_rule, format_weekdays, merge_rules, rule_key, rule_type


class TestLaunchRules(unittest.TestCase):
    def test_legacy_rule_without_type_is_url(self):
        self.assertEqual(rule_type({'url': 'https://a.example'}), 'url')

    def test_rule_key_distinguishes_arguments(self):
        a = {'type': 'program', 'command': 'x.exe', 'arguments': '1'}
        b = {'type': 'program', 'command': 'x.exe', 'arguments': '2'}
        self.assertNotEqual(rule_key(a), rule_key(b))

    def test_format_weekdays(self):
        self.assertEqual(format_weekdays(None), '')
        self.assertEqual(format_weekdays([0, 1, 2, 3, 4]), '週一至週五')
        self.assertEqual(format_weekdays(list(range(7))), '每天')
        self.assertEqual(format_weekdays([0, 2]), '週一、三')

    def test_describe_rule(self):
        self.assertEqual(
            describe_rule({'url': 'https://a.example', 'start_hour': 9, 'end_hour': 12}),
            '09:00–12:00  [網頁] https://a.example',
        )
        self.assertEqual(
            describe_rule({'type': 'program', 'command': 'p.exe', 'arguments': 'a.py',
                           'start_hour': 9, 'end_hour': 9, 'weekdays': [0, 1, 2, 3, 4]}),
            '09:00–09:00  週一至週五  [程式] p.exe a.py',
        )
        self.assertEqual(
            describe_rule({'type': 'program', 'command': 'p.exe', 'name': '最新公告',
                           'start_hour': 9, 'end_hour': 9}),
            '09:00–09:00  [程式] 最新公告 — p.exe',
        )

    def test_merge_rules_skips_duplicates(self):
        rule = {'type': 'program', 'command': 'p.exe', 'arguments': 'a', 'start_hour': 9,
                'end_hour': 9, 'weekdays': [0, 1]}
        other_hour = {**rule, 'start_hour': 10, 'end_hour': 10}
        merged, added = merge_rules([rule], [dict(rule), other_hour])
        self.assertEqual(added, 1)
        self.assertEqual(len(merged), 2)

    def test_merge_rules_dedupes_within_incoming(self):
        rule = {'url': 'https://a.example', 'start_hour': 9, 'end_hour': 9}
        merged, added = merge_rules([], [rule, dict(rule)])
        self.assertEqual((len(merged), added), (1, 1))


if __name__ == '__main__':
    unittest.main()
