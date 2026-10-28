import unittest

import pandas as pd

from ballout import bfo, upcoming

PAGE = """
<div class="table-header"><a href="/events/ufc-999-1"><h1>UFC 999 Odds</h1></a></div>
<table class="odds-table odds-table-responsive-header"><tbody></tbody></table>
<table class="odds-table">
 <thead><tr><th></th>
  <th data-b="21"><a href="#">FanDuel</a></th>
  <th data-b="24"><a href="#">Caesars</a></th>
  <th data-b="29"><a href="#">Kalshi</a></th>
 </tr></thead>
 <tbody>
  <tr><th data-admin-matchup="7"><a href="/fighters/a-1"><span>Fighter One</span></a></th>
   <td data-li="[21,1,7]"><span>-150</span></td><td data-li="[24,1,7]"><span>-140</span></td>
   <td data-li="[29,1,7]"><span>+900</span></td></tr>
  <tr><th><a href="/fighters/b-2"><span>Fighter Two</span></a></th>
   <td data-li="[21,2,7]"><span>+130</span></td><td data-li="[24,2,7]"><span>+120</span></td>
   <td data-li="[29,2,7]"><span>+4566</span></td></tr>
  <tr class="pr"><th>Fight goes to decision</th>
   <td data-li="[21,1,7,1,0]"><span>-120</span></td><td data-li="[24,1,7,1,0]"><span>-110</span></td><td></td></tr>
  <tr class="pr"><th>Fight doesn't go to decision</th>
   <td data-li="[21,2,7,1,0]"><span>-110</span></td><td data-li="[24,2,7,1,0]"><span>-120</span></td><td></td></tr>
  <tr><th data-admin-matchup="8"><a href="/fighters/c-3"><span>No Odds Yet</span></a></th><td></td></tr>
  <tr><th><a href="/fighters/d-4"><span>Also None</span></a></th><td></td></tr>
 </tbody>
</table>
"""


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.parsed = bfo.parse_event(PAGE)

    def test_lines_and_props(self):
        self.assertEqual(self.parsed["name"], "UFC 999")
        self.assertEqual(len(self.parsed["lines"]), 6)
        self.assertEqual(set(self.parsed["lines"]["book"]), {"FanDuel", "Caesars", "Kalshi"})
        self.assertEqual(len(self.parsed["props"]), 4)

    def test_consensus_ignores_prediction_markets(self):
        c = bfo.consensus(self.parsed["lines"]).iloc[0]
        self.assertEqual((c.fighter1, c.fighter2), ("Fighter One", "Fighter Two"))
        self.assertEqual(c.books, 2)  # Kalshi's +900/+4566 is left out
        self.assertAlmostEqual(c.dec2_best, 2.3)
        self.assertEqual(c.book2_best, "FanDuel")
        self.assertTrue(0.55 < c.p1_market < 0.6)

    def test_prop_consensus(self):
        pc = bfo.prop_consensus(self.parsed["props"]).iloc[0]
        self.assertAlmostEqual(pc.p_decision, 0.5, places=6)  # -120/-110 and -110/-120 average out

    def test_fighters_include_unpriced_matchups(self):
        self.assertEqual(bfo.fighters_by_matchup(PAGE)[8], ("No Odds Yet", "Also None"))


class ValueBetTests(unittest.TestCase):
    def _event(self, date, best1=2.6, median1=2.2):
        fights = pd.DataFrame([{
            "fighter1": "A", "fighter2": "B", "p1_est": 0.45, "p1_market": 0.43, "p1_model": 0.5,
            "dec1_best": best1, "book1_best": "X", "dec2_best": 1.6, "book2_best": "Y",
            "dec1_median": median1, "dec2_median": 1.6,
            "ev1": 0.45 * best1 - 1, "ev2": 0.55 * 1.6 - 1, "kelly1": 0.02, "kelly2": 0.0,
            "stake1": float("nan"), "stake2": float("nan"),
        }])
        return upcoming.EventAnalysis("UFC 999", date, "url", fights)

    def test_value_bets_and_stale_flag(self):
        vb = upcoming.value_bets([self._event(pd.Timestamp("2026-11-01"))], 0.05)
        self.assertEqual(list(vb["bet"]), ["A"])
        self.assertIn("stale", vb.iloc[0]["check"])  # 2.6 vs typical 2.2 is a 7-point gap

    def test_undated_events_never_produce_value_bets(self):
        self.assertTrue(upcoming.value_bets([self._event(pd.NaT)], 0.05).empty)


if __name__ == "__main__":
    unittest.main()
