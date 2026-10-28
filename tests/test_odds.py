import unittest

from ballout import odds


class OddsTests(unittest.TestCase):
    def test_parse_american_and_decimal(self):
        self.assertAlmostEqual(odds.parse_odds("-150"), 1 + 100 / 150)
        self.assertAlmostEqual(odds.parse_odds("+130"), 2.3)
        self.assertAlmostEqual(odds.parse_odds(130), 2.3)
        self.assertAlmostEqual(odds.parse_odds("1.91"), 1.91)
        with self.assertRaises(ValueError):
            odds.parse_odds("0.5")

    def test_round_trip(self):
        self.assertEqual(odds.decimal_to_american(2.5), "+150")
        self.assertEqual(odds.decimal_to_american(1.5), "-200")
        self.assertEqual(odds.prob_to_american(0.5), "+100")

    def test_no_vig(self):
        pa, pb, vig = odds.no_vig(odds.parse_odds(-110), odds.parse_odds(-110))
        self.assertAlmostEqual(pa, 0.5)
        self.assertAlmostEqual(pb, 0.5)
        self.assertAlmostEqual(vig, 0.0476, places=3)

    def test_ev_and_kelly(self):
        self.assertAlmostEqual(odds.expected_value(0.5, 2.2), 0.1)
        self.assertAlmostEqual(odds.kelly_fraction(0.5, 2.2), 0.1 / 1.2)
        self.assertEqual(odds.kelly_fraction(0.4, 2.0), 0.0)


if __name__ == "__main__":
    unittest.main()
