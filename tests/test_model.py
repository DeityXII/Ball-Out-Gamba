import unittest

import numpy as np
import pandas as pd

from ballout import features, model


class ModelTests(unittest.TestCase):
    def test_logistic_recovers_signal(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(4000, 2))
        y = (rng.random(4000) < 1 / (1 + np.exp(-(1.5 * X[:, 0])))).astype(float)
        w = model.fit_logistic(X, y, l2=0.1)
        self.assertAlmostEqual(w[0], 1.5, delta=0.2)
        self.assertAlmostEqual(w[1], 0.0, delta=0.15)

    def test_win_model_is_symmetric(self):
        rng = np.random.default_rng(1)
        n = 500
        rows = pd.DataFrame({c: rng.normal(size=n) for c in model.DIFF_COLS})
        rows["result_a"] = np.where(rows["d_elo"] + rng.normal(size=n) > 0, "W", "L")
        rows["date"] = pd.Timestamp("2015-01-01")
        m = model.train_win_model(rows)
        d = {c: float(v) for c, v in rows.iloc[0][model.DIFF_COLS].items()}
        flipped = {c: -v for c, v in d.items()}
        self.assertAlmostEqual(m.predict(d)[0] + m.predict(flipped)[0], 1.0)

    def test_method_probs_sum_to_one(self):
        base = {"KO": 0.33, "SUB": 0.2, "DEC": 0.47}
        mp = model.method_probs(0.6, {"KO": 5, "SUB": 0, "DEC": 1}, {"KO": 0, "SUB": 1, "DEC": 1},
                                {"KO": 0, "SUB": 3, "DEC": 3}, {"KO": 2, "SUB": 0, "DEC": 2}, base)
        total = sum(v for k, v in mp.items() if k != "distance")
        self.assertAlmostEqual(total, 1.0)
        self.assertGreater(mp["A_KO"], mp["A_SUB"])  # a KO artist vs someone who gets KO'd


class FighterStateTests(unittest.TestCase):
    def test_streak(self):
        st = features.FighterState("x", "X")
        st.results = ["L", "W", "W", "NC", "W"]
        self.assertEqual(st.streak, 3)
        st.results = ["W", "L", "L"]
        self.assertEqual(st.streak, -2)

    def test_shrinkage_toward_population(self):
        st = features.FighterState("x", "X")
        self.assertAlmostEqual(st.slpm, features.POP["slpm"])
        self.assertAlmostEqual(st.win_rate, 0.5)


if __name__ == "__main__":
    unittest.main()
