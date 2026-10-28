"""Betting lines from BestFightOdds.com (robots.txt allows crawling).

* Upcoming UFC events: live moneylines from every listed sportsbook and
  prediction market, plus props (goes to decision, method of victory, rounds).
* Completed UFC events (2023 onward; older pages no longer show odds):
  closing lines, used to extend the historical odds that the market blend
  and ROI backtest are built on.

Requests are spaced DELAY seconds apart. Completed events are parsed once and
cached in data/raw/bfo/ so later updates only fetch new or upcoming events.
"""

from __future__ import annotations

import html as htmllib
import json
import re
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

from . import config, odds

BASE = "https://www.bestfightodds.com"
USER_AGENT = "ballout/0.2 (personal UFC research tool; +https://github.com/DeityXII/Ball-Out-Gamba)"
DELAY = 1.0
HISTORY_START = "2023-01-01"  # pages before this no longer show any odds
FUTURE_EVENTS_SLUG = "future-events"
_EXCLUDE = re.compile(r"/events/ufc-bjj|grappling|invitational")

_last_request = 0.0


@dataclass
class EventRef:
    url: str
    date: pd.Timestamp

    @property
    def slug(self) -> str:
        return self.url.rstrip("/").rsplit("/", 1)[-1]


def _get(session: requests.Session, url: str) -> str:
    global _last_request
    wait = DELAY - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    for attempt in range(4):
        try:
            resp = session.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
            _last_request = time.time()
            resp.raise_for_status()
            return resp.text
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))


def _sitemap(session: requests.Session) -> str:
    if not hasattr(session, "_bfo_sitemap"):
        session._bfo_sitemap = _get(session, f"{BASE}/sitemap-events.xml")
    return session._bfo_sitemap


def list_ufc_events(session: requests.Session) -> list[EventRef]:
    """Every UFC event page on the site, with its date, from the sitemap."""
    xml = _sitemap(session)
    out = []
    for loc, lastmod in re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", xml):
        if "/events/ufc" in loc and not _EXCLUDE.search(loc):
            out.append(EventRef(loc, pd.Timestamp(lastmod[:10])))
    return sorted(out, key=lambda e: e.date)


def future_events_ref(session: requests.Session) -> EventRef | None:
    """The catch-all page of announced fights that have no event date yet."""
    xml = _sitemap(session)
    m = re.search(r"<loc>([^<]*/events/future-events[^<]*)</loc>", xml)
    return EventRef(m.group(1), pd.NaT) if m else None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _price(td) -> float | None:
    span = td.find("span")
    text = span.get_text(strip=True) if span else td.get_text(strip=True)
    try:
        return odds.parse_odds(text)
    except ValueError:
        return None


def parse_event(page: str) -> dict:
    """-> {"name", "lines": DataFrame, "props": DataFrame}.

    lines: matchup_id, side (1/2), fighter, book, dec
    props: matchup_id, prop_type, team, side, label, book, dec
      (side 1 is the "yes"/"over" leg, side 2 its complement)
    """
    soup = BeautifulSoup(page, "lxml")
    h1 = soup.select_one(".table-header h1")
    name = h1.get_text(" ", strip=True).removesuffix(" Odds") if h1 else ""
    tables = soup.select("table.odds-table")
    lines, props = [], []
    for table in tables:
        if "odds-table-responsive-header" in (table.get("class") or []):
            continue
        books = {th.get("data-b"): th.find("a").get_text(strip=True) if th.find("a") else th.get_text(strip=True)
                 for th in table.select("thead th[data-b]")}
        for tr in table.select("tbody tr"):
            th = tr.find("th")
            if th is None:
                continue
            label = htmllib.unescape(th.get_text(" ", strip=True))
            is_prop = "pr" in (tr.get("class") or [])
            for td in tr.select("td[data-li]"):
                try:
                    li = json.loads(td["data-li"])
                except (ValueError, KeyError):
                    continue
                dec = _price(td)
                if dec is None:
                    continue
                book = books.get(str(li[0]), str(li[0]))
                if is_prop and len(li) >= 5:
                    props.append({"matchup_id": li[2], "prop_type": li[3], "team": li[4], "side": li[1],
                                  "label": label, "book": book, "dec": dec})
                elif not is_prop and len(li) == 3:
                    lines.append({"matchup_id": li[2], "side": li[1], "fighter": label, "book": book, "dec": dec})
    return {"name": name, "lines": pd.DataFrame(lines, columns=["matchup_id", "side", "fighter", "book", "dec"]),
            "props": pd.DataFrame(props, columns=["matchup_id", "prop_type", "team", "side", "label", "book", "dec"])}


def fighters_by_matchup(page: str) -> dict[int, tuple[str, str]]:
    """Matchup id -> (fighter 1, fighter 2), including fights with no odds yet."""
    soup = BeautifulSoup(page, "lxml")
    out: dict[int, list] = {}
    for table in soup.select("table.odds-table"):
        if "odds-table-responsive-header" in (table.get("class") or []):
            continue
        current = None
        for tr in table.select("tbody tr"):
            if "pr" in (tr.get("class") or []):
                continue
            th = tr.find("th")
            if th is None or th.find("a", href=re.compile("/fighters/")) is None:
                continue
            mu = th.get("data-admin-matchup")
            if mu is not None:
                current = int(mu)
                out[current] = [th.get_text(" ", strip=True)]
            elif current is not None and len(out[current]) == 1:
                out[current].append(th.get_text(" ", strip=True))
    return {k: tuple(v) for k, v in out.items() if len(v) == 2}


# Prediction-market quotes are often thin (e.g. +4566 on a coin flip), so they
# are left out of consensus prices and best-line shopping.
EXCHANGES = {"Polymarket", "Kalshi"}
# BestFightOdds prop type ids
PROP_DECISION = 1        # "Fight goes to decision" (two-way)
PROP_KO, PROP_SUB = 8, 9  # "<fighter> wins by TKO/KO / submission" (one-way), team 1/2
PROP_WINS_DEC = 11       # "<fighter> wins by decision" (two-way), team 1/2


def _sane_two_way(wide: pd.DataFrame) -> pd.DataFrame:
    """Rows (books) quoting both sides with a plausible margin, sportsbooks only."""
    both = wide.dropna()
    both = both[~both.index.isin(EXCHANGES)]
    over = 1 / both[1] + 1 / both[2] - 1
    return both[(over > -0.01) & (over < 0.15)]


def consensus(lines: pd.DataFrame) -> pd.DataFrame:
    """One row per matchup: fighters, median no-vig probability across books,
    median and best price per side (with the book offering it)."""
    rows = []
    for mu, grp in lines.groupby("matchup_id"):
        names = grp.groupby("side")["fighter"].first()
        if 1 not in names or 2 not in names:
            continue
        wide = grp.pivot_table(index="book", columns="side", values="dec", aggfunc="last")
        if 1 not in wide or 2 not in wide:
            continue
        both = _sane_two_way(wide)
        if both.empty:
            continue
        p1 = (1 / both[1]) / (1 / both[1] + 1 / both[2])
        rows.append({
            "matchup_id": int(mu), "fighter1": names[1], "fighter2": names[2],
            "p1_market": float(p1.median()), "books": int(len(both)),
            "dec1_median": float(both[1].median()), "dec2_median": float(both[2].median()),
            "dec1_best": float(both[1].max()), "book1_best": both[1].idxmax(),
            "dec2_best": float(both[2].max()), "book2_best": both[2].idxmax(),
        })
    return pd.DataFrame(rows)


def book_lines(lines: pd.DataFrame) -> pd.DataFrame:
    """Every book's current price on both fighters, one row per matchup and book.

    Columns: matchup_id, book, dec1, dec2. Quotes with an implausible margin
    (stale or broken) are dropped; prediction markets are kept so they can be
    chosen in Settings."""
    rows = []
    for mu, grp in lines.groupby("matchup_id"):
        wide = grp.pivot_table(index="book", columns="side", values="dec", aggfunc="last")
        if 1 not in wide or 2 not in wide:
            continue
        both = wide.dropna()
        over = 1 / both[1] + 1 / both[2] - 1
        for book, r in both[(over > -0.01) & (over < 0.15)].iterrows():
            rows.append({"matchup_id": int(mu), "book": book, "dec1": float(r[1]), "dec2": float(r[2])})
    return pd.DataFrame(rows, columns=["matchup_id", "book", "dec1", "dec2"])


def best_prices(book_rows: pd.DataFrame, books: list[str]) -> dict:
    """Best price on each fighter among the chosen books (case-insensitive).

    -> {"dec1", "book1", "dec2", "book2", "lines": {book: (dec1, dec2)}}; prices
    are NaN when none of the chosen books has posted the fight."""
    wanted = {b.lower() for b in books}
    mine = book_rows[book_rows["book"].str.lower().isin(wanted)]
    out = {"dec1": float("nan"), "book1": None, "dec2": float("nan"), "book2": None,
           "lines": {r.book: (r.dec1, r.dec2) for r in mine.itertuples()}}
    if len(mine):
        i1, i2 = mine["dec1"].idxmax(), mine["dec2"].idxmax()
        out.update(dec1=float(mine.at[i1, "dec1"]), book1=mine.at[i1, "book"],
                   dec2=float(mine.at[i2, "dec2"]), book2=mine.at[i2, "book"])
    return out


def prop_consensus(props: pd.DataFrame) -> pd.DataFrame:
    """Per matchup, the market's view of how the fight ends.

    Columns: matchup_id, p_decision (no-vig, "fight goes to decision") and the
    six-way method split p_1_KO, p_1_SUB, p_1_DEC, p_2_KO, p_2_SUB, p_2_DEC,
    built per book from the KO / submission / decision props with the margin
    removed, then the median across books. Also the best price on each leg.
    """
    cols = ["matchup_id", "p_decision", "dec_decision_best", "dec_no_decision_best"]
    if props.empty:
        return pd.DataFrame(columns=cols)
    props = props[~props["book"].isin(EXCHANGES)]
    rows = []
    for mu, grp in props.groupby("matchup_id"):
        rec = {"matchup_id": int(mu)}
        dec = grp[grp["prop_type"] == PROP_DECISION].pivot_table(index="book", columns="side", values="dec", aggfunc="last")
        if 1 in dec and 2 in dec:
            both = _sane_two_way(dec)
            if not both.empty:
                rec["p_decision"] = float(((1 / both[1]) / (1 / both[1] + 1 / both[2])).median())
                rec["dec_decision_best"] = float(both[1].max())
                rec["dec_no_decision_best"] = float(both[2].max())
        # six-way method split, per book
        legs = {(PROP_KO, 1): "1_KO", (PROP_SUB, 1): "1_SUB", (PROP_WINS_DEC, 1): "1_DEC",
                (PROP_KO, 2): "2_KO", (PROP_SUB, 2): "2_SUB", (PROP_WINS_DEC, 2): "2_DEC"}
        yes = grp[grp["side"] == 1]
        per_book = []
        for book, bk in yes.groupby("book"):
            prices = {legs[k]: float(r) for k, r in
                      bk.set_index(["prop_type", "team"])["dec"].items() if k in legs}
            if len(prices) == 6:
                imp = {k: 1 / v for k, v in prices.items()}
                tot = sum(imp.values())
                per_book.append({k: v / tot for k, v in imp.items()})
        if per_book:
            med = pd.DataFrame(per_book).median()
            med = med / med.sum()
            rec.update({f"p_{k}": float(v) for k, v in med.items()})
            rec["method_books"] = len(per_book)
            best = yes[yes.set_index(["prop_type", "team"]).index.isin(list(legs))]
            for (pt, team), g in best.groupby(["prop_type", "team"]):
                rec[f"dec_{legs[(pt, team)]}_best"] = float(g["dec"].max())
        rows.append(rec)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Fetching with cache
# ---------------------------------------------------------------------------

def _cache_dir():
    d = config.RAW_DIR / "bfo"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch_event(session: requests.Session, ev: EventRef, use_cache: bool) -> dict:
    """Parsed event; completed events are cached as CSV and never refetched."""
    d = _cache_dir()
    lines_p, props_p, meta_p = d / f"{ev.slug}.lines.csv", d / f"{ev.slug}.props.csv", d / f"{ev.slug}.json"
    if use_cache and lines_p.exists() and meta_p.exists():
        meta = json.loads(meta_p.read_text())
        return {"name": meta["name"], "lines": pd.read_csv(lines_p), "props": pd.read_csv(props_p),
                "fighters": {int(k): tuple(v) for k, v in meta.get("fighters", {}).items()}}
    page = _get(session, ev.url)
    parsed = parse_event(page)
    parsed["fighters"] = fighters_by_matchup(page)
    if use_cache:
        parsed["lines"].to_csv(lines_p, index=False)
        parsed["props"].to_csv(props_p, index=False)
        meta_p.write_text(json.dumps({"name": parsed["name"], "url": ev.url, "date": str(ev.date.date()),
                                      "fighters": {str(k): v for k, v in parsed["fighters"].items()}}))
    return parsed


def update_history(verbose: bool = True) -> pd.DataFrame:
    """Fetch closing lines for completed UFC events since HISTORY_START.

    Returns one row per matchup: date, fighter1/2, dec1/dec2 (median price
    across books), p1_market, books, plus best prices."""
    session = requests.Session()
    today = pd.Timestamp.today().normalize()
    events = [e for e in list_ufc_events(session)
              if pd.Timestamp(HISTORY_START) <= e.date < today - pd.Timedelta(days=1)]
    cached = {p.name.removesuffix(".json") for p in _cache_dir().glob("*.json")}
    todo = [e for e in events if e.slug not in cached]
    if verbose and todo:
        print(f"  fetching {len(todo)} completed UFC events from BestFightOdds "
              f"(~{len(todo) * (DELAY + 0.8) / 60:.0f} min the first time, cached afterwards)")
    rows = []
    for i, ev in enumerate(events):
        try:
            parsed = fetch_event(session, ev, use_cache=True)
        except requests.RequestException as e:
            if verbose:
                print(f"  warning: skipped {ev.url} ({e})")
            continue
        if verbose and ev.slug not in cached and (i % 25 == 0):
            print(f"    ... {ev.date:%Y-%m-%d} {parsed['name']}")
        cons = consensus(parsed["lines"])
        if not cons.empty:
            cons["date"] = ev.date
            cons["event"] = parsed["name"]
            rows.append(cons)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def upcoming(include_unscheduled: bool = True) -> list[dict]:
    """Live odds for upcoming UFC events (always refetched).

    Returns a list of {"name", "date", "url", "lines", "props", "consensus",
    "prop_consensus", "fighters"}; the undated "future events" page comes last."""
    session = requests.Session()
    today = pd.Timestamp.today().normalize()
    refs = [e for e in list_ufc_events(session) if e.date >= today - pd.Timedelta(days=1)]
    if include_unscheduled:
        fut = future_events_ref(session)
        if fut:
            refs.append(fut)
    out = []
    for ev in refs:
        parsed = fetch_event(session, ev, use_cache=False)
        parsed.update({"date": ev.date, "url": ev.url,
                       "consensus": consensus(parsed["lines"]),
                       "book_lines": book_lines(parsed["lines"]),
                       "prop_consensus": prop_consensus(parsed["props"])})
        if pd.isna(ev.date):
            parsed["name"] = "Announced fights without a date (all promotions)"
        out.append(parsed)
    return out
