from unittest import TestCase

from preview.config import boolean, interval, bytesize


class BooleanTestCase(TestCase):
    def test_parse_true(self):
        strings = [
            'true', 'True', 'TRUE', 'on', 'On', 'ON', 'yes', 'Yes', 'YES', '1',
        ]
        for s in strings:
            self.assertTrue(boolean(s) is True, '%s did not evaluate to True' % s)

    def test_parse_false(self):
        strings = [
            None, 'false', 'False', 'FALSE', 'off', 'Off', 'OFF', 'no', 'No', 'NO', '0',
        ]
        for s in strings:
            self.assertTrue(boolean(s) is False, '%s did not evaluate to False' % s)


class IntervalTestCase(TestCase):
    def test_parse_invalid(self):
        self.assertIsNone(interval(''))
        self.assertIsNone(interval(None))
        with self.assertRaises(ValueError):
            interval('1g')

    def test_parse_valid(self):
        self.assertEqual(interval('1'), 1)
        self.assertEqual(interval('1s'), 1)
        self.assertEqual(interval('5m'), 300)
        self.assertEqual(interval('5M'), 300)
        self.assertEqual(interval('500s'), 500)
        self.assertEqual(interval('007m'), 420)


class BytesizeTestCase(TestCase):
    def test_parse_invalid(self):
        self.assertIsNone(bytesize(''))
        self.assertIsNone(bytesize(None))
        with self.assertRaises(ValueError):
            bytesize('1s')

    def test_parse_valid(self):
        self.assertEqual(bytesize('1'), 1)
        self.assertEqual(bytesize('1m'), 1048576)
        self.assertEqual(bytesize('1g'), 1073741824)
        self.assertEqual(bytesize('5g'), 5368709120)
        self.assertEqual(bytesize('5G'), 5368709120)
        self.assertEqual(bytesize('1t'), 1099511627776)
