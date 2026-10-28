import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from ballout import config, market


class BlendTests(unittest.TestCase):
    def test_blend_is_symmetric(self):
        w = [0.25, 1.0]
        p = market.blend(0.7, 0.6, w) + market.blend(0.3, 0.4, w)
        self.assertAlmostEqual(float(p), 1.0)

    def test_fit_blend_trusts_the_informative_source(self):
        rng = np.random.default_rng(0)
        truth = rng.uniform(0.2, 0.8, 3000)
        y = (rng.random(3000) < truth).astype(float)
        noise = np.clip(truth + rng.normal(0, 0.25, 3000), 0.05, 0.95)
        w = market.fit_blend(noise, truth, y)
        self.assertGreater(w[1], 0.8)
        self.assertLess(w[0], 0.3)

    def test_roi_table(self):
        wf = pd.DataFrame({"p_model": [0.6, 0.3], "p_market": [0.5, 0.5],
                           "dec_a": [2.0, 2.0], "dec_b": [2.0, 2.0], "y": [1.0, 1.0]})
        roi = market.roi_table(wf, "p_model", thresholds=(0.05,)).iloc[0]
        # bets: fight 1 side A (wins +1), fight 2 side B (loses -1)
        self.assertEqual(roi["bets"], 2)
        self.assertAlmostEqual(roi["profit (units)"], 0.0)


class OddsMatchingTests(unittest.TestCase):
    def test_matches_renamed_fighters_and_aligns_sides(self):
        fights = pd.DataFrame({
            "fight_id": ["f1", "f2"],
            "date": pd.to_datetime(["2023-08-19", "2023-08-19"]),
            "fighter_a": ["Ian Machado Garry", "Some One"],
            "fighter_b": ["Neil Magny", "Other Guy"],
        })
        raw = pd.DataFrame({
            "event_date": ["2023-08-19", "2023-08-19"],
            "fighter1": ["Neil Magny", "Some One"], "fighter2": ["Ian Garry", "Other Guy"],
            "favourite": ["Ian Garry", "Some One"], "underdog": ["Neil Magny", "Other Guy"],
            "favourite_odds": [1.3, 1.5], "underdog_odds": [3.6, 2.7],
        })
        old = config.RAW_DIR
        with tempfile.TemporaryDirectory() as tmp:
            config.RAW_DIR = Path(tmp)
            try:
                raw.to_csv(Path(tmp) / config.ODDS_FILE, index=False)
                out = market.build_odds(fights, verbose=False).set_index("fight_id")
            finally:
                config.RAW_DIR = old
        self.assertEqual(out.loc["f1", "dec_a"], 1.3)  # Garry is our fighter_a and the favourite
        self.assertEqual(out.loc["f1", "dec_b"], 3.6)
        self.assertEqual(out.loc["f2", "dec_a"], 1.5)


if __name__ == "__main__":
    unittest.main()
