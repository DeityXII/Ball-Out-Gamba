"""Chronological replay of every UFC fight.

Walking fights in date order, we snapshot each fighter's career numbers
*before* the fight (so model features never see the result they predict),
then update their running totals. The final state after the replay is what
gets used to analyse upcoming matchups.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

ELO_START = 1500.0

# Pseudo-counts used to shrink small samples toward the population average.
PRIOR_MINUTES = 15.0      # career-rate stats (per-minute / per-15)
PRIOR_ATTEMPTS = 20.0     # accuracy / defence percentages
PRIOR_FIGHTS = 3.0        # win / finish rates

# Rough UFC-era population averages used as the shrinkage targets.
POP = {
    "slpm": 3.6, "sapm": 3.6, "sig_acc": 0.45, "sig_def": 0.55,
    "td_avg": 1.3, "td_acc": 0.38, "td_def": 0.62, "sub_avg": 0.45,
    "kd_avg": 0.25, "ctrl_share": 0.15, "win_rate": 0.5,
    "ko_loss_rate": 0.15, "finish_rate": 0.5,
}


def elo_k(n_fights: int) -> float:
    return 48.0 if n_fights < 3 else 36.0 if n_fights < 8 else 28.0


@dataclass
class FighterState:
    fighter_id: str
    name: str
    fights: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    nc: int = 0
    ko_wins: int = 0
    sub_wins: int = 0
    dec_wins: int = 0
    ko_losses: int = 0
    sub_losses: int = 0
    dec_losses: int = 0
    title_fights: int = 0
    five_round_fights: int = 0
    stat_seconds: float = 0.0
    sig_landed: float = 0.0
    sig_att: float = 0.0
    sig_absorbed: float = 0.0
    opp_sig_att: float = 0.0
    td_landed: float = 0.0
    td_att: float = 0.0
    opp_td_landed: float = 0.0
    opp_td_att: float = 0.0
    kd: float = 0.0
    kd_absorbed: float = 0.0
    sub_att: float = 0.0
    ctrl_sec: float = 0.0
    opp_ctrl_sec: float = 0.0
    head_landed: float = 0.0
    body_landed: float = 0.0
    leg_landed: float = 0.0
    dist_landed: float = 0.0
    clinch_landed: float = 0.0
    ground_landed: float = 0.0
    total_seconds: float = 0.0
    elo: float = ELO_START
    peak_elo: float = ELO_START
    last_date: pd.Timestamp | None = None
    first_date: pd.Timestamp | None = None
    results: list = field(default_factory=list)  # 'W','L','D','NC' in order

    # ---- derived metrics ------------------------------------------------
    @property
    def minutes(self) -> float:
        return self.stat_seconds / 60.0

    def _rate(self, total: float, per: float, pop: float) -> float:
        """Per-`per`-minute rate shrunk toward the population mean."""
        return (total + pop / per * PRIOR_MINUTES) / (self.minutes + PRIOR_MINUTES) * per

    def _pct(self, num: float, den: float, pop: float) -> float:
        return (num + pop * PRIOR_ATTEMPTS) / (den + PRIOR_ATTEMPTS)

    @property
    def slpm(self): return self._rate(self.sig_landed, 1, POP["slpm"])
    @property
    def sapm(self): return self._rate(self.sig_absorbed, 1, POP["sapm"])
    @property
    def sig_acc(self): return self._pct(self.sig_landed, self.sig_att, POP["sig_acc"])
    @property
    def sig_def(self): return 1 - self._pct(self.sig_absorbed, self.opp_sig_att, 1 - POP["sig_def"])
    @property
    def td_avg(self): return self._rate(self.td_landed, 15, POP["td_avg"])
    @property
    def td_acc(self): return self._pct(self.td_landed, self.td_att, POP["td_acc"])
    @property
    def td_def(self): return 1 - self._pct(self.opp_td_landed, self.opp_td_att, 1 - POP["td_def"])
    @property
    def sub_avg(self): return self._rate(self.sub_att, 15, POP["sub_avg"])
    @property
    def kd_avg(self): return self._rate(self.kd, 15, POP["kd_avg"])
    @property
    def ctrl_share(self):
        return (self.ctrl_sec + POP["ctrl_share"] * PRIOR_MINUTES * 60) / (self.stat_seconds + PRIOR_MINUTES * 60)
    @property
    def opp_ctrl_share(self):
        return (self.opp_ctrl_sec + POP["ctrl_share"] * PRIOR_MINUTES * 60) / (self.stat_seconds + PRIOR_MINUTES * 60)

    @property
    def decisive(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self):
        return (self.wins + POP["win_rate"] * PRIOR_FIGHTS) / (self.decisive + PRIOR_FIGHTS)

    @property
    def finish_rate(self):
        return (self.ko_wins + self.sub_wins + POP["finish_rate"] * PRIOR_FIGHTS) / (self.wins + PRIOR_FIGHTS)

    @property
    def ko_loss_rate(self):
        return (self.ko_losses + POP["ko_loss_rate"] * PRIOR_FIGHTS) / (self.fights + PRIOR_FIGHTS)

    @property
    def streak(self) -> int:
        """+n for n straight wins, -n for n straight losses (draws/NCs skipped)."""
        s = 0
        for r in reversed(self.results):
            if r not in ("W", "L"):
                continue
            if s == 0:
                s = 1 if r == "W" else -1
            elif (r == "W") == (s > 0):
                s += 1 if s > 0 else -1
            else:
                break
        return s

    def recent_win_rate(self, n: int = 3) -> float:
        last = [r for r in self.results if r in ("W", "L")][-n:]
        return (sum(r == "W" for r in last) + 0.5) / (len(last) + 1)

    @property
    def avg_fight_minutes(self) -> float:
        return self.total_seconds / 60.0 / self.fights if self.fights else float("nan")

    @property
    def record(self) -> str:
        s = f"{self.wins}-{self.losses}-{self.draws}"
        return s + (f" ({self.nc} NC)" if self.nc else "")


# ---------------------------------------------------------------------------

FEATURES = [
    "elo", "age", "reach", "height", "exp", "win_rate", "recent", "streak",
    "layoff", "slpm", "sapm", "sig_acc", "sig_def", "td_avg", "td_acc",
    "td_def", "sub_avg", "kd_avg", "ctrl", "ko_loss_rate", "finish_rate",
    "five_rd_exp",
]


FEATURE_LABELS = {
    "elo": "Elo rating", "age": "age", "reach": "reach", "height": "height",
    "exp": "UFC experience", "win_rate": "UFC win rate", "recent": "recent form",
    "streak": "streak", "layoff": "layoff", "slpm": "strikes landed/min",
    "sapm": "strikes absorbed/min", "sig_acc": "striking accuracy",
    "sig_def": "striking defence", "td_avg": "takedowns/15", "td_acc": "takedown accuracy",
    "td_def": "takedown defence", "sub_avg": "submission attempts", "kd_avg": "knockdowns/15",
    "ctrl": "control time", "ko_loss_rate": "times KO'd", "finish_rate": "finish rate",
    "five_rd_exp": "5-round experience",
}


def side_features(st: FighterState, info: dict, date: pd.Timestamp) -> dict:
    """Pre-fight features for one fighter (absolute, not differenced)."""
    dob = info.get("dob")
    age = (date - dob).days / 365.25 if dob is not None and not pd.isna(dob) else np.nan
    if st.last_date is not None:
        layoff = math.log1p(max((date - st.last_date).days, 0) / 30.0)
    else:
        layoff = np.nan
    return {
        "elo": st.elo / 100.0,
        "age": age,
        "reach": info.get("reach_in", np.nan),
        "height": info.get("height_in", np.nan),
        "exp": math.log1p(st.fights),
        "win_rate": st.win_rate,
        "recent": st.recent_win_rate(3),
        "streak": max(-4, min(4, st.streak)),
        "layoff": layoff,
        "slpm": st.slpm,
        "sapm": st.sapm,
        "sig_acc": st.sig_acc,
        "sig_def": st.sig_def,
        "td_avg": st.td_avg,
        "td_acc": st.td_acc,
        "td_def": st.td_def,
        "sub_avg": st.sub_avg,
        "kd_avg": st.kd_avg,
        "ctrl": st.ctrl_share - st.opp_ctrl_share,
        "ko_loss_rate": st.ko_loss_rate,
        "finish_rate": st.finish_rate,
        "five_rd_exp": math.log1p(st.five_round_fights),
    }


def diff_features(fa: dict, fb: dict) -> dict:
    """A-minus-B differences; missing physicals/age/layoff become 0 (no info)."""
    out = {}
    for k in FEATURES:
        a, b = fa[k], fb[k]
        out[k] = 0.0 if (pd.isna(a) or pd.isna(b)) else float(a) - float(b)
    return out


def _update(st: FighterState, row, date, opp_elo_before: float, outcome: str) -> None:
    st.fights += 1
    st.results.append(outcome)
    if outcome == "W":
        st.wins += 1
    elif outcome == "L":
        st.losses += 1
    elif outcome == "D":
        st.draws += 1
    else:
        st.nc += 1
    grp = row.method_group
    if outcome in ("W", "L"):
        bucket = {"KO": "ko", "SUB": "sub", "DEC": "dec"}.get(grp)
        if bucket:
            attr = f"{bucket}_{'wins' if outcome == 'W' else 'losses'}"
            setattr(st, attr, getattr(st, attr) + 1)
    if row.title_bout:
        st.title_fights += 1
    if row.scheduled_rounds == 5:
        st.five_round_fights += 1
    if not pd.isna(row.fight_seconds):
        st.total_seconds += row.fight_seconds
    if row.has_stats and not pd.isna(row.fight_seconds):
        st.stat_seconds += row.fight_seconds
        g = lambda c: 0.0 if pd.isna(getattr(row, c)) else float(getattr(row, c))
        st.sig_landed += g("sig_landed"); st.sig_att += g("sig_att")
        st.sig_absorbed += g("opp_sig_landed"); st.opp_sig_att += g("opp_sig_att")
        st.td_landed += g("td_landed"); st.td_att += g("td_att")
        st.opp_td_landed += g("opp_td_landed"); st.opp_td_att += g("opp_td_att")
        st.kd += g("kd"); st.kd_absorbed += g("opp_kd")
        st.sub_att += g("sub_att")
        st.ctrl_sec += g("ctrl_sec"); st.opp_ctrl_sec += g("opp_ctrl_sec")
        st.head_landed += g("head_landed"); st.body_landed += g("body_landed")
        st.leg_landed += g("leg_landed"); st.dist_landed += g("dist_landed")
        st.clinch_landed += g("clinch_landed"); st.ground_landed += g("ground_landed")
    # Elo (draws count as half a win; no-contests are ignored)
    if outcome in ("W", "L", "D"):
        score = {"W": 1.0, "L": 0.0, "D": 0.5}[outcome]
        expected = 1.0 / (1.0 + 10 ** ((opp_elo_before - st.elo) / 400.0))
        mult = 1.15 if grp in ("KO", "SUB") and outcome != "D" else 1.0
        st.elo += elo_k(st.fights - 1) * mult * (score - expected)
        st.peak_elo = max(st.peak_elo, st.elo)
    st.first_date = st.first_date or date
    st.last_date = date


@dataclass
class Replay:
    states: dict[str, FighterState]
    rows: pd.DataFrame  # one row per fight with pre-fight features for both sides


def replay(tables: dict[str, pd.DataFrame]) -> Replay:
    fights = tables["fights"]
    ff = tables["fighter_fights"]
    fighters = tables["fighters"].set_index("fighter_id")
    info = fighters[["dob", "reach_in", "height_in"]].to_dict("index")

    # fighter-fight rows keyed by (fight_id, fighter_id)
    ff_idx = {(r.fight_id, r.fighter_id): r for r in ff.itertuples(index=False)}

    states: dict[str, FighterState] = {}

    def state(fid, name):
        if fid not in states:
            states[fid] = FighterState(fid, name)
        return states[fid]

    out = []
    for f in fights.itertuples(index=False):
        sa = state(f.fighter_a_id, f.fighter_a)
        sb = state(f.fighter_b_id, f.fighter_b)
        date = f.date
        fa = side_features(sa, info.get(f.fighter_a_id, {}), date)
        fb = side_features(sb, info.get(f.fighter_b_id, {}), date)
        rec = {
            "fight_id": f.fight_id, "date": date, "event": f.event,
            "fighter_a_id": f.fighter_a_id, "fighter_b_id": f.fighter_b_id,
            "fighter_a": f.fighter_a, "fighter_b": f.fighter_b,
            "result_a": f.result_a, "method_group": f.method_group,
            "weight_class": f.weight_class, "scheduled_rounds": f.scheduled_rounds,
            "a_fights": sa.fights, "b_fights": sb.fights,
            # method-share inputs, used to model method of victory
            "a_wins": sa.wins, "a_losses": sa.losses, "b_wins": sb.wins, "b_losses": sb.losses,
            "a_ko_w": sa.ko_wins, "a_sub_w": sa.sub_wins, "a_dec_w": sa.dec_wins,
            "a_ko_l": sa.ko_losses, "a_sub_l": sa.sub_losses, "a_dec_l": sa.dec_losses,
            "b_ko_w": sb.ko_wins, "b_sub_w": sb.sub_wins, "b_dec_w": sb.dec_wins,
            "b_ko_l": sb.ko_losses, "b_sub_l": sb.sub_losses, "b_dec_l": sb.dec_losses,
        }
        rec.update({f"d_{k}": v for k, v in diff_features(fa, fb).items()})
        out.append(rec)

        elo_a, elo_b = sa.elo, sb.elo
        ra = ff_idx.get((f.fight_id, f.fighter_a_id))
        rb = ff_idx.get((f.fight_id, f.fighter_b_id))
        if ra is not None:
            _update(sa, ra, date, elo_b, f.result_a)
        if rb is not None:
            _update(sb, rb, date, elo_a, f.result_b)

    return Replay(states=states, rows=pd.DataFrame(out))
