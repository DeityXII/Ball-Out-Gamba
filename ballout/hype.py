"""Hype meter: how far a fighter's reputation runs ahead of what the numbers show.

Fans, media and betting prices react to highlight finishes, unbeaten records
and storylines; the stats model only sees performance. Backtesting closing
odds for every priced UFC fight since 2014 (9,600+ fighter-fights), two
signals predicted a fighter falling short of what the odds implied:

  1. the market rating them above the stats model (z = -4), and
  2. that gap mattering more when they're unbeaten (z = -2).

Other ideas were tested and dropped because they didn't hold up: a "padded"
record against weak opposition, win streaks, inexperience, and past hype
(fighters hyped before actually did slightly better - lasting hype tends to be
earned). Young fighters and fighters stepping up in competition tended to
*beat* their odds.

The score (in log-odds) maps to a 0-100 meter. Very hyped fighters won 3-4
points less often than their odds implied once the usual favourite bias is
removed - the measurable "fraud check". It is a modest effect: most hyped
favourites still win.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config, market

HISTORY_FILE = "hype_history.csv"

BANDS = [  # (upper bound of hype score, label)
    (-0.5, "Underrated"),
    (0.25, "Fairly rated"),
    (0.75, "Hyped"),
    (1.25, "Very hyped"),
    (math.inf, "Fraud-check zone"),
]
_METER_POINTS = [(-1.5, 0), (-0.5, 20), (0.25, 40), (0.75, 60), (1.25, 80), (2.0, 100)]


UFC_AVG_ELO = 1500.0


def score(gap: float, unbeaten: bool) -> float:
    """gap = market log-odds minus stats-model log-odds for this fighter."""
    return gap * (1 + 0.5 * bool(unbeaten))


def meter(s: float) -> int:
    """Hype score -> 0-100 (piecewise linear through the band edges)."""
    xs, ys = zip(*_METER_POINTS)
    return int(round(float(np.interp(s, xs, ys))))


def label(s: float) -> str:
    return next(name for hi, name in BANDS if s <= hi)


def gap_points(p_market: float, p_model: float) -> float:
    """Gap shown to people: market % minus stats-model %, in points."""
    return 100 * (p_market - p_model)


# ---------------------------------------------------------------------------
# History (built by `update`): every priced fight, both sides
# ---------------------------------------------------------------------------

def build_history(rows: pd.DataFrame, odds: pd.DataFrame) -> pd.DataFrame:
    """Hype at fight time for both fighters in every fight with closing odds.

    The stats probability is out-of-sample (each year predicted by a model
    trained on earlier years), so the history is a fair test of the meter."""
    pr = market.model_probs(rows, odds)
    L = market._logit
    out = []
    for s, flip in (("a", False), ("b", True)):
        pm = 1 - pr["p_market"] if flip else pr["p_market"]
        pmod = 1 - pr["p_model"] if flip else pr["p_model"]
        unbeaten = (pr[f"{s}_fights"] >= 2) & (pr[f"{s}_losses"] == 0)
        gap = L(pm.to_numpy()) - L(pmod.to_numpy())
        out.append(pd.DataFrame({
            "date": pr["date"], "fight_id": pr["fight_id"], "fighter_id": pr[f"fighter_{s}_id"],
            "fighter": pr[f"fighter_{s}"], "opponent": pr["fighter_b" if s == "a" else "fighter_a"],
            "weight_class": pr["weight_class"], "p_market": pm, "p_model": pmod, "won": (1 - pr["y"]) if flip else pr["y"],
            "gap": gap, "unbeaten": unbeaten.astype(int),
        }))
    h = pd.concat(out, ignore_index=True)
    h["hype"] = [score(g, u) for g, u in zip(h["gap"], h["unbeaten"])]
    return h.sort_values("date").reset_index(drop=True)


def save_history(h: pd.DataFrame) -> None:
    h.to_csv(config.PROCESSED_DIR / HISTORY_FILE, index=False)


def load_history() -> pd.DataFrame:
    path = config.PROCESSED_DIR / HISTORY_FILE
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["date"])


def backtest_table(h: pd.DataFrame) -> pd.DataFrame:
    """Per hype band: how fighters did against their odds.

    'corrected odds' removes the favourite-longshot bias (favourites as a
    group beat their odds), so the comparison isolates the hype effect."""
    if h.empty:
        return pd.DataFrame()
    L = market._logit
    x, y = L(h["p_market"].to_numpy()), h["won"].to_numpy(float)
    a = 1.0
    for _ in range(30):  # 1-parameter logistic fit: fair log-odds = a * market log-odds
        p = 1 / (1 + np.exp(-a * x))
        a -= ((p - y) * x).sum() / (p * (1 - p) * x * x).sum()
    fair = 1 / (1 + np.exp(-a * x))
    h = h.assign(fair=fair, band=[label(s) for s in h["hype"]])
    rows = []
    for _, name in BANDS:
        sub = h[h["band"] == name]
        if sub.empty:
            continue
        se = math.sqrt((sub["fair"] * (1 - sub["fair"])).sum()) / len(sub)
        rows.append({"band": name, "fights": len(sub), "favourites": (sub["p_market"] > 0.5).mean(),
                     "odds said": sub["p_market"].mean(), "corrected odds": sub["fair"].mean(),
                     "actually won": sub["won"].mean(), "vs corrected": sub["won"].mean() - sub["fair"].mean(),
                     "± (1 s.e.)": se})
    out = pd.DataFrame(rows)
    out.attrs["since"] = h["date"].min()
    return out


# ---------------------------------------------------------------------------
# Current hype for fighters
# ---------------------------------------------------------------------------

def current(db, fid: str, history: pd.DataFrame, live: dict | None = None) -> dict:
    """Hype for one fighter now.

    With a live line for a booked fight (live = {"p_market", "p_model",
    "opponent", "event"}), that fight is scored - the validated use. Otherwise
    the meter describes their last priced fight."""
    st = db.states[fid]
    unbeaten = st.fights >= 2 and st.losses == 0
    context = {"unbeaten": unbeaten, "record": st.record, "ufc_fights": st.fights, "streak": st.streak,
               "opp_avg_elo": st.sos if st.opp_elo_n else None}
    if live:
        pm, pmod = live["p_market"], live["p_model"]
        basis = f"live odds vs {live['opponent']}" + (f" ({live['event']})" if live.get("event") else "")
        when = None
    else:
        mine = history[history["fighter_id"] == fid] if not history.empty else history
        if mine.empty:
            return {"fighter_id": fid, "fighter": st.name, "available": False,
                    "reason": "no fight with betting odds yet", **context}
        last = mine.iloc[-1]
        pm, pmod = float(last["p_market"]), float(last["p_model"])
        basis = f"last priced fight vs {last['opponent']}"
        when = last["date"]
    gap = float(market._logit(pm) - market._logit(pmod))
    s = score(gap, unbeaten)
    return {"fighter_id": fid, "fighter": st.name, "available": True, "score": s, "meter": meter(s),
            "label": label(s), "basis": basis, "date": when, "market %": pm, "stats %": pmod,
            "gap pts": gap_points(pm, pmod), **context}


def reasons(h: dict) -> list[str]:
    """Plain-English drivers behind a hype reading."""
    out = []
    if not h.get("available"):
        return out
    gp = h["gap pts"]
    if gp >= 5:
        out.append(f"the odds rate them {gp:.0f} pts higher than their stats do")
    elif gp <= -5:
        out.append(f"their stats rate them {-gp:.0f} pts higher than the odds do")
    if h["unbeaten"] and gp > 0:
        out.append("unbeaten in the UFC, which makes a hype gap more likely to be exposed")
    opp = h.get("opp_avg_elo")
    if opp is not None and h["ufc_fights"] <= 7 and opp < UFC_AVG_ELO - 25:
        out.append(f"context: has mostly faced below-average UFC opposition (opponents average {opp:.0f} Elo)")
    return out


def up_and_comers(db, history: pd.DataFrame, division: str | None = None, max_fights: int = 7,
                  max_age: float = 31, active_days: int = 450, live: dict | None = None,
                  date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Rising fighters (few UFC fights, young, winning, active) with their hype meter.

    live: optional {fighter_id: live-dict} from upcoming cards, so booked
    fighters are scored on their next fight's odds."""
    date = pd.Timestamp(date) if date is not None else pd.Timestamp.today().normalize()
    rows = []
    for fid, st in db.states.items():
        if not (2 <= st.fights <= max_fights) or st.last_date is None:
            continue
        if (date - st.last_date).days > active_days or st.wins < st.losses + 2:
            continue
        dob = db.info(fid).get("dob")
        age = (date - dob).days / 365.25 if dob is not None and not pd.isna(dob) else np.nan
        if not pd.isna(age) and age > max_age:
            continue
        wc = db.fight_log(fid).iloc[0]["weight_class"]
        if division and wc != division:  # division is the canonical name, e.g. "Women's Flyweight"
            continue
        h = current(db, fid, history, (live or {}).get(fid))
        if not h["available"]:
            continue
        rows.append({**h, "fighter": db.label(fid), "division": wc, "age": age, "elo": round(st.elo),
                     "why": "; ".join(reasons(h))})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("score", ascending=False).reset_index(drop=True)


def fraud_checks(db, analyses, history: pd.DataFrame, threshold: float = 0.75) -> list[dict]:
    """Booked fights where the favourite is very hyped (score >= threshold) on today's odds."""
    alerts = []
    for ea in analyses:
        if pd.isna(ea.date):
            continue
        for f in ea.fights.to_dict("records"):
            if pd.isna(f.get("p1_model")):
                continue
            for side, other, p_mkt, p_mod in (("1", "2", f["p1_market"], f["p1_model"]),
                                             ("2", "1", 1 - f["p1_market"], 1 - f["p1_model"])):
                if p_mkt <= 0.5:
                    continue
                fid = db.find_strict(f[f"fighter{side}"])
                if not fid:
                    continue
                h = current(db, fid, history, {"p_market": p_mkt, "p_model": p_mod,
                                               "opponent": f[f"fighter{other}"], "event": ea.name})
                if h["score"] >= threshold:
                    opp = db.find_strict(f[f"fighter{other}"])
                    step = (db.states[opp].elo - db.states[fid].sos) if opp else np.nan
                    alerts.append({**h, "event": ea.name, "date": ea.date, "opponent": f[f"fighter{other}"],
                                   "division": f.get("weight_class"),
                                   "our %": f["p1_est"] if side == "1" else 1 - f["p1_est"],
                                   "step_up": step, "why": reasons(h)})
    return sorted(alerts, key=lambda a: -a["score"])
