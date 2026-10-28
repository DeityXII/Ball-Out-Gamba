"""High-level queries: fighter lookup, profiles, matchups, cards, leaderboards."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import data, features, market, model, odds
from .features import FighterState


class LookupError_(ValueError):
    pass


def normalize_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


@dataclass
class Prediction:
    a: FighterState
    b: FighterState
    p_a: float
    methods: dict
    diffs: dict
    date: pd.Timestamp
    notes: list


class Database:
    def __init__(self):
        self.tables = data.load()
        self.fights = self.tables["fights"]
        self.ff = self.tables["fighter_fights"]
        self.fighters = self.tables["fighters"].set_index("fighter_id")
        self.replay = features.replay(self.tables)
        self.states = self.replay.states
        self.win_model, self.base_rates, self.backtest_metrics, self.blend_weights = model.load()
        from . import hype
        self.hype_history = hype.load_history()
        self._names = {}
        for fid, st in self.states.items():
            self._names.setdefault(normalize_name(st.name), []).append(fid)

    # ---- lookup --------------------------------------------------------
    def info(self, fid: str) -> dict:
        if fid in self.fighters.index:
            return self.fighters.loc[fid].to_dict()
        return {}

    def label(self, fid: str) -> str:
        st = self.states[fid]
        if len(self._names.get(normalize_name(st.name), [])) > 1:
            w = self.info(fid).get("weight_lbs")
            return f"{st.name} ({int(w)} lbs)" if not pd.isna(w) else f"{st.name} [{fid}]"
        return st.name

    def find(self, query: str) -> str:
        """Resolve a name (or fighter id) to a fighter id."""
        q = query.strip()
        if q in self.states:
            return q
        nq = normalize_name(q)
        hits = self._names.get(nq)
        if not hits:
            subs = [fid for n, ids in self._names.items() if nq and nq in n for fid in ids]
            if len(subs) == 1:
                return subs[0]
            if subs:
                hits = subs
        if not hits:
            close = self._fuzzy(nq)
            if len(close) == 1 and len(self._names[close[0]]) == 1:
                return self._names[close[0]][0]
            hits = [fid for n in close for fid in self._names[n]]
        if not hits:
            raise LookupError_(f"No UFC fighter matching '{query}'.")
        if len(hits) == 1:
            return hits[0]
        opts = sorted(hits, key=lambda f: self.states[f].last_date or pd.Timestamp(0), reverse=True)[:10]
        lines = "\n".join(
            f"  {f}  {self.label(f):30s} {self.states[f].record:10s} last fought "
            f"{self.states[f].last_date:%Y-%m-%d}" for f in opts)
        raise LookupError_(f"'{query}' is ambiguous. Use the full name or the id:\n{lines}")

    def find_strict(self, name: str) -> str | None:
        """Exact (accent/case-insensitive) or near-exact full-name match, else None.

        Used for scraped cards, where a debutant must not be mistaken for a
        different UFC veteran with a similar name."""
        nq = normalize_name(name)
        hits = self._names.get(nq)
        if not hits:
            close = difflib.get_close_matches(nq, list(self._names), n=2, cutoff=0.9)
            if len(close) == 1:
                hits = self._names[close[0]]
        if not hits:
            return None
        return max(hits, key=lambda f: self.states[f].last_date or pd.Timestamp(0))

    def _fuzzy(self, nq: str, cutoff: float = 0.8, limit: int = 5) -> list[str]:
        """Names close to the query, comparing the whole name and each part of it
        (so a misspelt surname alone still matches)."""
        scored = []
        for n in self._names:
            parts = [n] + (n.split() if " " not in nq else [])
            score = max(difflib.SequenceMatcher(None, nq, p).ratio() for p in parts)
            if score >= cutoff:
                scored.append((score, n))
        scored.sort(reverse=True)
        if not scored:
            return []
        best = scored[0][0]
        return [n for sc, n in scored if sc >= best - 0.05][:limit]

    def search(self, query: str, limit: int = 20) -> list[str]:
        nq = normalize_name(query)
        hits = [fid for n, ids in self._names.items() if nq in n for fid in ids]
        if not hits:
            hits = [fid for n in self._fuzzy(nq, cutoff=0.7, limit=limit) for fid in self._names[n]]
        return sorted(hits, key=lambda f: self.states[f].last_date or pd.Timestamp(0), reverse=True)[:limit]

    # ---- fighter data --------------------------------------------------
    def fight_log(self, fid: str) -> pd.DataFrame:
        log = self.ff[self.ff["fighter_id"] == fid].copy()
        return log.sort_values(["date", "bout_order"], ascending=[False, True])

    def career_stats(self, fid: str) -> dict:
        """Raw (unsmoothed) career numbers in the familiar ufcstats style."""
        st = self.states[fid]
        mins = st.minutes
        div = lambda a, b: a / b if b else np.nan
        landed_pos = st.dist_landed + st.clinch_landed + st.ground_landed
        landed_tgt = st.head_landed + st.body_landed + st.leg_landed
        return {
            "SLpM": div(st.sig_landed, mins),
            "SApM": div(st.sig_absorbed, mins),
            "Str. Acc": div(st.sig_landed, st.sig_att),
            "Str. Def": 1 - div(st.sig_absorbed, st.opp_sig_att) if st.opp_sig_att else np.nan,
            "TD Avg/15": div(st.td_landed, mins) * 15 if mins else np.nan,
            "TD Acc": div(st.td_landed, st.td_att),
            "TD Def": 1 - div(st.opp_td_landed, st.opp_td_att) if st.opp_td_att else np.nan,
            "Sub Avg/15": div(st.sub_att, mins) * 15 if mins else np.nan,
            "KD/15": div(st.kd, mins) * 15 if mins else np.nan,
            "Ctrl %": div(st.ctrl_sec, st.stat_seconds),
            "Opp Ctrl %": div(st.opp_ctrl_sec, st.stat_seconds),
            "Head %": div(st.head_landed, landed_tgt),
            "Body %": div(st.body_landed, landed_tgt),
            "Leg %": div(st.leg_landed, landed_tgt),
            "Distance %": div(st.dist_landed, landed_pos),
            "Clinch %": div(st.clinch_landed, landed_pos),
            "Ground %": div(st.ground_landed, landed_pos),
            "Avg fight (min)": st.avg_fight_minutes,
        }

    def distance_rate(self, fid: str) -> float:
        log = self.fight_log(fid)
        log = log[log["method_group"].isin(["KO", "SUB", "DEC"])]
        return float((log["method_group"] == "DEC").mean()) if len(log) else np.nan

    # ---- matchups ------------------------------------------------------
    def predict(self, a_id: str, b_id: str, date: pd.Timestamp | None = None,
                weight_class: str | None = None) -> Prediction:
        date = pd.Timestamp(date) if date is not None else pd.Timestamp.today().normalize()
        sa, sb = self.states[a_id], self.states[b_id]
        wc = self._weight_class(weight_class) if weight_class else self._likely_weight_class(a_id, b_id)
        fa = features.side_features(sa, self.info(a_id), date, wc)
        fb = features.side_features(sb, self.info(b_id), date, wc)
        diffs = {f"d_{k}": v for k, v in features.diff_features(fa, fb).items()}
        p_a = float(self.win_model.predict(diffs)[0])

        base = self.base_rates.get(wc, self.base_rates["_all"])
        aw = {"KO": sa.ko_wins, "SUB": sa.sub_wins, "DEC": sa.dec_wins}
        al = {"KO": sa.ko_losses, "SUB": sa.sub_losses, "DEC": sa.dec_losses}
        bw = {"KO": sb.ko_wins, "SUB": sb.sub_wins, "DEC": sb.dec_wins}
        bl = {"KO": sb.ko_losses, "SUB": sb.sub_losses, "DEC": sb.dec_losses}
        methods = model.method_probs(p_a, aw, al, bw, bl, base)
        methods["weight_class"] = wc

        notes = []
        for st in (sa, sb):
            if st.fights < 2:
                notes.append(f"{st.name} has {st.fights} UFC fight(s): stats are mostly league-average priors.")
            if st.last_date is not None and (date - st.last_date).days > 540:
                notes.append(f"{st.name} has not fought in {(date - st.last_date).days // 30} months.")
        for fid in (a_id, b_id):
            if pd.isna(self.info(fid).get("dob")):
                notes.append(f"No date of birth for {self.states[fid].name}; age edge ignored.")
        return Prediction(sa, sb, p_a, methods, diffs, date, notes)

    def drivers(self, pred: Prediction, n: int = 5) -> list[tuple[str, str]]:
        """The features pushing the prediction hardest: [(label, favoured fighter)]."""
        wm = self.win_model
        contribs = {k: v / wm.scale[wm.columns.index(k)] * wm.weights[wm.columns.index(k)]
                    for k, v in pred.diffs.items()}
        top = sorted(contribs.items(), key=lambda kv: -abs(kv[1]))[:n]
        return [(features.FEATURE_LABELS[k[2:]], pred.a.name if c > 0 else pred.b.name)
                for k, c in top if abs(c) >= 0.02]

    def _weight_class(self, text: str) -> str:
        """Case-insensitive match of a user-typed division to the canonical name."""
        known = sorted(set(self.fights["weight_class"]), key=len, reverse=True)
        nq = normalize_name(text)
        women = "women" in nq
        for wc in known:
            if normalize_name(wc.replace("Women's ", "")) in nq and ("Women's" in wc) == women:
                return wc
        raise LookupError_(f"Unknown weight class '{text}'. Options: {', '.join(sorted(known))}")

    def division_of(self, fid: str) -> str | None:
        """The weight class of a fighter's most recent UFC fight."""
        log = self.fight_log(fid)
        return log.iloc[0]["weight_class"] if len(log) else None

    def _likely_weight_class(self, a_id: str, b_id: str) -> str:
        for fid in (a_id, b_id):
            log = self.fight_log(fid)
            if len(log):
                return log.iloc[0]["weight_class"]
        return "_all"

    def head_to_head(self, a_id: str, b_id: str) -> pd.DataFrame:
        log = self.fight_log(a_id)
        return log[log["opponent_id"] == b_id]

    def common_opponents(self, a_id: str, b_id: str) -> pd.DataFrame:
        la, lb = self.fight_log(a_id), self.fight_log(b_id)
        common = (set(la["opponent_id"]) & set(lb["opponent_id"])) - {a_id, b_id}
        rows = []
        for opp in common:
            ra = la[la["opponent_id"] == opp]
            rb = lb[lb["opponent_id"] == opp]
            fmt = lambda df: ", ".join(f"{r.result} {r.method_group} R{int(r.round) if not pd.isna(r.round) else '?'} "
                                       f"({r.date:%Y})" for r in df.itertuples())
            rows.append({"opponent": self.label(opp), self.states[a_id].name: fmt(ra),
                         self.states[b_id].name: fmt(rb), "_last": max(ra["date"].max(), rb["date"].max())})
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).sort_values("_last", ascending=False).drop(columns="_last")

    def price(self, pred: Prediction, odds_a, odds_b, bankroll: float | None = None,
              kelly_mult: float = 0.25, max_stake: float = 1.0) -> pd.DataFrame:
        """Compare our probability with sportsbook prices for each side.

        With both sides' odds, the estimate is the model blended with the
        market (see market.py); edges, EV and stakes are computed from it.
        With one side only, the raw model is used and there is no no-vig line.
        """
        def parse(raw):
            if raw is None or raw == "" or (isinstance(raw, float) and np.isnan(raw)):
                return None
            return odds.parse_odds(raw)

        dec = {"a": parse(odds_a), "b": parse(odds_b)}
        p_model = {"a": pred.p_a, "b": 1 - pred.p_a}
        p_est, p_mkt, vig = dict(p_model), {"a": None, "b": None}, None
        used = "model"
        if dec["a"] and dec["b"]:
            p_mkt["a"], p_mkt["b"], vig = odds.no_vig(dec["a"], dec["b"])
            if self.blend_weights:
                pa = float(market.blend(pred.p_a, p_mkt["a"], self.blend_weights))
                p_est = {"a": pa, "b": 1 - pa}
                used = "blend"
        rows = []
        for side, st in (("a", pred.a), ("b", pred.b)):
            d, p = dec[side], p_est[side]
            row = {"fighter": st.name, "model %": p_model[side]}
            if p_mkt[side] is not None:
                row["market %"] = p_mkt[side]
            if used == "blend":
                row["blend %"] = p
            row["fair line"] = odds.prob_to_american(p)
            if d:
                k = min(odds.kelly_fraction(p, d) * kelly_mult, max_stake)
                row.update({
                    "book line": odds.decimal_to_american(d),
                    "edge %": p - (p_mkt[side] if p_mkt[side] is not None else odds.implied_prob(d)),
                    "EV/$100": 100 * odds.expected_value(p, d),
                    "kelly %": k,
                })
                if bankroll:
                    row["stake"] = round(bankroll * k, 2)
            rows.append(row)
        out = pd.DataFrame(rows)
        out.attrs["used"] = used
        if vig is not None:
            out.attrs["vig"] = vig
        return out

    # ---- lists ---------------------------------------------------------
    def leaders(self, division: str | None = None, active_days: int = 730, limit: int = 25,
                date: pd.Timestamp | None = None) -> pd.DataFrame:
        date = pd.Timestamp(date) if date is not None else pd.Timestamp.today().normalize()
        division = self._weight_class(division) if division else None
        rows = []
        for fid, st in self.states.items():
            if st.last_date is None or (date - st.last_date).days > active_days or st.fights < 2:
                continue
            log = self.fight_log(fid)
            wc = log.iloc[0]["weight_class"]
            if division and wc != division:
                continue
            dob = self.info(fid).get("dob")
            rows.append({"fighter": self.label(fid), "division": wc, "elo": round(st.elo),
                         "ufc record": st.record, "streak": st.streak,
                         "age": round((date - dob).days / 365.25, 1) if not pd.isna(dob) else np.nan,
                         "last fight": st.last_date.date()})
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        return df.sort_values("elo", ascending=False).head(limit).reset_index(drop=True)

    def find_event(self, query: str) -> str:
        names = self.fights.drop_duplicates("event")[["event", "date"]]
        nq = normalize_name(query)
        exact = names[names["event"].map(normalize_name) == nq]
        if len(exact):
            return exact.iloc[0]["event"]
        hits = names[names["event"].map(normalize_name).str.contains(nq, regex=False)]
        if len(hits):
            return hits.sort_values("date", ascending=False).iloc[0]["event"]
        close = difflib.get_close_matches(query, names["event"].tolist(), n=1, cutoff=0.5)
        if close:
            return close[0]
        raise LookupError_(f"No event matching '{query}'.")
