import json
import unittest
import zlib

import numpy as np
import pandas as pd

from ballout import web


class WebTests(unittest.TestCase):
    def test_clean_makes_everything_json_safe(self):
        df = pd.DataFrame({"x": [1.5, np.nan], "d": [pd.Timestamp("2026-11-01"), pd.NaT]})
        out = web.clean({"df": df, "n": np.int64(3), "f": np.float64("inf"), "b": np.bool_(True),
                         "date": pd.Timestamp("2026-11-01").date()})
        json.dumps(out)  # must not raise
        self.assertEqual(out["df"][0], {"x": 1.5, "d": "2026-11-01T00:00:00"})
        self.assertEqual(out["df"][1], {"x": None, "d": None})
        self.assertEqual((out["n"], out["f"], out["b"], out["date"]), (3, None, True, "2026-11-01"))

    def test_icon_is_a_valid_png(self):
        png = web._png(32)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        idat = png[png.index(b"IDAT") + 4:png.index(b"IEND") - 8]
        self.assertEqual(len(zlib.decompress(idat)), 32 * (1 + 32 * 3))

    def test_page_is_served_from_module(self):
        from ballout.webpage import INDEX_HTML
        self.assertIn("apple-touch-icon", INDEX_HTML)
        self.assertIn("/api/upcoming", INDEX_HTML.replace("api('upcoming'", "/api/upcoming"))


if __name__ == "__main__":
    unittest.main()
