"""Historical betting odds: matching, market benchmark, model+market blend, ROI backtest.

Odds come from https://github.com/jansen88/ufc-data (decimal odds for ~3,500
UFC fights, late 2014 - 2023). They are used to

  * measure the model against the betting market on the same fights,
  * learn how much weight to give the model vs the market when you supply
    live odds (the "blend"), and
  * backtest whether betting the model's edges would actually have paid.
"""

from __future__ import annotations

import difflib

import numpy as np
import pandas as pd

from . import config
from .model import _log_loss, _sigmoid, fit_logistic, train_win_model

EDGE_THRESHOLDS = (0.0, 0.03, 0.05, 0.08, 0.10, 0.15)


def _norm(s: str) -> str:
    from .analysis import normalize_name
    return normalize_name(s)


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def build_odds(fights: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Match raw odds rows to fight ids; returns fight_id, dec_a, dec_b (aligned to fighter_a/b)."""
    path = config.RAW_DIR / config.ODDS_FILE
    if not path.exists():
        return pd.DataFrame(columns=["fight_id", "dec_a", "dec_b"])
    o = pd.read_csv(path)
    o = o[np.isfinite(o["favourite_odds"]) & np.isfinite(o["underdog_odds"])]
    o = o[(o["favourite_odds"] > 1.0) & (o["underdog_odds"] > 1.0)]
    over = 1 / o["favourite_odds"] + 1 / o["underdog_odds"] - 1
    o = o[(over > -0.02) & (over < 0.15)].copy()  # drop corrupt lines
    o["date"] = pd.to_datetime(o["event_date"])

    by_date: dict[pd.Timestamp, list] = {}
    for r in fights.itertuples(index=False):
        by_date.setdefault(r.date, []).append((r.fight_id, _norm(r.fighter_a), _norm(r.fighter_b)))

    def sim(x: str, y: str) -> float:
        if x == y:
            return 1.0
        if x.split()[-1] == y.split()[-1]:
            return 0.9
        return difflib.SequenceMatcher(None, x, y).ratio()

    def match(date, n1, n2):
        """-> (fight_id, fighter1_is_our_fighter_a) or (None, None).

        Exact names first; otherwise allow one renamed fighter (e.g. "Ian Garry"
        -> "Ian Machado Garry") as long as the match is unique on that date."""
        scored = []
        for fid, a, b in by_date.get(date, []):
            for score, straight in ((min(sim(n1, a), sim(n2, b)), True), (min(sim(n1, b), sim(n2, a)), False)):
                pair = (sim(n1, a), sim(n2, b)) if straight else (sim(n1, b), sim(n2, a))
                if score >= 0.6 and max(pair) == 1.0:
                    scored.append((score, fid, straight))
        scored.sort(reverse=True)
        if not scored or (len(scored) > 1 and scored[1][0] == scored[0][0] and scored[1][1] != scored[0][1]):
            return None, None
        return scored[0][1], scored[0][2]

    rows = []
    for r in o.itertuples(index=False):
        n1, n2 = _norm(r.fighter1), _norm(r.fighter2)
        fid, straight = match(r.date, n1, n2)
        if fid is None:
            continue
        fav = _norm(r.favourite)
        odds1 = r.favourite_odds if fav == n1 else r.underdog_odds
        odds2 = r.underdog_odds if fav == n1 else r.favourite_odds
        dec_a, dec_b = (odds1, odds2) if straight else (odds2, odds1)
        rows.append({"fight_id": fid, "dec_a": float(dec_a), "dec_b": float(dec_b)})
    out = pd.DataFrame(rows).drop_duplicates("fight_id")
    if verbose:
        print(f"  matched historical odds for {len(out)} of {len(o)} priced fights")
    return out


# ---------------------------------------------------------------------------

def market_probs(dec_a, dec_b) -> np.ndarray:
    ia, ib = 1 / np.asarray(dec_a, float), 1 / np.asarray(dec_b, float)
    return ia / (ia + ib)


def fit_blend(p_model, p_market, y) -> np.ndarray:
    """Weights (w_model, w_market) on log-odds; no intercept keeps it symmetric."""
    X = np.column_stack([_logit(p_model), _logit(p_market)])
    X = np.vstack([X, -X])
    yy = np.concatenate([y, 1 - y])
    return fit_logistic(X, yy, l2=1.0)


def blend(p_model, p_market, w) -> np.ndarray:
    return _sigmoid(w[0] * _logit(p_model) + w[1] * _logit(p_market))


def model_probs(rows: pd.DataFrame, odds: pd.DataFrame) -> pd.DataFrame:
    """Priced, decisive fights with out-of-sample model and no-vig market probabilities.

    Each year's fights are predicted by a model trained only on earlier fights."""
    priced = rows.merge(odds, on="fight_id")
    priced = priced[priced["result_a"].isin(["W", "L"])].copy()
    priced["p_market"] = market_probs(priced["dec_a"], priced["dec_b"])
    priced["y"] = (priced["result_a"] == "W").astype(float)
    priced["year"] = priced["date"].dt.year
    priced["p_model"] = np.nan
    for year in sorted(priced["year"].unique()):
        m = train_win_model(rows[rows["date"] < pd.Timestamp(f"{year}-01-01")])
        idx = priced["year"] == year
        priced.loc[idx, "p_model"] = m.predict(priced[idx])
    return priced


def walk_forward(rows: pd.DataFrame, odds: pd.DataFrame, start_year: int = 2016) -> pd.DataFrame:
    """Adds walk-forward blended probabilities: each year's blend weights are fitted
    on priced fights from earlier years only (so the first priced year, 2015,
    is used purely for fitting)."""
    priced = model_probs(rows, odds)
    priced["p_blend"] = np.nan
    for year in sorted(priced["year"].unique()):
        tr = priced[priced["year"] < year]
        if year < start_year or tr.empty:
            continue
        te = priced["year"] == year
        w = fit_blend(tr["p_model"], tr["p_market"], tr["y"].to_numpy())
        priced.loc[te, "p_blend"] = blend(priced.loc[te, "p_model"], priced.loc[te, "p_market"], w)
    return priced[priced["year"] >= start_year]


def summary(wf: pd.DataFrame) -> pd.DataFrame:
    y = wf["y"].to_numpy()
    rows = []
    for name, col in (("betting market (no-vig)", "p_market"), ("stats model", "p_model"),
                      ("model + market blend", "p_blend")):
        p = wf[col].to_numpy()
        rows.append({"source": name, "fights": len(wf), "accuracy": float(np.mean((p > 0.5) == y)),
                     "log loss": _log_loss(p, y), "brier": float(np.mean((p - y) ** 2))})
    return pd.DataFrame(rows)


def roi_table(wf: pd.DataFrame, prob_col: str, thresholds=EDGE_THRESHOLDS) -> pd.DataFrame:
    """Flat 1-unit bets on every side whose edge (prob - no-vig prob) beats the threshold."""
    rows = []
    for th in thresholds:
        stakes = won = profit = 0.0
        n_dog = 0
        for side in ("a", "b"):
            p = wf[prob_col] if side == "a" else 1 - wf[prob_col]
            pm = wf["p_market"] if side == "a" else 1 - wf["p_market"]
            dec = wf[f"dec_{side}"]
            win = wf["y"] if side == "a" else 1 - wf["y"]
            sel = (p - pm) > th
            stakes += sel.sum()
            won += win[sel].sum()
            profit += ((dec[sel] - 1) * win[sel] - (1 - win[sel])).sum()
            n_dog += (sel & (dec > 2.0)).sum()
        rows.append({"min edge": th, "bets": int(stakes), "win %": won / stakes if stakes else np.nan,
                     "underdog bets %": n_dog / stakes if stakes else np.nan,
                     "profit (units)": profit, "ROI": profit / stakes if stakes else np.nan})
    return pd.DataFrame(rows)


def final_blend_weights(rows: pd.DataFrame, odds: pd.DataFrame) -> list[float] | None:
    """Blend weights fitted on every priced fight, for use with live odds."""
    priced = model_probs(rows, odds)
    if priced.empty:
        return None
    return [float(x) for x in fit_blend(priced["p_model"], priced["p_market"], priced["y"].to_numpy())]
