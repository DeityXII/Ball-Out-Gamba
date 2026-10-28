"""Analyse upcoming UFC cards straight from live sportsbook lines.

For every scheduled fight: the market's consensus probability (all
sportsbooks), our stats model, the model+market blend, the best price on each
fighter among the sportsbooks you chose in Settings (and which book has it),
every chosen book's line, expected value and stake at the best price, the market's
method-of-victory and goes-the-distance probabilities from the props, line
movement since we first saw the fight, and optional news flags.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import bfo, config, hype, market, news, odds, settings
from .analysis import Database

SNAPSHOTS = "odds_snapshots.csv"
_snapshot_lock = threading.Lock()  # the web app can run two analyses at once


@dataclass
class EventAnalysis:
    name: str
    date: pd.Timestamp
    url: str
    fights: pd.DataFrame
    news: dict = field(default_factory=dict)  # fighter -> list[Headline]


def _snapshot(events: list[dict]) -> pd.DataFrame:
    """Append current consensus lines to the snapshot log and return the log."""
    with _snapshot_lock:
        return _snapshot_locked(events)


def _snapshot_locked(events: list[dict]) -> pd.DataFrame:
    path = config.DATA_DIR / SNAPSHOTS
    now = pd.Timestamp.now().floor("min")
    frames = []
    for ev in events:
        c = ev["consensus"]
        if c.empty:
            continue
        frames.append(c[["matchup_id", "fighter1", "fighter2", "p1_market", "dec1_best", "dec2_best"]]
                      .assign(seen_at=now, event=ev["name"]))
    log = pd.read_csv(path, parse_dates=["seen_at"]) if path.exists() else pd.DataFrame()
    if frames:
        log = pd.concat([log] + frames, ignore_index=True)
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        log.to_csv(path, index=False)
    return log


def analyse(db: Database, event_filter: str | None = None, include_unscheduled: bool = False,
            with_news: bool = False, news_days: int = 21, bankroll: float | None = None,
            kelly_mult: float = 0.25, max_stake: float = 0.05, verbose: bool = True,
            books: list[str] | None = None) -> list[EventAnalysis]:
    books = books or settings.books()
    events = bfo.upcoming(include_unscheduled=include_unscheduled)
    if event_filter:
        q = event_filter.lower()
        events = [e for e in events if q in e["name"].lower() or q in e["url"].lower()]
    log = _snapshot(events)
    weights = db.blend_weights
    session = None
    out = []
    for ev in events:
        cons, props = ev["consensus"], ev["prop_consensus"]
        unscheduled = pd.isna(ev["date"])
        date = pd.Timestamp.today().normalize() if unscheduled else ev["date"]
        rows = []
        for c in cons.itertuples(index=False):
            a_id, b_id = db.find_strict(c.fighter1), db.find_strict(c.fighter2)
            if unscheduled and not (a_id and b_id):
                continue  # the undated page mixes promotions; keep UFC-vs-UFC only
            mine = bfo.best_prices(ev["book_lines"][ev["book_lines"]["matchup_id"] == c.matchup_id], books)
            rec = {"matchup_id": c.matchup_id, "fighter1": c.fighter1, "fighter2": c.fighter2,
                   "p1_market": c.p1_market, "books": c.books,
                   "dec1_best": mine["dec1"], "book1_best": mine["book1"],
                   "dec2_best": mine["dec2"], "book2_best": mine["book2"],
                   "lines": {b: list(v) for b, v in mine["lines"].items()},
                   "dec1_median": c.dec1_median, "dec2_median": c.dec2_median, "notes": []}
            if not mine["lines"]:
                rec["notes"].append("None of your chosen sportsbooks has posted this fight yet.")
            known = [i for i in (a_id, b_id) if i]
            rec["weight_class"] = db.division_of(known[0]) if known else None
            p1_model = np.nan
            if a_id and b_id and a_id != b_id:
                pred = db.predict(a_id, b_id, date)
                p1_model = pred.p_a
                rec["weight_class"] = pred.methods["weight_class"]
                rec["notes"] += pred.notes
                for side, fid, opp, pm, pmod in (("1", a_id, c.fighter2, c.p1_market, p1_model),
                                                ("2", b_id, c.fighter1, 1 - c.p1_market, 1 - p1_model)):
                    h = hype.current(db, fid, db.hype_history, {"p_market": pm, "p_model": pmod,
                                                                "opponent": opp, "event": ev["name"]})
                    rec[f"hype{side}"], rec[f"hype{side}_label"] = h["meter"], h["label"]
            else:
                missing = [n for n, i in ((c.fighter1, a_id), (c.fighter2, b_id)) if not i]
                rec["notes"].append(f"No UFC history for {', '.join(missing)}: market price only.")
            rec["p1_model"] = p1_model
            if weights and not np.isnan(p1_model):
                rec["p1_est"] = float(market.blend(p1_model, c.p1_market, weights))
            else:
                rec["p1_est"] = c.p1_market
            for side, p, dec in (("1", rec["p1_est"], rec["dec1_best"]), ("2", 1 - rec["p1_est"], rec["dec2_best"])):
                rec[f"ev{side}"] = odds.expected_value(p, dec)
                k = min(odds.kelly_fraction(p, dec) * kelly_mult, max_stake)
                rec[f"kelly{side}"] = k
                rec[f"stake{side}"] = round(bankroll * k, 2) if bankroll else np.nan
            # line movement since first seen
            hist = log[log["matchup_id"] == c.matchup_id] if not log.empty else pd.DataFrame()
            if len(hist) > 1:
                first = hist.sort_values("seen_at").iloc[0]
                rec["move"] = c.p1_market - first["p1_market"]
                rec["move_since"] = first["seen_at"]
            else:
                rec["move"], rec["move_since"] = np.nan, pd.NaT
            # market props
            pr = props[props["matchup_id"] == c.matchup_id] if not props.empty else props
            if len(pr):
                pr = pr.iloc[0]
                for col in ("p_decision", "p_1_KO", "p_1_SUB", "p_1_DEC", "p_2_KO", "p_2_SUB", "p_2_DEC"):
                    rec[col] = pr.get(col, np.nan)
            rows.append(rec)
        fights = pd.DataFrame(rows)
        ea = EventAnalysis(ev["name"], ev["date"], ev["url"], fights)
        if with_news and len(fights):
            import requests
            session = session or requests.Session()
            if verbose:
                print(f"  checking news for {2 * len(fights)} fighters on {ev['name']}...")
            for name in pd.concat([fights["fighter1"], fights["fighter2"]]).unique():
                ea.news[name] = news.fighter_news(name, days=news_days, session=session)
        out.append(ea)
    # the site sometimes lists one event under two pages a day apart; drop the empty twin
    named = {}
    for ea in out:
        named.setdefault(ea.name, []).append(ea)
    return [ea for ea in out if len(ea.fights) or all(e.fights.empty for e in named[ea.name])]


def filter_division(analyses: list[EventAnalysis], division: str | None) -> list[EventAnalysis]:
    """Keep only fights in one weight class (division = canonical name, e.g. "Women's Flyweight")."""
    if not division:
        return analyses
    out = []
    for ea in analyses:
        f = ea.fights[ea.fights["weight_class"] == division] if len(ea.fights) else ea.fights
        if len(f):
            out.append(EventAnalysis(ea.name, ea.date, ea.url, f.reset_index(drop=True), ea.news))
    return out


STALE_GAP = 0.05  # best price implies 5+ points less than the typical book: likely stale


def value_bets(analyses: list[EventAnalysis], min_ev: float = 0.05) -> pd.DataFrame:
    """Sides with EV >= min_ev at the best price. Undated fights are skipped:
    their lines are often stale and some of those fights never happen."""
    rows = []
    for ea in analyses:
        if pd.isna(ea.date):
            continue
        for r in ea.fights.to_dict("records"):
            for side, other in (("1", "2"), ("2", "1")):
                if r[f"ev{side}"] >= min_ev:
                    p = r["p1_est"] if side == "1" else 1 - r["p1_est"]
                    rows.append({
                        "event": ea.name, "division": r.get("weight_class"),
                        "bet": r[f"fighter{side}"], "vs": r[f"fighter{other}"],
                        "price": odds.decimal_to_american(r[f"dec{side}_best"]), "book": r[f"book{side}_best"],
                        "our %": p, "market %": r["p1_market"] if side == "1" else 1 - r["p1_market"],
                        "EV": r[f"ev{side}"], "kelly %": r[f"kelly{side}"], "stake": r[f"stake{side}"],
                        "market only": bool(np.isnan(r["p1_model"])),
                        "check": ("lone outlier price - may be stale"
                                  if 1 / r[f"dec{side}_median"] - 1 / r[f"dec{side}_best"] > STALE_GAP else ""),
                    })
    return pd.DataFrame(rows).sort_values("EV", ascending=False) if rows else pd.DataFrame()


def live_odds_for(db: Database, a_id: str, b_id: str, books: list[str] | None = None):
    """Best current prices (among the chosen sportsbooks) for a matchup if it's
    on an upcoming card, else None.

    Returns (event name, event date, best price for a, best price for b,
    (book for a, book for b), number of chosen books with a line)."""
    books = books or settings.books()
    for ev in bfo.upcoming(include_unscheduled=True):
        for c in ev["consensus"].itertuples(index=False):
            ids = (db.find_strict(c.fighter1), db.find_strict(c.fighter2))
            if set(ids) == {a_id, b_id}:
                mine = bfo.best_prices(ev["book_lines"][ev["book_lines"]["matchup_id"] == c.matchup_id], books)
                if not mine["lines"]:
                    return None
                straight = ids[0] == a_id
                pa = mine["dec1"] if straight else mine["dec2"]
                pb = mine["dec2"] if straight else mine["dec1"]
                bks = (mine["book1"], mine["book2"]) if straight else (mine["book2"], mine["book1"])
                return ev["name"], ev["date"], pa, pb, bks, len(mine["lines"])
    return None
