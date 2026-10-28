import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from ballout import bfo, config, settings, upcoming


def _lines():
    rows = []
    for book, d1, d2 in (("FanDuel", 1.80, 2.05), ("DraftKings", 1.90, 1.95), ("Kalshi", 1.70, 2.30)):
        rows += [{"matchup_id": 7, "side": 1, "fighter": "Fighter One", "book": book, "dec": d1},
                 {"matchup_id": 7, "side": 2, "fighter": "Fighter Two", "book": book, "dec": d2}]
    return pd.DataFrame(rows)


class TempDataDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = config.DATA_DIR
        config.DATA_DIR = Path(self._tmp.name)

    def tearDown(self):
        config.DATA_DIR = self._old
        self._tmp.cleanup()


class SettingsTests(TempDataDir):
    def test_default_is_every_sportsbook_without_prediction_markets(self):
        self.assertEqual(settings.books(), settings.SPORTSBOOKS)

    def test_set_books_normalises_names_and_resets(self):
        self.assertEqual(settings.set_books(["fanduel", "DRAFTKINGS", "fanduel"]), ["FanDuel", "DraftKings"])
        self.assertEqual(settings.books(), ["FanDuel", "DraftKings"])
        self.assertEqual(settings.set_books(None), settings.SPORTSBOOKS)


class BestPriceTests(unittest.TestCase):
    def test_best_price_only_from_chosen_books(self):
        rows = bfo.book_lines(_lines())
        mine = bfo.best_prices(rows, ["FanDuel", "DraftKings"])
        self.assertEqual((mine["dec1"], mine["book1"]), (1.90, "DraftKings"))
        self.assertEqual((mine["dec2"], mine["book2"]), (2.05, "FanDuel"))
        self.assertEqual(set(mine["lines"]), {"FanDuel", "DraftKings"})
        self.assertEqual(bfo.best_prices(rows, ["kalshi"])["dec2"], 2.30)  # chosen on purpose: allowed

    def test_no_chosen_book_gives_no_price(self):
        mine = bfo.best_prices(bfo.book_lines(_lines()), ["BetMGM"])
        self.assertTrue(pd.isna(mine["dec1"]))
        self.assertEqual(mine["lines"], {})


class AnalyseUsesChosenBooksTests(TempDataDir):
    def test_ev_and_best_price_follow_the_selection(self):
        lines = _lines()
        event = {"name": "UFC 999", "date": pd.Timestamp("2026-11-01"), "url": "u", "lines": lines,
                 "props": pd.DataFrame(), "consensus": bfo.consensus(lines),
                 "book_lines": bfo.book_lines(lines), "prop_consensus": pd.DataFrame(), "fighters": {}}
        db = mock.Mock(blend_weights=None)
        db.find_strict.return_value = None  # debutants: market price only
        with mock.patch.object(bfo, "upcoming", return_value=[event]):
            (ea,) = upcoming.analyse(db, books=["FanDuel"], verbose=False)
        f = ea.fights.iloc[0]
        self.assertEqual((f.dec2_best, f.book2_best), (2.05, "FanDuel"))
        self.assertAlmostEqual(f.ev2, (1 - f.p1_est) * 2.05 - 1)
        self.assertEqual(set(f.lines), {"FanDuel"})


if __name__ == "__main__":
    unittest.main()
