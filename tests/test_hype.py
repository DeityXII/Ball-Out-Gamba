import unittest

import numpy as np
import pandas as pd

from ballout import hype


class HypeScoreTests(unittest.TestCase):
    def test_score_meter_and_label(self):
        self.assertAlmostEqual(hype.score(0.6, False), 0.6)
        self.assertAlmostEqual(hype.score(0.6, True), 0.9)  # unbeaten amplifies the gap
        self.assertEqual(hype.label(-1.0), "Underrated")
        self.assertEqual(hype.label(0.0), "Fairly rated")
        self.assertEqual(hype.label(0.5), "Hyped")
        self.assertEqual(hype.label(1.0), "Very hyped")
        self.assertEqual(hype.label(2.0), "Fraud-check zone")
        self.assertEqual(hype.meter(-5), 0)
        self.assertEqual(hype.meter(0.75), 60)
        self.assertEqual(hype.meter(1.25), 80)
        self.assertEqual(hype.meter(9), 100)
        meters = [hype.meter(x) for x in np.linspace(-2, 3, 50)]
        self.assertEqual(meters, sorted(meters))  # monotone

    def test_reasons(self):
        h = {"available": True, "gap pts": 20.0, "unbeaten": True, "ufc_fights": 3, "opp_avg_elo": 1440.0}
        why = " ".join(hype.reasons(h))
        self.assertIn("20 pts higher", why)
        self.assertIn("unbeaten", why)
        self.assertIn("below-average", why)
        self.assertEqual(hype.reasons({"available": True, "gap pts": -12.0, "unbeaten": False,
                                       "ufc_fights": 10, "opp_avg_elo": 1600.0}),
                         ["their stats rate them 12 pts higher than the odds do"])


class BacktestTableTests(unittest.TestCase):
    def test_bands_and_bias_correction(self):
        rng = np.random.default_rng(0)
        n = 6000
        pm = rng.uniform(0.2, 0.85, n)
        h = pd.DataFrame({"date": pd.Timestamp("2020-01-01"), "p_market": pm,
                          "won": (rng.random(n) < pm).astype(float), "hype": rng.normal(0, 0.7, n)})
        bt = hype.backtest_table(h)
        self.assertEqual(list(bt["band"]), [b for _, b in hype.BANDS])
        self.assertEqual(bt["fights"].sum(), n)
        # outcomes drawn from the odds themselves: no band should be far off
        self.assertTrue((bt["vs corrected"].abs() < 4 * bt["± (1 s.e.)"] + 0.01).all())


if __name__ == "__main__":
    unittest.main()
