"""Command-line interface: `python -m ballout <command>` or `ballout <command>`."""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

import requests

from . import bfo, config, data, features, footage, market, model, news, odds, upcoming
from .analysis import Database, LookupError_

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)
pd.set_option("display.max_colwidth", 60)

MAX_STAKE = 0.05  # never suggest more than this fraction of bankroll on one bet
DISCLAIMER = ("These are estimates, not certainties: check the news (`news`, `--news`) for injuries, "
              "replacements and weight cuts, and bet only what you can afford to lose.")


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
    if not args.no_live_odds:
        print("Updating closing lines from BestFightOdds...")
        try:
            closing = bfo.update_history()
            if len(closing):
                closing.to_csv(config.PROCESSED_DIR / market.BFO_CLOSING, index=False)
        except requests.RequestException as e:
            print(f"  warning: BestFightOdds unavailable ({e}); using previously saved lines")
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


def _print_headlines(name: str, headlines, limit: int = 6):
    flags = news.summarize_flags(headlines)
    print(f"{name}: " + (f"FLAGS - {flags}" if flags else "no injury / withdrawal / weight flags")
          + ("" if headlines else " (no recent headlines found)"))
    for h in headlines[:limit]:
        tag = f" [{', '.join(h.flags)}]" if h.flags else ""
        when = f"{h.published:%b %d}" if not pd.isna(h.published) else "     "
        print(f"  {when}  {h.title[:110]}{tag}  ({h.source})")


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
    drivers = [f"{label} -> {who}" for label, who in db.drivers(pred)]
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
    if args.live and not args.odds:
        live = upcoming.live_odds_for(db, a, b)
        if live:
            ev_name, ev_date, oa, ob, books, n = live
            if not pd.isna(ev_date) and not args.date:
                pred = db.predict(a, b, ev_date, args.weight_class)
            print(f"Live odds ({ev_name}, best of {n} sportsbooks): {pred.a.name} "
                  f"{odds.decimal_to_american(oa)} at {books[0]}, {pred.b.name} {odds.decimal_to_american(ob)} "
                  f"at {books[1]}")
        else:
            print("This fight isn't on an upcoming card at BestFightOdds; showing the model only.")
    _print_matchup(db, pred, oa, ob, args.bankroll, args.kelly)
    _header("Where to watch")
    meetings = db.head_to_head(a, b)
    for r in meetings.itertuples():
        print(f"  Their {r.date:%Y} fight: {footage.links(pred.a.name, pred.b.name, r.event)['UFC YouTube']}")
    for st in (pred.a, pred.b):
        print(f"  {st.name}: {footage.fighter_links(st.name)['UFC YouTube']}")
    print(f"  More: `footage \"{pred.a.name}\"` lists a link for every fight.")
    if args.news:
        _header("Recent news")
        session = requests.Session()
        for st in (pred.a, pred.b):
            _print_headlines(st.name, news.fighter_news(st.name, days=args.news_days, session=session))
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
        value = priced[priced["EV/$100"] >= 100 * args.min_ev].sort_values("EV/$100", ascending=False)
        _header(f"Value bets (expected return >= {args.min_ev:.0%} at the listed price)")
        if value.empty:
            print("None on this card at these prices.")
        else:
            show = value[["bout", "pick", "book", "fair", "est %", "edge %", "EV/$100", "kelly %"]
                         + (["stake"] if args.bankroll else [])].copy()
            show["est %"] = show["est %"].map(lambda x: _pct(x, 1))
            show["edge %"] = show["edge %"].map(lambda x: _pct(x, 1))
            show["EV/$100"] = show["EV/$100"].map(lambda x: f"{x:+.2f}")
            show["kelly %"] = show["kelly %"].map(lambda x: _pct(x, 2))
            print(show.to_string(index=False))
    print(f"\n{DISCLAIMER}")


def cmd_upcoming(args, db: Database):
    print("Fetching live lines from BestFightOdds...")
    analyses = upcoming.analyse(db, args.event, args.unscheduled, args.news, args.news_days,
                                args.bankroll, args.kelly, MAX_STAKE)
    if not analyses:
        print("No upcoming UFC events found" + (f" matching '{args.event}'." if args.event else "."))
        return
    for ea in analyses:
        when = "date TBA" if pd.isna(ea.date) else f"{ea.date:%a %b %d %Y}"
        _header(f"{ea.name}  -  {when}   {ea.url}")
        f = ea.fights
        if f.empty:
            print("No lines posted yet.")
            continue
        show = pd.DataFrame({
            "fight": f["fighter1"] + " vs " + f["fighter2"],
            "market": [f"{_pct(p, 0)} / {_pct(1 - p, 0)}" for p in f["p1_market"]],
            "model": [f"{_pct(p, 0)} / {_pct(1 - p, 0)}" if not pd.isna(p) else "no data" for p in f["p1_model"]],
            "ours": [f"{_pct(p, 1)} / {_pct(1 - p, 1)}" for p in f["p1_est"]],
            "best prices": [f"{odds.decimal_to_american(a)} {ba} / {odds.decimal_to_american(b)} {bb}"
                            for a, ba, b, bb in zip(f["dec1_best"], f["book1_best"], f["dec2_best"], f["book2_best"])],
            "EV": [f"{e1:+.0%} / {e2:+.0%}" for e1, e2 in zip(f["ev1"], f["ev2"])],
            "moved": [("-" if pd.isna(m) else f"{m * 100:+.1f}") for m in f["move"]],
        })
        print(show.to_string(index=False))
        if f["move"].notna().any():
            since = f["move_since"].dropna().min()
            print(f"'moved' = change in {f['fighter1'].iloc[0].split()[-1]}-side market % since first checked "
                  f"({since:%b %d %H:%M}); run `upcoming` regularly to track line movement.")
        if "p_decision" in f and f["p_decision"].notna().any():
            _header("How the market expects it to end (from props)")
            f = f[f["p_decision"].notna()]
            pm = pd.DataFrame({
                "fight": f["fighter1"] + " vs " + f["fighter2"],
                "decision": f["p_decision"].map(lambda x: _pct(x, 0)),
                "fighter1 KO/SUB/DEC": [f"{_pct(a, 0)}/{_pct(b, 0)}/{_pct(c, 0)}" for a, b, c in
                                        zip(f.get("p_1_KO", np.nan), f.get("p_1_SUB", np.nan), f.get("p_1_DEC", np.nan))],
                "fighter2 KO/SUB/DEC": [f"{_pct(a, 0)}/{_pct(b, 0)}/{_pct(c, 0)}" for a, b, c in
                                        zip(f.get("p_2_KO", np.nan), f.get("p_2_SUB", np.nan), f.get("p_2_DEC", np.nan))],
            })
            print(pm.to_string(index=False))
            f = ea.fights
        notes = [(r.fighter1, r.fighter2, n) for r in f.itertuples() for n in r.notes]
        for a, b, n in notes:
            print(f"Note ({a} vs {b}): {n}")
        if ea.news:
            _header("News check")
            for name, hs in ea.news.items():
                flagged = [h for h in hs if h.flags]
                if flagged or args.all_news:
                    _print_headlines(name, flagged if not args.all_news else hs, limit=4)
            clean = [n for n, hs in ea.news.items() if not any(h.flags for h in hs)]
            if clean and not args.all_news:
                print(f"No flags for: {', '.join(clean)}")

    if any(pd.isna(ea.date) for ea in analyses):
        print("\nNote: lines on fights without a date are often stale and some of those fights never happen, "
              "so they are left out of the value bets below.")
    vb = upcoming.value_bets(analyses, args.min_ev)
    _header(f"Value bets (expected return >= {args.min_ev:.0%} at the best available price)")
    if vb.empty:
        print("None right now. Lines move - check again closer to fight night.")
    else:
        show = vb.copy()
        for c in ("our %", "market %"):
            show[c] = show[c].map(lambda x: _pct(x, 1))
        show["EV"] = show["EV"].map(lambda x: f"{x:+.1%}")
        show["kelly %"] = show["kelly %"].map(lambda x: _pct(x, 2))
        show["market only"] = np.where(show["market only"], "yes", "")
        if not args.bankroll:
            show = show.drop(columns="stake")
        print(show.to_string(index=False))
        print("'ours' blends the stats model with the market. 'market only' = a fighter without UFC history, so "
              "the value comes purely from one book beating the consensus price.")
    print(f"\n{DISCLAIMER}")


def cmd_footage(args, db: Database):
    fid = db.find(args.name)
    name = db.states[fid].name
    log = db.fight_log(fid)
    if args.vs:
        opp = db.find(args.vs)
        log = log[log["opponent_id"] == opp]
        if log.empty:
            sys.exit(f"{name} has never fought {db.states[opp].name} in the UFC.")
    _header(f"Where to watch {name}")
    print("Full fights are on UFC Fight Pass (subscription); free fights and highlights are on the official "
          "UFC YouTube channel.")
    for label, url in footage.fighter_links(name).items():
        print(f"  {label:20s} {url}")
    for r in log.head(args.fights).itertuples():
        _header(f"{r.date:%Y-%m-%d}  {r.result} vs {r.opponent} ({r.method}, R{_num(r.round, 0)})  {r.event}")
        for label, url in footage.links(name, r.opponent, r.event).items():
            print(f"  {label:15s} {url}")


def cmd_news(args, db: Database | None = None):
    session = requests.Session()
    if args.fighter:
        name = args.fighter
        if db is not None:
            try:
                name = db.states[db.find(args.fighter)].name
            except LookupError_:
                pass
        _print_headlines(name, news.fighter_news(name, days=args.days, session=session, limit=args.limit),
                         limit=args.limit)
        return
    hs = news.general_news(args.limit, session=session)
    for h in hs:
        tag = f" [{', '.join(h.flags)}]" if h.flags else ""
        when = f"{h.published:%b %d %H:%M}" if not pd.isna(h.published) else ""
        print(f"{when:12s} {h.source:8s} {h.title[:110]}{tag}")


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
    shop = wf[wf["best_a"].notna()]
    tables_ = [("stats model alone, typical price", wf, "p_model", "dec"),
               ("model + market blend, typical price", wf, "p_blend", "dec")]
    if len(shop):
        tables_.append((f"model + market blend, best price across books ({shop['date'].min():%Y}-"
                        f"{shop['date'].max():%Y})", shop, "p_blend", "best"))
    for label, frame, col, price in tables_:
        _header(f"Flat 1-unit bets on every positive-EV side: {label}")
        roi = market.roi_table(frame, col, price=price)
        roi["min EV"] = roi["min EV"].map(lambda x: _pct(x))
        roi["win %"] = roi["win %"].map(lambda x: _pct(x, 1))
        roi["underdog bets %"] = roi["underdog bets %"].map(lambda x: _pct(x))
        roi["profit (units)"] = roi["profit (units)"].map(lambda x: f"{x:+.1f}")
        roi["ROI"] = roi["ROI"].map(lambda x: "-" if pd.isna(x) else f"{x:+.1%}")
        print(roi.to_string(index=False))
    print("\n'Typical price' is the 2014-2022 average line (~1% margin, so flattering) and, from 2023, the median "
          "across sportsbooks (~4-5% margin, realistic). 'Best price' assumes you can bet at whichever "
          "book is best - that line shopping is where most of the edge comes from.")


# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ballout", description="UFC fight history + betting analysis toolkit")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("update", help="download latest fight data, rebuild tables and retrain model")
    s.add_argument("--skip-download", action="store_true", help="rebuild from already-downloaded raw files")
    s.add_argument("--no-backtest", action="store_true", help="skip the walk-forward backtest (faster)")
    s.add_argument("--no-live-odds", action="store_true",
                   help="don't fetch recent closing lines from BestFightOdds (first run takes ~8 min)")

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
    s.add_argument("--live", action="store_true", help="use the best current odds if the fight is on an upcoming card")
    s.add_argument("--news", action="store_true", help="show recent headlines for both fighters")
    s.add_argument("--news-days", type=int, default=30)

    s = sub.add_parser("upcoming", help="analyse upcoming UFC cards from live sportsbook odds")
    s.add_argument("--event", help="only events whose name contains this, e.g. \"UFC 334\"")
    s.add_argument("--unscheduled", action="store_true",
                   help="also include announced UFC fights that don't have a date yet")
    s.add_argument("--news", action="store_true", help="check every fighter's recent headlines for red flags")
    s.add_argument("--all-news", action="store_true", help="with --news, list headlines even without flags")
    s.add_argument("--news-days", type=int, default=21)
    s.add_argument("--bankroll", type=float)
    s.add_argument("--kelly", type=float, default=0.25)
    s.add_argument("--min-ev", type=float, default=0.05,
                   help="minimum expected return to list as a value bet (default 0.05)")

    s = sub.add_parser("app", help="desktop app in its own window (needs: pip install pywebview)")

    s = sub.add_parser("web", help="phone-friendly web app (open it on your iPhone over Wi-Fi)")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--host", default="0.0.0.0", help="use 127.0.0.1 to allow this computer only")
    s.add_argument("--open", action="store_true", help="open it in this computer's browser too")

    s = sub.add_parser("footage", help="links to watch a fighter's fights (UFC YouTube, Fight Pass)")
    s.add_argument("name")
    s.add_argument("--vs", help="only fights against this opponent")
    s.add_argument("--fights", type=int, default=10)

    s = sub.add_parser("news", help="latest UFC headlines, or one fighter's recent news with red flags")
    s.add_argument("fighter", nargs="?")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--limit", type=int, default=15)

    s = sub.add_parser("card", help="analyse a whole card from a CSV of matchups and odds")
    s.add_argument("file", help="CSV with fighter_a, fighter_b[, odds_a, odds_b, weight_class]")
    s.add_argument("--date", help="event date (default today)")
    s.add_argument("--bankroll", type=float)
    s.add_argument("--kelly", type=float, default=0.25)
    s.add_argument("--min-ev", type=float, default=0.05,
                   help="minimum expected return to list as a value bet (default 0.05)")
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


_db: Database | None = None


def _database() -> Database:
    """Load once per process (the interactive prompt runs many commands)."""
    global _db
    if _db is None:
        _db = Database()
    return _db


def run(argv=None):
    global _db
    args = build_parser().parse_args(argv)
    try:
        if args.command == "update":
            _db = None
            return cmd_update(args)
        if args.command == "backtest":
            return cmd_backtest(args)
        if args.command == "news" and not args.fighter:
            return cmd_news(args)
        if args.command == "web":
            from . import web
            return web.serve(args.host, args.port, args.open)
        if args.command == "app":
            from . import desktop
            return desktop.run()
        db = _database()
        handler = {"search": cmd_search, "fighter": cmd_fighter, "matchup": cmd_matchup,
                   "card": cmd_card, "leaders": cmd_leaders, "event": cmd_event,
                   "upcoming": cmd_upcoming, "news": cmd_news, "footage": cmd_footage}[args.command]
        handler(args, db)
    except (LookupError_, FileNotFoundError, ValueError) as e:
        sys.exit(str(e))
    except requests.RequestException as e:
        sys.exit(f"Network error: {e}")


INTRO = """
Ball Out Gamba - UFC fight data, live odds and betting analysis
Type a command and press Enter ('help' for the full list, 'quit' to exit). For example:

  update                                   download / refresh all data (first time ~10 min)
  upcoming --news                          live odds + news for upcoming UFC cards
  matchup "Ilia Topuria" "Islam Makhachev" --live
  fighter "Alex Pereira"                   profile, stats, fight log
  footage "Alex Pereira"                   links to watch their fights
  web                                      phone app: open the address it prints on your iPhone
"""


def interactive():
    """Prompt loop for when the program is started without arguments
    (e.g. double-clicking the .exe), so the window stays open."""
    import shlex
    print(INTRO)
    if not config.MODEL_PATH.exists():
        print(f"No data yet in {config.DATA_DIR} - start with: update\n")
    while True:
        try:
            line = input("ballout> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            return
        if line.lower() in ("help", "?"):
            line = "--help"
        if line.split()[0] in ("ballout", "python"):  # tolerate pasted README commands
            line = line.split("ballout", 1)[-1].strip()
        try:
            run(shlex.split(line))
        except SystemExit as e:
            if isinstance(e.code, str):
                print(e.code)
        except KeyboardInterrupt:
            print("\n(stopped)")
        except Exception as e:  # keep the prompt alive whatever happens
            print(f"Error: {type(e).__name__}: {e}")
        print()


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # e.g. Windows consoles that can't show every headline character
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    if argv is None and len(sys.argv) == 1:
        return interactive()
    return run(argv)


if __name__ == "__main__":
    main()
