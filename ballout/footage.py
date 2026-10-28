"""Where to watch a fight.

The UFC owns its fight footage (full fights live on UFC Fight Pass, plus free
fights and highlights on the official UFC YouTube channel), so the tool links
to those sources instead of downloading or re-hosting video.
"""

from __future__ import annotations

import urllib.parse

import pandas as pd


def _q(text: str) -> str:
    return urllib.parse.quote_plus(text)


def links(fighter: str, opponent: str, event: str | None = None) -> dict[str, str]:
    """Search links for one fight, best source first."""
    a, b = fighter.split()[-1], opponent.split()[-1]
    pair = f"{fighter} vs {opponent}"
    return {
        "UFC YouTube": f"https://www.youtube.com/@UFC/search?query={urllib.parse.quote(f'{a} {b}')}",
        "UFC Fight Pass": "https://www.google.com/search?q=" + _q(f"site:ufcfightpass.com {a} {b}"),
        "YouTube": "https://www.youtube.com/results?search_query=" + _q(f"{pair} {event or 'UFC'} full fight"),
    }


def fighter_links(fighter: str) -> dict[str, str]:
    """Highlight reels and fight library for one fighter."""
    return {
        "UFC YouTube": f"https://www.youtube.com/@UFC/search?query={urllib.parse.quote(fighter)}",
        "UFC Fight Pass": "https://www.google.com/search?q=" + _q(f"site:ufcfightpass.com {fighter}"),
        "YouTube highlights": "https://www.youtube.com/results?search_query=" + _q(f"{fighter} UFC highlights"),
    }


def fight_log_links(log: pd.DataFrame) -> pd.DataFrame:
    """Fight log (from Database.fight_log) with a watch link per fight."""
    out = log[["date", "opponent", "result", "method", "event"]].copy()
    out["watch (UFC YouTube)"] = [links(f, o, e)["UFC YouTube"]
                                  for f, o, e in zip(log["fighter"], log["opponent"], log["event"])]
    out["watch (YouTube)"] = [links(f, o, e)["YouTube"]
                              for f, o, e in zip(log["fighter"], log["opponent"], log["event"])]
    return out
