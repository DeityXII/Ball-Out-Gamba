import math
import unittest

from ballout import data


class ParsingTests(unittest.TestCase):
    def test_parse_of(self):
        self.assertEqual(data.parse_of("24 of 47"), (24.0, 47.0))
        self.assertTrue(all(math.isnan(x) for x in data.parse_of("--")))

    def test_parse_mmss(self):
        self.assertEqual(data.parse_mmss("4:54"), 294)
        self.assertTrue(math.isnan(data.parse_mmss("--")))

    def test_parse_height_and_numbers(self):
        self.assertEqual(data.parse_height("5' 11\""), 71)
        self.assertEqual(data.parse_number("155 lbs."), 155)
        self.assertEqual(data.parse_number('72"'), 72)
        self.assertTrue(math.isnan(data.parse_number("--")))

    def test_time_format_and_fight_seconds(self):
        self.assertEqual(data.parse_time_format("5 Rnd (5-5-5-5-5)"), [5, 5, 5, 5, 5])
        self.assertEqual(data.parse_time_format("1 Rnd + OT (12-3)"), [12, 3])
        self.assertIsNone(data.parse_time_format("No Time Limit"))
        self.assertEqual(data.fight_seconds(2, 294, "3 Rnd (5-5-5)"), 594)
        self.assertEqual(data.fight_seconds(1, 733, "No Time Limit"), 733)

    def test_weight_class(self):
        self.assertEqual(data.normalize_weight_class("UFC Light Heavyweight Title Bout"),
                         ("Light Heavyweight", False, True))
        self.assertEqual(data.normalize_weight_class("Women's Strawweight Bout"),
                         ("Women's Strawweight", True, False))
        self.assertEqual(data.normalize_weight_class("UFC 2 Tournament Title Bout")[0], "Open Weight")
        self.assertEqual(data.weight_limit("Women's Flyweight"), 125)


if __name__ == "__main__":
    unittest.main()
