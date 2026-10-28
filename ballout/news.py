"""Fighter news with risk flags (injury, withdrawal, weight, suspension).

The market moves on news the fight stats can't see, so before a bet it's
worth scanning each fighter's recent headlines. Sources:

* Google News RSS search per fighter (headlines from ESPN, MMA Fighting,
  MMA Junkie, Sherdog, Yahoo, etc.)
* ESPN's UFC news feed and Sherdog's RSS feed for general headlines
"""

from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

USER_AGENT = "ballout/0.2 (personal UFC research tool)"
GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
ESPN_NEWS = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/news?limit=50"
SHERDOG_RSS = "https://www.sherdog.com/rss/news.xml"
DELAY = 0.5

# Headline phrases that usually move a betting line.
FLAGS = {
    "injury": (r"injur|\bhurt (his|her|in)\b|was hurt|surgery|torn|\btear\b|broken|fractur|\bacl\b|"
               r"concussion|hospital|illness|\bsick\b|staph|medical(ly)? (issue|suspen|clear)"),
    "withdrawal": (r"withdr[ae]w|pull(s|ed)? out|\bout (of|for|as|after|indefinitely)\b|\bis out\b|\bout\s*$|"
                   r"off the card|scrapped|cancel|replace|steps? in|short[- ]notice|falls? through|"
                   r"declin|turn(s|ed|ing)? down|absence"),
    "weight": r"miss(es|ed)? weight|weigh[- ]?ins?\b|weight cut|overweight|catch ?weight|on weight",
    "legal/suspension": r"suspen(d|sion)|usada|drug test|positive test|banned|arrest|charged|visa|lawsuit",
}
_FLAG_RE = {k: re.compile(v, re.I) for k, v in FLAGS.items()}

_last = 0.0


@dataclass
class Headline:
    title: str
    source: str
    published: pd.Timestamp
    url: str
    flags: list = field(default_factory=list)


def flags_for(title: str) -> list[str]:
    return [k for k, rx in _FLAG_RE.items() if rx.search(title)]


def _get(session: requests.Session, url: str) -> str:
    global _last
    wait = DELAY - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    resp = session.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    _last = time.time()
    resp.raise_for_status()
    return resp.text


def _parse_rss(xml: str, default_source: str = "") -> list[Headline]:
    soup = BeautifulSoup(xml, "xml")
    out = []
    for item in soup.find_all("item"):
        title = item.title.get_text(strip=True) if item.title else ""
        source = item.source.get_text(strip=True) if item.find("source") else default_source
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        try:
            published = pd.Timestamp(parsedate_to_datetime(item.pubDate.get_text(strip=True))).tz_convert(None)
        except (AttributeError, TypeError, ValueError):
            published = pd.NaT
        url = item.link.get_text(strip=True) if item.link else ""
        out.append(Headline(title, source, published, url, flags_for(title)))
    return out


def fighter_news(name: str, days: int = 30, session: requests.Session | None = None,
                 limit: int = 8) -> list[Headline]:
    """Recent headlines mentioning the fighter, newest first.

    Flags are only kept when the headline names the fighter (by surname), so
    a story about their opponent's injury doesn't flag them."""
    session = session or requests.Session()
    q = urllib.parse.quote_plus(f'"{name}" UFC when:{days}d')
    try:
        items = _parse_rss(_get(session, GOOGLE_NEWS.format(q=q)))
    except requests.RequestException:
        return []
    surname = name.split()[-1].lower()
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    seen, out = set(), []
    for h in sorted(items, key=lambda h: h.published if not pd.isna(h.published) else pd.Timestamp(0),
                    reverse=True):
        key = h.title.lower()[:60]
        if key in seen or (not pd.isna(h.published) and h.published < cutoff):
            continue
        seen.add(key)
        if surname not in h.title.lower():
            h.flags = []
        out.append(h)
    return out[:limit]


def general_news(limit: int = 30, session: requests.Session | None = None) -> list[Headline]:
    """Latest UFC/MMA headlines from ESPN and Sherdog, newest first."""
    session = session or requests.Session()
    out: list[Headline] = []
    try:
        data = requests.get(ESPN_NEWS, timeout=30, headers={"User-Agent": USER_AGENT}).json()
        for a in data.get("articles", []):
            title = a.get("headline", "")
            out.append(Headline(title, "ESPN", pd.Timestamp(a.get("published")).tz_convert(None)
                                if a.get("published") else pd.NaT,
                                a.get("links", {}).get("web", {}).get("href", ""), flags_for(title)))
    except (requests.RequestException, ValueError):
        pass
    try:
        out += _parse_rss(_get(session, SHERDOG_RSS), "Sherdog")
    except requests.RequestException:
        pass
    out.sort(key=lambda h: h.published if not pd.isna(h.published) else pd.Timestamp(0), reverse=True)
    return out[:limit]


def summarize_flags(headlines: list[Headline]) -> str:
    """'injury (2), withdrawal (1)' or '' for clean news."""
    counts: dict[str, int] = {}
    for h in headlines:
        for f in h.flags:
            counts[f] = counts.get(f, 0) + 1
    return ", ".join(f"{k} ({v})" for k, v in counts.items())
