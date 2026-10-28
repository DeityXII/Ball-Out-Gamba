"""Command-line interface: `python -m ballout <command>` or `ballout <command>`."""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from . import config, data, features, market, model, odds
from .analysis import Database, LookupError_

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)
pd.set_option("display.max_colwidth", 60)

MAX_STAKE = 0.05  # never suggest more than this fraction of bankroll on one bet
DISCLAIMER = ("Model output is an estimate from historical stats only - it knows nothing about injuries, "
              "camp changes or weight cuts. Bet only what you can afford to lose.")


def _pct(x, digits=0):
    return "-" if x is None or pd.isna(x) else f"{x * 100:.{digits}f}%"


def _num(x, digits=2):
    return "-" if x is None or pd.isna(x) else f"{x:.{digits}f}"


def _height(inches):
    return "-" if pd.isna(inches) else f"{int(inches) // 12}'{int(inches) % 12}\""


def _header(text):
    print(f"\n{text}\n{'-' * len(text)}")


# ---------------------------------------------------------------------------

def cmd_update(args):
    if not args.skip_download:
        print("Downloading fight data...")
        data.download()
    print("Building tables...")
    tables = data.build()
    print("Replaying fight history and training model...")
    rep = features.replay(tables)
    metrics = {}
    if not args.no_backtest:
        bt = model.backtest(rep.rows, tables["fights"])
        metrics = bt[bt["year"] == "ALL"].iloc[0].to_dict()
        print(f"  walk-forward backtest 2012-present: {metrics['acc_model']:.1%} picks correct, "
              f"log loss {metrics['logloss_model']:.3f} over {metrics['fights']} fights")
    hist_odds = market.build_odds(tables["fights"])
    hist_odds.to_csv(config.PROCESSED_DIR / "odds.csv", index=False)
    weights = market.final_blend_weights(rep.rows, hist_odds) if len(hist_odds) else None
    if weights:
        print(f"  model/market blend weights: model {weights[0]:.2f}, market {weights[1]:.2f}")
    model.save(model.train_win_model(rep.rows), model.method_base_rates(tables["fights"]), metrics, weights)
    rep.rows.to_csv(config.PROCESSED_DIR / "prefight_features.csv", index=False)
    print(f"Done. Tables are in {config.PROCESSED_DIR}")


def cmd_search(args, db: Database):
    hits = db.search(args.query)
    if not hits:
        print("No matches.")
        return
    rows = [{"id": f, "fighter": db.label(f), "ufc record": db.states[f].record,
             "last fight": db.states[f].last_date.date()} for f in hits]
    print(pd.DataFrame(rows).to_string(index=False))


def cmd_fighter(args, db: Database):
    fid = db.find(args.name)
    st = db.states[fid]
    info = db.info(fid)
    today = pd.Timestamp.today().normalize()
    age = (today - info["dob"]).days / 365.25 if not pd.isna(info.get("dob")) else np.nan
    nick = f' "{info["nickname"]}"' if isinstance(info.get("nickname"), str) else ""
    _header(f"{db.label(fid)}{nick}")
    print(f"UFC record {st.record}   Elo {st.elo:.0f} (peak {st.peak_elo:.0f})   streak {st.streak:+d}   "
          f"title fights {st.title_fights}")
    print(f"Age {_num(age, 1)}   height {_height(info.get('height_in'))}   reach {_num(info.get('reach_in'), 0)}\"   "
          f"stance {info.get('stance') if isinstance(info.get('stance'), str) else '-'}   "
          f"last fight {st.last_date:%Y-%m-%d} ({(today - st.last_date).days} days ago)")
    print(f"Wins:   KO/TKO {st.ko_wins}  SUB {st.sub_wins}  DEC {st.dec_wins}")
    print(f"Losses: KO/TKO {st.ko_losses}  SUB {st.sub_losses}  DEC {st.dec_losses}")
    print(f"Fights that went the distance: {_pct(db.distance_rate(fid))}")

    cs = db.career_stats(fid)
    _header("Career stats (UFC)")
    pct_keys = {k for k in cs if "%" in k or "Acc" in k or "Def" in k}
    items = [f"{k}: {_pct(v) if k in pct_keys else _num(v)}" for k, v in cs.items()]
    for i in range(0, len(items), 4):
        print("   ".join(f"{s:22s}" for s in items[i:i + 4]))

    _header(f"Fight log (last {args.fights})")
    log = db.fight_log(fid).head(args.fights)
    show = pd.DataFrame({
        "date": log["date"].dt.date, "opponent": log["opponent"], "res": log["result"],
        "method": log["method"], "rd": log["round"].astype("Int64"), "time": log["time"],
        "sig str": [f"{_num(a, 0)}-{_num(b, 0)}" for a, b in zip(log["sig_landed"], log["opp_sig_landed"])],
        "td": [f"{_num(a, 0)}/{_num(b, 0)}" for a, b in zip(log["td_landed"], log["td_att"])],
        "event": log["event"],
    })
    print(show.to_string(index=False))


def _format_priced(priced: pd.DataFrame) -> pd.DataFrame:
    fmt = priced.copy()
    for c in ("model %", "market %", "blend %", "edge %"):
        if c in fmt:
            fmt[c] = fmt[c].map(lambda x: _pct(x, 1))
    if "kelly %" in fmt:
        fmt["kelly %"] = fmt["kelly %"].map(lambda x: _pct(x, 2))
    if "EV/$100" in fmt:
        fmt["EV/$100"] = fmt["EV/$100"].map(lambda x: f"{x:+.2f}")
    return fmt


def _print_matchup(db: Database, pred, odds_a=None, odds_b=None, bankroll=None, kelly=0.25):
    a, b = pred.a, pred.b
    ia, ib = db.info(a.fighter_id), db.info(b.fighter_id)
    ca, cb = db.career_stats(a.fighter_id), db.career_stats(b.fighter_id)
    date = pred.date

    def age(info):
        return (date - info["dob"]).days / 365.25 if not pd.isna(info.get("dob")) else np.nan

    _header(f"{db.label(a.fighter_id)}  vs  {db.label(b.fighter_id)}   ({pred.methods['weight_class']})")
    rows = [
        ("UFC record", a.record, b.record),
        ("Elo", f"{a.elo:.0f}", f"{b.elo:.0f}"),
        ("Streak", f"{a.streak:+d}", f"{b.streak:+d}"),
        ("Age", _num(age(ia), 1), _num(age(ib), 1)),
        ("Height", _height(ia.get("height_in")), _height(ib.get("height_in"))),
        ("Reach", _num(ia.get("reach_in"), 0), _num(ib.get("reach_in"), 0)),
        ("Stance", ia.get("stance") if isinstance(ia.get("stance"), str) else "-",
         ib.get("stance") if isinstance(ib.get("stance"), str) else "-"),
        ("Days since last fight", (date - a.last_date).days if a.last_date is not None else "-",
         (date - b.last_date).days if b.last_date is not None else "-"),
        ("Wins KO/SUB/DEC", f"{a.ko_wins}/{a.sub_wins}/{a.dec_wins}", f"{b.ko_wins}/{b.sub_wins}/{b.dec_wins}"),
        ("Losses KO/SUB/DEC", f"{a.ko_losses}/{a.sub_losses}/{a.dec_losses}",
         f"{b.ko_losses}/{b.sub_losses}/{b.dec_losses}"),
    ]
    for k in ("SLpM", "SApM", "Str. Acc", "Str. Def", "TD Avg/15", "TD Acc", "TD Def",
              "Sub Avg/15", "KD/15", "Ctrl %", "Avg fight (min)"):
        fmt = _pct if ("%" in k or "Acc" in k or "Def" in k) else _num
        rows.append((k, fmt(ca[k]), fmt(cb[k])))
    rows.append(("Went the distance", _pct(db.distance_rate(a.fighter_id)), _pct(db.distance_rate(b.fighter_id))))
    print(pd.DataFrame(rows, columns=["", a.name, b.name]).to_string(index=False))

    h2h = db.head_to_head(a.fighter_id, b.fighter_id)
    if len(h2h):
        _header("Previous meetings")
        for r in h2h.itertuples():
            print(f"  {r.date:%Y-%m-%d}  {a.name} {r.result} by {r.method} R{int(r.round)} {r.time}  ({r.event})")
    common = db.common_opponents(a.fighter_id, b.fighter_id)
    if len(common):
        _header("Common opponents")
        print(common.head(10).to_string(index=False))

    m = pred.methods
    _header("Model")
    print(f"Win probability: {a.name} {_pct(pred.p_a, 1)} ({odds.prob_to_american(pred.p_a)})   "
          f"{b.name} {_pct(1 - pred.p_a, 1)} ({odds.prob_to_american(1 - pred.p_a)})")
    meth = pd.DataFrame(
        [[a.name, _pct(m["A_KO"], 1), _pct(m["A_SUB"], 1), _pct(m["A_DEC"], 1)],
         [b.name, _pct(m["B_KO"], 1), _pct(m["B_SUB"], 1), _pct(m["B_DEC"], 1)]],
        columns=["wins by", "KO/TKO", "SUB", "DEC"])
    print(meth.to_string(index=False))
    print(f"Goes the distance: {_pct(m['distance'], 1)} ({odds.prob_to_american(m['distance'])})   "
          f"Inside the distance: {_pct(1 - m['distance'], 1)} ({odds.prob_to_american(1 - m['distance'])})")
    wm = db.win_model
    contribs = {k: v / wm.scale[wm.columns.index(k)] * wm.weights[wm.columns.index(k)]
                for k, v in pred.diffs.items()}
    drivers = [f"{features.FEATURE_LABELS[k[2:]]} -> {a.name if c > 0 else b.name}"
               for k, c in sorted(contribs.items(), key=lambda kv: -abs(kv[1]))[:5] if abs(c) >= 0.02]
    if drivers:
        print("Biggest factors: " + "; ".join(drivers))

    if odds_a is not None or odds_b is not None:
        priced = db.price(pred, odds_a, odds_b, bankroll, kelly, MAX_STAKE)
        _header("Betting value")
        print(_format_priced(priced).to_string(index=False))
        if priced.attrs["used"] == "blend":
            print("Edges use the blend of model and market (the most accurate estimate in backtests; "
                  "see `backtest`).")
        else:
            print("Give odds for both fighters to get the market-blended estimate; "
                  "raw model edges lost money in backtests.")
        if "vig" in priced.attrs:
            print(f"Bookmaker margin (vig): {_pct(priced.attrs['vig'], 1)}.  Kelly sizing is {kelly:g}x Kelly, "
                  f"capped at {_pct(MAX_STAKE)} of bankroll.")
        if "market %" in priced and abs(priced["model %"].iloc[0] - priced["market %"].iloc[0]) > 0.15:
            print("Caution: the stats model and the market disagree by 15+ points. The market is usually "
                  "right when that happens (injury, short notice, style) - the blend leans on it accordingly.")

    for n in pred.notes:
        print(f"Note: {n}")


def cmd_matchup(args, db: Database):
    a = db.find(args.fighter_a)
    b = db.find(args.fighter_b)
    pred = db.predict(a, b, args.date, args.weight_class)
    oa, ob = (args.odds or (None, None))
    _print_matchup(db, pred, oa, ob, args.bankroll, args.kelly)
    print(f"\n{DISCLAIMER}")


def cmd_card(args, db: Database):
    card = pd.read_csv(args.file, dtype=str, keep_default_na=False)
    card.columns = [c.strip().lower() for c in card.columns]
    if not {"fighter_a", "fighter_b"} <= set(card.columns):
        sys.exit("Card CSV needs columns: fighter_a, fighter_b (optional: odds_a, odds_b, weight_class)")
    rows = []
    for r in card.itertuples(index=False):
        try:
            a, b = db.find(r.fighter_a), db.find(r.fighter_b)
        except LookupError_ as e:
            print(f"Skipping {r.fighter_a} vs {r.fighter_b}: {e}")
            continue
        wc = getattr(r, "weight_class", "") or None
        pred = db.predict(a, b, args.date, wc)
        oa, ob = getattr(r, "odds_a", "") or None, getattr(r, "odds_b", "") or None
        if args.detail:
            _print_matchup(db, pred, oa, ob, args.bankroll, args.kelly)
        priced = db.price(pred, oa, ob, args.bankroll, args.kelly, MAX_STAKE)
        for i, side in enumerate(priced.to_dict("records")):
            rows.append({
                "bout": f"{pred.a.name} vs {pred.b.name}", "pick": side["fighter"],
                "model %": side["model %"], "market %": side.get("market %", np.nan),
                "est %": side.get("blend %", side["model %"]), "fair": side["fair line"],
                "book": side.get("book line", ""), "edge %": side.get("edge %", np.nan),
                "EV/$100": side.get("EV/$100", np.nan), "kelly %": side.get("kelly %", np.nan),
                "stake": side.get("stake", np.nan),
                "KO %": pred.methods["A_KO" if i == 0 else "B_KO"],
                "SUB %": pred.methods["A_SUB" if i == 0 else "B_SUB"],
                "DEC %": pred.methods["A_DEC" if i == 0 else "B_DEC"],
                "distance %": pred.methods["distance"],
                "notes": " ".join(pred.notes),
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return
    if args.out:
        out.to_csv(args.out, index=False)
        print(f"Wrote {args.out}")

    _header("Card summary")
    fav = out.loc[out.groupby("bout", sort=False)["est %"].idxmax()]
    summary = pd.DataFrame({
        "bout": fav["bout"], "pick": fav["pick"], "win %": fav["est %"].map(lambda x: _pct(x, 1)),
        "stats model %": fav["model %"].map(lambda x: _pct(x, 1)),
        "market %": fav["market %"].map(lambda x: _pct(x, 1)),
        "fair": fav["fair"], "distance %": fav["distance %"].map(lambda x: _pct(x, 0)),
    })
    print(summary.to_string(index=False))

    priced = out[out["book"] != ""]
    if len(priced):
        value = priced[priced["edge %"] >= args.min_edge].sort_values("EV/$100", ascending=False)
        _header(f"Value bets (edge >= {args.min_edge:.0%} over the no-vig line)")
        if value.empty:
            print("None - no side beats the no-vig line by that much on this card.")
        else:
            show = value[["bout", "pick", "book", "fair", "est %", "edge %", "EV/$100", "kelly %"]
                         + (["stake"] if args.bankroll else [])].copy()
            show["est %"] = show["est %"].map(lambda x: _pct(x, 1))
            show["edge %"] = show["edge %"].map(lambda x: _pct(x, 1))
            show["EV/$100"] = show["EV/$100"].map(lambda x: f"{x:+.2f}")
            show["kelly %"] = show["kelly %"].map(lambda x: _pct(x, 2))
            print(show.to_string(index=False))
    print(f"\n{DISCLAIMER}")


def cmd_leaders(args, db: Database):
    df = db.leaders(args.division, args.active_days, args.limit)
    print(df.to_string() if len(df) else "No active fighters found for that division.")


def cmd_event(args, db: Database):
    name = db.find_event(args.name)
    f = db.fights[db.fights["event"] == name].sort_values("bout_order")
    _header(f"{name}  -  {f.iloc[0]['date']:%Y-%m-%d}, {f.iloc[0]['location']}")
    show = pd.DataFrame({
        "winner": np.where(f["result_a"] == "W", f["fighter_a"], np.where(f["result_b"] == "W", f["fighter_b"], "-")),
        "loser": np.where(f["result_a"] == "W", f["fighter_b"], np.where(f["result_b"] == "W", f["fighter_a"], "-")),
        "result": np.where(f["result_a"].isin(["W", "L"]), "", f["result_a"] + ": " + f["fighter_a"] + " vs " + f["fighter_b"]),
        "class": f["weight_class"] + np.where(f["title_bout"], " (title)", ""),
        "method": f["method"], "rd": f["round"].astype("Int64"), "time": f["time"],
    })
    print(show.to_string(index=False))


def cmd_backtest(args):
    tables = data.load()
    rep = features.replay(tables)
    bt = model.backtest(rep.rows, tables["fights"], args.start_year)
    show = bt.copy()
    for c in ("acc_model", "acc_elo", "acc_model_exp"):
        show[c] = show[c].map(lambda x: _pct(x, 1))
    for c in ("logloss_model", "logloss_elo", "brier_distance_model", "brier_distance_base"):
        show[c] = show[c].map(lambda x: _num(x, 3))
    print(show.rename(columns={
        "acc_model": "model acc", "acc_elo": "elo-only acc", "acc_model_exp": "acc (both 2+ fights)",
        "logloss_model": "model logloss", "logloss_elo": "elo logloss",
        "brier_distance_model": "distance brier", "brier_distance_base": "base-rate brier",
    }).to_string(index=False))
    _header("Calibration (favourite's side)")
    cal = bt.attrs["calibration"].copy()
    cal["predicted"] = cal["predicted"].map(lambda x: _pct(x, 1))
    cal["actual"] = cal["actual"].map(lambda x: _pct(x, 1))
    print(cal.to_string(index=False))
    print("\nEach year is predicted using a model trained only on earlier fights. Lower log loss / Brier is better; "
          "a coin flip scores 0.693 log loss.")

    hist_odds = market.build_odds(tables["fights"], verbose=False)
    if hist_odds.empty:
        print("\n(No historical odds downloaded - run `update` for the market comparison.)")
        return
    wf = market.walk_forward(rep.rows, hist_odds)
    _header(f"Against the betting market ({wf['date'].min():%Y}-{wf['date'].max():%Y}, same fights)")
    summ = market.summary(wf)
    summ["accuracy"] = summ["accuracy"].map(lambda x: _pct(x, 1))
    summ["log loss"] = summ["log loss"].map(lambda x: _num(x, 4))
    summ["brier"] = summ["brier"].map(lambda x: _num(x, 4))
    print(summ.to_string(index=False))
    for label, col in (("stats model alone", "p_model"), ("model + market blend", "p_blend")):
        _header(f"Flat 1-unit bets on every edge, using the {label}")
        roi = market.roi_table(wf, col)
        roi["min edge"] = roi["min edge"].map(lambda x: _pct(x))
        roi["win %"] = roi["win %"].map(lambda x: _pct(x, 1))
        roi["underdog bets %"] = roi["underdog bets %"].map(lambda x: _pct(x))
        roi["profit (units)"] = roi["profit (units)"].map(lambda x: f"{x:+.1f}")
        roi["ROI"] = roi["ROI"].map(lambda x: "-" if pd.isna(x) else f"{x:+.1%}")
        print(roi.to_string(index=False))
    print("\nOdds in this history carry ~1% bookmaker margin (sharp/average lines); a typical sportsbook "
          "charges 4-5%, which would cut every ROI above by roughly 2-3 points. Shop for the best line.")


# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ballout", description="UFC fight history + betting analysis toolkit")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("update", help="download latest fight data, rebuild tables and retrain model")
    s.add_argument("--skip-download", action="store_true", help="rebuild from already-downloaded raw files")
    s.add_argument("--no-backtest", action="store_true", help="skip the walk-forward backtest (faster)")

    s = sub.add_parser("search", help="find fighters by (partial) name")
    s.add_argument("query")

    s = sub.add_parser("fighter", help="fighter profile, career stats and fight log")
    s.add_argument("name")
    s.add_argument("--fights", type=int, default=10, help="number of recent fights to list")

    s = sub.add_parser("matchup", help="head-to-head analysis and model prediction")
    s.add_argument("fighter_a")
    s.add_argument("fighter_b")
    s.add_argument("--odds", nargs=2, metavar=("ODDS_A", "ODDS_B"),
                   help="sportsbook odds for each fighter, American (-150 +130) or decimal (1.67 2.30)")
    s.add_argument("--date", help="fight date (default today), affects age and layoff")
    s.add_argument("--weight-class", help="e.g. Lightweight (default: most recent division)")
    s.add_argument("--bankroll", type=float, help="bankroll for stake sizing")
    s.add_argument("--kelly", type=float, default=0.25, help="Kelly multiplier (default 0.25 = quarter Kelly)")

    s = sub.add_parser("card", help="analyse a whole card from a CSV of matchups and odds")
    s.add_argument("file", help="CSV with fighter_a, fighter_b[, odds_a, odds_b, weight_class]")
    s.add_argument("--date", help="event date (default today)")
    s.add_argument("--bankroll", type=float)
    s.add_argument("--kelly", type=float, default=0.25)
    s.add_argument("--min-edge", type=float, default=0.05,
                   help="minimum edge to list as value (default 0.05; smaller edges ~broke even in backtests)")
    s.add_argument("--detail", action="store_true", help="also print the full breakdown for every fight")
    s.add_argument("--out", help="write all results to this CSV")

    s = sub.add_parser("leaders", help="top active fighters by Elo")
    s.add_argument("--division", help="e.g. Lightweight, \"Women's Flyweight\"")
    s.add_argument("--limit", type=int, default=25)
    s.add_argument("--active-days", type=int, default=730, help="must have fought within this many days")

    s = sub.add_parser("event", help="results of a past event")
    s.add_argument("name")

    s = sub.add_parser("backtest", help="walk-forward accuracy and calibration of the model")
    s.add_argument("--start-year", type=int, default=2012)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "update":
            return cmd_update(args)
        if args.command == "backtest":
            return cmd_backtest(args)
        db = Database()
        handler = {"search": cmd_search, "fighter": cmd_fighter, "matchup": cmd_matchup,
                   "card": cmd_card, "leaders": cmd_leaders, "event": cmd_event}[args.command]
        handler(args, db)
    except (LookupError_, FileNotFoundError, ValueError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
