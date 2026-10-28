import unittest

from ballout import news


class FlagTests(unittest.TestCase):
    def test_flags(self):
        cases = {
            "Islam Makhachev Out for UFC 336 as Prates vs. Morales headlines": ["withdrawal"],
            "UFC Slammed for Interim Title Move with Islam Makhachev Out": ["withdrawal"],
            "Henry Cejudo Agrees With Makhachev Turning Down Prates": ["withdrawal"],
            "Fighter X misses weight by 3 pounds ahead of UFC 334": ["weight"],
            "Fighter Y suffers torn ACL, replaced on short notice": ["injury", "withdrawal"],
            "Fighter Z receives six-month USADA suspension": ["legal/suspension"],
            "Malcolm Wellmaker says UFC loss 'hurts' after team move": [],
            "Carlos Prates' coach says Michael Morales won't make it to Round 3": [],
            "Sean O'Malley calls out Merab after knockout win": [],
        }
        for title, expected in cases.items():
            self.assertEqual(sorted(news.flags_for(title)), sorted(expected), title)

    def test_parse_google_rss(self):
        xml = """<?xml version="1.0"?><rss><channel><item>
          <title>Makhachev out of UFC 336 - ESPN</title>
          <link>https://example.com/a</link>
          <pubDate>Sat, 24 Oct 2026 20:09:00 GMT</pubDate>
          <source url="https://espn.com">ESPN</source>
        </item></channel></rss>"""
        (h,) = news._parse_rss(xml)
        self.assertEqual(h.title, "Makhachev out of UFC 336")
        self.assertEqual(h.source, "ESPN")
        self.assertEqual(h.published.year, 2026)
        self.assertEqual(h.flags, ["withdrawal"])


if __name__ == "__main__":
    unittest.main()
