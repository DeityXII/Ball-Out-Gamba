"""Download the raw UFC stats CSVs and turn them into clean, joined tables.

Output tables (written to data/processed/):
  events.csv         one row per event
  fights.csv         one row per fight: fighters, result, method, round, time
  fighter_fights.csv one row per fighter per fight, with that fighter's totals
                     and the opponent's totals (the main analysis table)
  rounds.csv         round-by-round stats per fighter
  fighters.csv       physical attributes (height, reach, stance, DOB)
"""

from __future__ import annotations

import re
import time

import numpy as np
import pandas as pd
import requests

from . import config

WEIGHT_LIMITS = {
    "Strawweight": 115,
    "Flyweight": 125,
    "Bantamweight": 135,
    "Featherweight": 145,
    "Lightweight": 155,
    "Welterweight": 170,
    "Middleweight": 185,
    "Light Heavyweight": 205,
    "Heavyweight": 265,
}
# Order matters: check longer names before the names they contain.
_CLASS_ORDER = [
    "Super Heavyweight", "Light Heavyweight", "Heavyweight", "Middleweight",
    "Welterweight", "Lightweight", "Featherweight", "Bantamweight",
    "Flyweight", "Strawweight", "Catch Weight", "Open Weight",
]

METHOD_MAP = {
    "KO/TKO": ("KO/TKO", "KO"),
    "TKO - Doctor's Stoppage": ("TKO (Doctor)", "KO"),
    "Submission": ("Submission", "SUB"),
    "Decision - Unanimous": ("U-DEC", "DEC"),
    "Decision - Split": ("S-DEC", "DEC"),
    "Decision - Majority": ("M-DEC", "DEC"),
    "DQ": ("DQ", "OTHER"),
    "Overturned": ("Overturned", "OTHER"),
    "Could Not Continue": ("CNC", "OTHER"),
    "Other": ("Other", "OTHER"),
}

# landed/attempted columns in the raw stats file -> clean prefix
_PAIR_COLS = {
    "SIG.STR.": "sig", "TOTAL STR.": "str", "TD": "td", "HEAD": "head",
    "BODY": "body", "LEG": "leg", "DISTANCE": "dist", "CLINCH": "clinch",
    "GROUND": "ground",
}
STAT_COLS = (
    [f"{p}_{s}" for p in _PAIR_COLS.values() for s in ("landed", "att")]
    + ["kd", "sub_att", "rev", "ctrl_sec"]
)


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------

def _fetch(session: requests.Session, url: str) -> bytes:
    for attempt in range(4):
        try:
            resp = session.get(url, timeout=120)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))


def download(verbose: bool = True) -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    for name in config.SOURCE_FILES:
        content = _fetch(session, f"{config.SOURCE_BASE}/{name}")
        (config.RAW_DIR / name).write_bytes(content)
        if verbose:
            print(f"  downloaded {name} ({len(content) / 1e6:.1f} MB)")
    try:  # optional: everything except the market blend works without it
        content = _fetch(session, config.ODDS_URL)
        (config.RAW_DIR / config.ODDS_FILE).write_bytes(content)
        if verbose:
            print(f"  downloaded historical odds ({len(content) / 1e6:.1f} MB)")
    except requests.RequestException as e:
        if verbose:
            print(f"  warning: historical odds unavailable ({e}); market blend disabled")


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------

def _clean_str(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)


def parse_of(value) -> tuple[float, float]:
    """'24 of 47' -> (24, 47)."""
    if not isinstance(value, str):
        return (np.nan, np.nan)
    m = re.match(r"\s*(\d+)\s+of\s+(\d+)", value)
    return (float(m.group(1)), float(m.group(2))) if m else (np.nan, np.nan)


def parse_mmss(value) -> float:
    """'4:54' -> 294 seconds."""
    if not isinstance(value, str) or ":" not in value:
        return np.nan
    m, s = value.strip().split(":")[:2]
    try:
        return int(m) * 60 + int(s)
    except ValueError:
        return np.nan


def parse_height(value) -> float:
    """5' 11" -> 71 inches."""
    if not isinstance(value, str):
        return np.nan
    m = re.match(r"\s*(\d+)'\s*(\d+)", value)
    return float(int(m.group(1)) * 12 + int(m.group(2))) if m else np.nan


def parse_number(value) -> float:
    """'155 lbs.' -> 155, '72"' -> 72, '--' -> NaN."""
    if not isinstance(value, str):
        return np.nan
    m = re.search(r"(\d+(?:\.\d+)?)", value)
    return float(m.group(1)) if m else np.nan


def parse_time_format(fmt) -> list[int] | None:
    """'3 Rnd (5-5-5)' -> [5, 5, 5] minutes; 'No Time Limit' -> None."""
    if not isinstance(fmt, str):
        return None
    m = re.search(r"\(([\d\-]+)\)", fmt)
    if not m:
        return None
    return [int(x) for x in m.group(1).split("-") if x]


def normalize_weight_class(raw) -> tuple[str, bool, bool]:
    """-> (weight class, is_women, is_title_bout)."""
    raw = raw if isinstance(raw, str) else ""
    women = "Women's" in raw
    title = "Title" in raw or "Championship" in raw
    cls = next((c for c in _CLASS_ORDER if c in raw), "Open Weight")
    if women and cls in WEIGHT_LIMITS:
        cls = f"Women's {cls}"
    return cls, women, title


def weight_limit(weight_class: str) -> float:
    return WEIGHT_LIMITS.get(weight_class.replace("Women's ", ""), np.nan)


def fight_seconds(round_: float, time_sec: float, fmt) -> float:
    """Total elapsed fight time given the finishing round and clock."""
    if pd.isna(round_) or pd.isna(time_sec):
        return np.nan
    lengths = parse_time_format(fmt)
    r = int(round_)
    if not lengths:
        return float(time_sec)
    prior = sum(lengths[: r - 1]) if r - 1 <= len(lengths) else sum(lengths) + 5 * (r - 1 - len(lengths))
    return prior * 60.0 + time_sec


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def _read_raw(name: str) -> pd.DataFrame:
    path = config.RAW_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run `ballout update` first")
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def _build_fighters() -> pd.DataFrame:
    tott = _read_raw("ufc_fighter_tott.csv")
    details = _read_raw("ufc_fighter_details.csv")
    df = pd.DataFrame({
        "fighter_id": tott["URL"].str.rsplit("/", n=1).str[-1],
        "name": _clean_str(tott["FIGHTER"]),
        "height_in": tott["HEIGHT"].map(parse_height),
        "weight_lbs": tott["WEIGHT"].map(parse_number),
        "reach_in": tott["REACH"].map(parse_number),
        "stance": _clean_str(tott["STANCE"]),
        "dob": pd.to_datetime(tott["DOB"], format="%b %d, %Y", errors="coerce"),
    })
    nick = pd.DataFrame({
        "fighter_id": details["URL"].str.rsplit("/", n=1).str[-1],
        "nickname": _clean_str(details["NICKNAME"]),
    })
    df = df.merge(nick, on="fighter_id", how="left")
    return df.drop_duplicates("fighter_id").reset_index(drop=True)


def _assign_fighter_ids(names: pd.Series, classes: pd.Series, fighters: pd.DataFrame) -> pd.Series:
    """Map each bout-side name to a fighter id.

    A handful of names belong to two different fighters (e.g. two Bruno
    Silvas); those are resolved by picking the one whose listed weight is
    closest to the bout's weight class limit.
    """
    by_name = fighters.groupby("name")
    lookup = {name: grp[["fighter_id", "weight_lbs"]].values.tolist() for name, grp in by_name}
    out = []
    for name, cls in zip(names, classes):
        cands = lookup.get(name)
        if not cands:
            out.append("name:" + name)
        elif len(cands) == 1:
            out.append(cands[0][0])
        else:
            limit = weight_limit(cls)
            def dist(c):
                w = c[1]
                if pd.isna(w):
                    return 1e6
                return abs(w - limit) if not pd.isna(limit) else 1e3
            out.append(min(cands, key=dist)[0])
    return pd.Series(out, index=names.index)


def build(verbose: bool = True) -> dict[str, pd.DataFrame]:
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Events ---------------------------------------------------------------
    ev = _read_raw("ufc_event_details.csv")
    events = pd.DataFrame({
        "event_id": ev["URL"].str.rsplit("/", n=1).str[-1],
        "event": _clean_str(ev["EVENT"]),
        "date": pd.to_datetime(ev["DATE"].str.strip(), format="%B %d, %Y", errors="coerce"),
        "location": _clean_str(ev["LOCATION"]),
    }).drop_duplicates("event")
    event_lookup = events.set_index("event")

    # Fights ---------------------------------------------------------------
    res = _read_raw("ufc_fight_results.csv")
    res["EVENT"] = _clean_str(res["EVENT"])
    res["BOUT"] = _clean_str(res["BOUT"])
    res["fight_id"] = res["URL"].str.strip().str.rsplit("/", n=1).str[-1]
    res["bout_order"] = res.groupby("EVENT").cumcount()  # 0 = main event
    # (event, bout) -> fight id, including events listed under two names.
    key_to_fight = dict(zip(zip(res["EVENT"], res["BOUT"]), res["fight_id"]))

    res["_known_event"] = res["EVENT"].isin(event_lookup.index)
    res = (res.sort_values("_known_event", ascending=False, kind="stable")
              .drop_duplicates("fight_id")
              .sort_index())
    res = res[res["_known_event"]].copy()

    sides = res["BOUT"].str.split(" vs. ", n=1, expand=True)
    outcome = res["OUTCOME"].str.strip().str.split("/", expand=True)
    wc = res["WEIGHTCLASS"].map(normalize_weight_class)
    method_raw = _clean_str(res["METHOD"])
    method = method_raw.map(lambda m: METHOD_MAP.get(m, (m, "OTHER")))

    fights = pd.DataFrame({
        "fight_id": res["fight_id"].values,
        "event": res["EVENT"].values,
        "event_id": event_lookup.loc[res["EVENT"], "event_id"].values,
        "date": event_lookup.loc[res["EVENT"], "date"].values,
        "location": event_lookup.loc[res["EVENT"], "location"].values,
        "bout_order": res["bout_order"].values,
        "fighter_a": _clean_str(sides[0]).values,
        "fighter_b": _clean_str(sides[1]).values,
        "result_a": outcome[0].values,
        "result_b": outcome[1].values,
        "weight_class": [w[0] for w in wc],
        "women": [w[1] for w in wc],
        "title_bout": [w[2] for w in wc],
        "weight_class_raw": _clean_str(res["WEIGHTCLASS"]).values,
        "method": [m[0] for m in method],
        "method_group": [m[1] for m in method],
        "round": pd.to_numeric(res["ROUND"], errors="coerce").values,
        "time": res["TIME"].str.strip().values,
        "time_format": res["TIME FORMAT"].str.strip().values,
        "referee": _clean_str(res["REFEREE"]).values,
        "details": _clean_str(res["DETAILS"]).values,
    })
    fights["scheduled_rounds"] = fights["time_format"].map(
        lambda f: len(parse_time_format(f)) if parse_time_format(f) else np.nan)
    time_sec = fights["time"].map(parse_mmss)
    fights["fight_seconds"] = [
        fight_seconds(r, t, f) for r, t, f in zip(fights["round"], time_sec, fights["time_format"])
    ]
    fights["winner"] = np.where(fights["result_a"] == "W", fights["fighter_a"],
                                np.where(fights["result_b"] == "W", fights["fighter_b"], None))

    fighters = _build_fighters()
    fights["fighter_a_id"] = _assign_fighter_ids(fights["fighter_a"], fights["weight_class"], fighters)
    fights["fighter_b_id"] = _assign_fighter_ids(fights["fighter_b"], fights["weight_class"], fighters)
    fights = fights.sort_values(["date", "bout_order"], ascending=[True, False]).reset_index(drop=True)

    # Fighters only known by name (no profile row) still need a row.
    known = set(fighters["fighter_id"])
    extra = []
    for col_id, col_name in (("fighter_a_id", "fighter_a"), ("fighter_b_id", "fighter_b")):
        for fid, name in zip(fights[col_id], fights[col_name]):
            if fid not in known:
                known.add(fid)
                extra.append({"fighter_id": fid, "name": name})
    if extra:
        fighters = pd.concat([fighters, pd.DataFrame(extra)], ignore_index=True)

    # Round stats ----------------------------------------------------------
    st = _read_raw("ufc_fight_stats.csv").dropna(subset=["FIGHTER", "ROUND"])
    st["EVENT"] = _clean_str(st["EVENT"])
    st["BOUT"] = _clean_str(st["BOUT"])
    st["FIGHTER"] = _clean_str(st["FIGHTER"])
    st["fight_id"] = [key_to_fight.get(k) for k in zip(st["EVENT"], st["BOUT"])]
    st = st.dropna(subset=["fight_id"])
    st = st[st["fight_id"].isin(set(fights["fight_id"]))]
    st = st.drop_duplicates(["fight_id", "ROUND", "FIGHTER"])

    rounds = pd.DataFrame({
        "fight_id": st["fight_id"].values,
        "fighter": st["FIGHTER"].values,
        "round": st["ROUND"].str.extract(r"(\d+)")[0].astype(float).values,
    })
    for raw_col, prefix in _PAIR_COLS.items():
        pairs = st[raw_col].map(parse_of)
        rounds[f"{prefix}_landed"] = [p[0] for p in pairs]
        rounds[f"{prefix}_att"] = [p[1] for p in pairs]
    rounds["kd"] = pd.to_numeric(st["KD"], errors="coerce").values
    rounds["sub_att"] = pd.to_numeric(st["SUB.ATT"], errors="coerce").values
    rounds["rev"] = pd.to_numeric(st["REV."], errors="coerce").values
    rounds["ctrl_sec"] = st["CTRL"].map(parse_mmss).values

    totals = rounds.groupby(["fight_id", "fighter"], as_index=False)[STAT_COLS].sum(min_count=1)

    # Fighter-fight long table --------------------------------------------
    base_cols = ["fight_id", "event", "date", "bout_order", "weight_class", "women",
                 "title_bout", "method", "method_group", "round", "time",
                 "fight_seconds", "scheduled_rounds", "referee", "details"]
    a = fights[base_cols].assign(
        fighter_id=fights["fighter_a_id"], fighter=fights["fighter_a"],
        opponent_id=fights["fighter_b_id"], opponent=fights["fighter_b"],
        result=fights["result_a"])
    b = fights[base_cols].assign(
        fighter_id=fights["fighter_b_id"], fighter=fights["fighter_b"],
        opponent_id=fights["fighter_a_id"], opponent=fights["fighter_a"],
        result=fights["result_b"])
    ff = pd.concat([a, b], ignore_index=True)
    own = totals.rename(columns={"fighter": "_name"})
    ff = ff.merge(own, left_on=["fight_id", "fighter"], right_on=["fight_id", "_name"], how="left").drop(columns="_name")
    opp = totals.rename(columns={c: f"opp_{c}" for c in STAT_COLS}).rename(columns={"fighter": "_name"})
    ff = ff.merge(opp, left_on=["fight_id", "opponent"], right_on=["fight_id", "_name"], how="left").drop(columns="_name")
    ff["has_stats"] = ff["sig_landed"].notna() & ff["opp_sig_landed"].notna()
    ff = ff.sort_values(["date", "bout_order", "fight_id"], ascending=[True, False, True]).reset_index(drop=True)

    tables = {"events": events, "fights": fights, "fighter_fights": ff,
              "rounds": rounds, "fighters": fighters}
    for name, df in tables.items():
        df.to_csv(config.PROCESSED_DIR / f"{name}.csv", index=False)
    if verbose:
        print(f"  {len(events)} events, {len(fights)} fights, {len(fighters)} fighters, "
              f"{len(rounds)} fighter-rounds "
              f"({fights['date'].min():%Y-%m-%d} to {fights['date'].max():%Y-%m-%d})")
    return tables


def load() -> dict[str, pd.DataFrame]:
    """Load processed tables (run `ballout update` first)."""
    out = {}
    for name, dates in (("events", ["date"]), ("fights", ["date"]),
                        ("fighter_fights", ["date"]), ("fighters", ["dob"])):
        path = config.PROCESSED_DIR / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing - run `ballout update` first")
        out[name] = pd.read_csv(path, parse_dates=dates, low_memory=False)
    return out
