"""Win-probability model, method-of-victory estimates, and walk-forward backtest.

The win model is an L2-regularised logistic regression on A-minus-B feature
differences, fitted with no intercept on both orientations of every fight, so
it is symmetric: P(A beats B) = 1 - P(B beats A), and the order fighters are
listed in (ufcstats usually lists the winner first) cannot leak in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config
from .features import FEATURES

DIFF_COLS = [f"d_{k}" for k in FEATURES]
MIN_TRAIN_DATE = pd.Timestamp("2001-01-01")  # unified rules / modern era
METHOD_PRIOR = 4.0  # pseudo-wins for shrinking a fighter's method mix
L2 = 400.0  # ridge strength on standardised features, tuned on the backtest


# ---------------------------------------------------------------------------
# Logistic regression (numpy, Newton-Raphson)
# ---------------------------------------------------------------------------

def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 50) -> np.ndarray:
    n, d = X.shape
    w = np.zeros(d)
    for _ in range(iters):
        p = _sigmoid(X @ w)
        grad = X.T @ (p - y) + l2 * w
        H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(d)
        step = np.linalg.solve(H, grad)
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return w


@dataclass
class WinModel:
    columns: list[str]
    scale: np.ndarray
    weights: np.ndarray

    def predict(self, diffs: pd.DataFrame | dict) -> np.ndarray:
        X = pd.DataFrame([diffs] if isinstance(diffs, dict) else diffs)[self.columns].to_numpy(float)
        return _sigmoid((X / self.scale) @ self.weights)

    def to_dict(self) -> dict:
        return {"columns": self.columns, "scale": self.scale.tolist(), "weights": self.weights.tolist()}

    @classmethod
    def from_dict(cls, d: dict) -> "WinModel":
        return cls(d["columns"], np.array(d["scale"]), np.array(d["weights"]))


def _training_rows(rows: pd.DataFrame) -> pd.DataFrame:
    return rows[rows["result_a"].isin(["W", "L"]) & (rows["date"] >= MIN_TRAIN_DATE)]


def train_win_model(rows: pd.DataFrame, columns: list[str] = DIFF_COLS, l2: float = L2) -> WinModel:
    tr = _training_rows(rows)
    X = tr[columns].to_numpy(float)
    y = (tr["result_a"] == "W").to_numpy(float)
    X = np.vstack([X, -X])          # both orientations -> symmetric model
    y = np.concatenate([y, 1 - y])
    scale = X.std(axis=0)
    scale[scale == 0] = 1.0
    w = fit_logistic(X / scale, y, l2=l2)
    return WinModel(list(columns), scale, w)


# ---------------------------------------------------------------------------
# Method of victory
# ---------------------------------------------------------------------------

def method_base_rates(fights: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Share of KO / SUB / DEC among decisive results, per weight class (2010+)."""
    f = fights[(fights["date"] >= "2010-01-01") & fights["method_group"].isin(["KO", "SUB", "DEC"])
               & fights["result_a"].isin(["W", "L"])]
    overall = f["method_group"].value_counts(normalize=True).to_dict()
    out = {"_all": {k: overall.get(k, 0.0) for k in ("KO", "SUB", "DEC")}}
    for wc, grp in f.groupby("weight_class"):
        if len(grp) >= 50:
            vc = grp["method_group"].value_counts(normalize=True)
            out[wc] = {k: float(vc.get(k, 0.0)) for k in ("KO", "SUB", "DEC")}
    return out


def method_split(wins: dict, opp_losses: dict, base: dict) -> dict[str, float]:
    """P(method | this fighter wins).

    Blends how this fighter usually wins with how the opponent usually loses,
    each shrunk toward the weight-class base rate.
    """
    nw = sum(wins.values())
    nl = sum(opp_losses.values())
    out = {}
    for m in ("KO", "SUB", "DEC"):
        own = (wins[m] + METHOD_PRIOR * base[m]) / (nw + METHOD_PRIOR)
        opp = (opp_losses[m] + METHOD_PRIOR * base[m]) / (nl + METHOD_PRIOR)
        out[m] = (own + opp) / 2.0
    tot = sum(out.values())
    return {m: v / tot for m, v in out.items()}


def method_probs(p_a: float, a_wins: dict, a_losses: dict, b_wins: dict, b_losses: dict,
                 base: dict) -> dict[str, float]:
    sa = method_split(a_wins, b_losses, base)
    sb = method_split(b_wins, a_losses, base)
    out = {f"A_{m}": p_a * sa[m] for m in sa}
    out.update({f"B_{m}": (1 - p_a) * sb[m] for m in sb})
    out["distance"] = out["A_DEC"] + out["B_DEC"]
    return out


def _row_counts(r, side: str) -> tuple[dict, dict]:
    w = {"KO": getattr(r, f"{side}_ko_w"), "SUB": getattr(r, f"{side}_sub_w"), "DEC": getattr(r, f"{side}_dec_w")}
    l = {"KO": getattr(r, f"{side}_ko_l"), "SUB": getattr(r, f"{side}_sub_l"), "DEC": getattr(r, f"{side}_dec_l")}
    return w, l


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save(model: WinModel, base_rates: dict, metrics: dict | None = None,
         blend_weights: list[float] | None = None) -> None:
    config.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"win_model": model.to_dict(), "method_base_rates": base_rates,
               "blend_weights": blend_weights, "backtest": metrics or {}}
    config.MODEL_PATH.write_text(json.dumps(payload, indent=2, default=float))


def load() -> tuple[WinModel, dict, dict, list[float] | None]:
    if not config.MODEL_PATH.exists():
        raise FileNotFoundError(f"{config.MODEL_PATH} missing - run `ballout update` first")
    d = json.loads(config.MODEL_PATH.read_text())
    return (WinModel.from_dict(d["win_model"]), d["method_base_rates"], d.get("backtest", {}),
            d.get("blend_weights"))


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def _log_loss(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def backtest(rows: pd.DataFrame, fights: pd.DataFrame, start_year: int = 2012,
             columns: list[str] = DIFF_COLS, l2: float = L2) -> pd.DataFrame:
    """Walk-forward: for each year, train only on fights before Jan 1 of that
    year and score that year's fights. Returns one row per year plus 'ALL'."""
    decisive = rows[rows["result_a"].isin(["W", "L"])]
    last_year = int(decisive["date"].dt.year.max())
    recs = []
    preds = []
    for year in range(start_year, last_year + 1):
        cutoff = pd.Timestamp(f"{year}-01-01")
        train = rows[rows["date"] < cutoff]
        test = decisive[decisive["date"].dt.year == year]
        if test.empty:
            continue
        full = train_win_model(train, columns, l2)
        elo = train_win_model(train, ["d_elo"])
        base = method_base_rates(fights[fights["date"] < cutoff])
        p = full.predict(test)
        pe = elo.predict(test)
        y = (test["result_a"] == "W").to_numpy(float)

        # "goes the distance" calibration, scored on fights with a known method
        dist_p, dist_y, dist_base = [], [], []
        for r, pa in zip(test.itertuples(index=False), p):
            if r.method_group not in ("KO", "SUB", "DEC"):
                continue
            b = base.get(r.weight_class, base["_all"])
            aw, al = _row_counts(r, "a")
            bw, bl = _row_counts(r, "b")
            mp = method_probs(pa, aw, al, bw, bl, b)
            dist_p.append(mp["distance"])
            dist_base.append(b["DEC"])
            dist_y.append(1.0 if r.method_group == "DEC" else 0.0)
        exp_mask = ((test["a_fights"] >= 2) & (test["b_fights"] >= 2)).to_numpy()
        preds.append(pd.DataFrame({"year": year, "p": p, "pe": pe, "y": y, "exp": exp_mask}))
        recs.append({
            "year": year, "fights": len(test),
            "acc_model": float(np.mean((p > 0.5) == y)),
            "acc_elo": float(np.mean((pe > 0.5) == y)),
            "logloss_model": _log_loss(p, y),
            "logloss_elo": _log_loss(pe, y),
            "acc_model_exp": float(np.mean((p[exp_mask] > 0.5) == y[exp_mask])) if exp_mask.any() else np.nan,
            "brier_distance_model": float(np.mean((np.array(dist_p) - np.array(dist_y)) ** 2)),
            "brier_distance_base": float(np.mean((np.array(dist_base) - np.array(dist_y)) ** 2)),
        })
    out = pd.DataFrame(recs)
    allp = pd.concat(preds)
    m = allp["exp"].to_numpy()
    total = {
        "year": "ALL", "fights": int(len(allp)),
        "acc_model": float(np.mean((allp.p > 0.5) == allp.y)),
        "acc_elo": float(np.mean((allp.pe > 0.5) == allp.y)),
        "logloss_model": _log_loss(allp.p.to_numpy(), allp.y.to_numpy()),
        "logloss_elo": _log_loss(allp.pe.to_numpy(), allp.y.to_numpy()),
        "acc_model_exp": float(np.mean((allp.p[m] > 0.5) == allp.y[m])),
        "brier_distance_model": float(np.average(out["brier_distance_model"], weights=out["fights"])),
        "brier_distance_base": float(np.average(out["brier_distance_base"], weights=out["fights"])),
    }
    out = pd.concat([out, pd.DataFrame([total])], ignore_index=True)
    out.attrs["calibration"] = calibration_table(allp.p.to_numpy(), allp.y.to_numpy())
    return out


def calibration_table(p: np.ndarray, y: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Fold to the favourite's side so each bucket is 'model said X%, won Y%'."""
    fav_p = np.where(p >= 0.5, p, 1 - p)
    fav_y = np.where(p >= 0.5, y, 1 - y)
    edges = np.linspace(0.5, 1.0, bins // 2 + 1)
    idx = np.clip(np.digitize(fav_p, edges) - 1, 0, len(edges) - 2)
    rows = []
    for i in range(len(edges) - 1):
        m = idx == i
        if m.any():
            rows.append({"bucket": f"{edges[i]:.0%}-{edges[i + 1]:.0%}", "fights": int(m.sum()),
                         "predicted": float(fav_p[m].mean()), "actual": float(fav_y[m].mean())})
    return pd.DataFrame(rows)
