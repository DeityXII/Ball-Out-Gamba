"""The app's web server, used two ways:

* `ballout web`: the phone app. Open the printed address in Safari on your
  iPhone (same Wi-Fi) and use Share -> Add to Home Screen.
* the desktop app (desktop.py), which shows the same pages in a native window.

Uses only the standard library. Anyone on the same network who knows the
address can open it (they can view everything and start a data refresh, but
can't change or delete anything); use `--host 127.0.0.1` to keep it to this
computer.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import socket
import struct
import sys
import threading
import time
import urllib.parse
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pandas as pd

from . import config, footage, news, odds, upcoming
from .analysis import Database, LookupError_
from .webpage import INDEX_HTML

MAX_STAKE = 0.05


def clean(obj):
    """Make pandas/numpy values JSON-safe (NaN -> null, dates -> ISO strings)."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return clean(obj.to_dict("records"))
    if obj is pd.NaT:  # before the date checks: NaT is a datetime subclass
        return None
    if isinstance(obj, (pd.Timestamp, np.datetime64)):
        return None if pd.isna(obj) else pd.Timestamp(obj).isoformat()
    if isinstance(obj, dt.date):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if math.isnan(obj) or math.isinf(obj) else float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def _height(inches):
    return None if pd.isna(inches) else f"{int(inches) // 12}'{int(inches) % 12}\""


class NoData(Exception):
    """No downloaded data yet: the page shows its first-run setup screen."""


class _LineWriter:
    """File-like object collecting printed output as progress lines."""

    def __init__(self, lines: list):
        self.lines, self._buf = lines, ""

    def write(self, text: str) -> int:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self.lines.append(line.rstrip())
        return len(text)

    def flush(self):
        pass


def _headline(h: news.Headline) -> dict:
    return {"title": h.title, "source": h.source, "published": h.published, "url": h.url, "flags": h.flags}


class App:
    def __init__(self, db: Database | None = None, desktop: bool = False, phone_port: int = 8765):
        self._db = db
        self.desktop = desktop
        self.phone_port = phone_port
        self.phone_server: ThreadingHTTPServer | None = None
        self.phone_url: str | None = None
        self.job = {"state": "idle", "lines": [], "started": None, "finished": None, "error": None}
        self._cache: dict = {}
        self._lock = threading.Lock()
        self._key_locks: dict = {}
        self._db_lock = threading.Lock()

    @property
    def db(self) -> Database:
        """Loaded on first use, so the app can start before any data exists."""
        if self._db is None:
            with self._db_lock:
                if self._db is None:
                    if not config.MODEL_PATH.exists():
                        raise NoData("No fight data yet. Download it to get started.")
                    self._db = Database()
        return self._db

    def _cached(self, key, ttl: float, fn):
        """Memoise fn() for ttl seconds. Each key has its own lock, so a slow live
        fetch never holds up unrelated requests, and the same fetch never runs twice."""
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:
            hit = self._cache.get(key)
            if hit and time.time() - hit[0] < ttl:
                return hit[1]
            value = fn()
            self._cache[key] = (time.time(), value)
            return value

    # ---- setup, data refresh and phone access ---------------------------
    def status(self) -> dict:
        has_data = config.MODEL_PATH.exists()
        out = {"desktop": self.desktop, "has_data": has_data, "data_dir": str(config.DATA_DIR),
               "updated_at": pd.Timestamp.fromtimestamp(config.MODEL_PATH.stat().st_mtime) if has_data else None,
               "job": {k: v for k, v in self.job.items() if k != "lines"},
               "phone": {"enabled": self.phone_server is not None or not self.desktop, "url": self.phone_url}}
        if has_data and self.job["state"] != "running":
            try:
                f = self.db.fights
                out.update({"fights": len(f), "fighters": len(self.db.states),
                            "first_event": f["date"].min(), "latest_event": f["date"].max()})
            except Exception:  # half-written data: report what we can
                pass
        return out

    def update(self, quick: str = "") -> dict:
        """Start a full data refresh in the background (download, rebuild, retrain)."""
        with self._lock:
            if self.job["state"] != "running":
                self.job = {"state": "running", "lines": [], "started": pd.Timestamp.now(),
                            "finished": None, "error": None}
                threading.Thread(target=self._run_update, args=(quick == "1",), daemon=True).start()
        return self.update_status()

    def _run_update(self, quick: bool):
        import argparse
        import contextlib

        from . import cli
        writer = _LineWriter(self.job["lines"])
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                cli.cmd_update(argparse.Namespace(skip_download=False, no_backtest=quick, no_live_odds=False))
            with self._db_lock:
                self._db = None
            self._cache.clear()
            self.job.update(state="done", finished=pd.Timestamp.now())
        except Exception as e:  # network down, disk full...
            self.job["lines"].append(f"Error: {type(e).__name__}: {e}")
            self.job.update(state="error", error=f"{type(e).__name__}: {e}", finished=pd.Timestamp.now())

    def update_status(self, since: str = "0") -> dict:
        lines = self.job["lines"]
        return {**{k: v for k, v in self.job.items() if k != "lines"},
                "lines": lines[int(since):], "next": len(lines)}

    def phone(self, enable: str = "1") -> dict:
        """Desktop only: start/stop a second server on the local network for the phone."""
        if not self.desktop:
            return {"enabled": True, "url": self.phone_url}
        if enable == "1" and self.phone_server is None:
            for port in range(self.phone_port, self.phone_port + 10):
                try:
                    self.phone_server = make_server(self, "0.0.0.0", port)
                    break
                except OSError:
                    continue
            if self.phone_server is None:
                raise ValueError("Couldn't open a network port for phone access.")
            threading.Thread(target=self.phone_server.serve_forever, daemon=True).start()
            self.phone_url = f"http://{lan_ip()}:{self.phone_server.server_address[1]}"
        elif enable != "1" and self.phone_server is not None:
            self.phone_server.shutdown()
            self.phone_server.server_close()
            self.phone_server, self.phone_url = None, None
        return {"enabled": self.phone_server is not None, "url": self.phone_url}

    # ---- endpoints -----------------------------------------------------
    def search(self, q: str = "") -> list:
        if len(q.strip()) < 2:
            return []
        db = self.db
        return [{"id": f, "name": db.label(f), "record": db.states[f].record,
                 "last": db.states[f].last_date} for f in db.search(q, limit=12)]

    def _side(self, fid: str, date: pd.Timestamp) -> dict:
        db, st = self.db, self.db.states[fid]
        info = db.info(fid)
        dob = info.get("dob")
        return {
            "id": fid, "name": db.label(fid), "nickname": info.get("nickname"),
            "record": st.record, "elo": round(st.elo), "peak_elo": round(st.peak_elo), "streak": st.streak,
            "title_fights": st.title_fights,
            "age": None if pd.isna(dob) else (date - dob).days / 365.25,
            "height": _height(info.get("height_in")), "reach": info.get("reach_in"),
            "stance": info.get("stance"), "last_fight": st.last_date,
            "days_since": (date - st.last_date).days if st.last_date is not None else None,
            "wins": {"KO": st.ko_wins, "SUB": st.sub_wins, "DEC": st.dec_wins},
            "losses": {"KO": st.ko_losses, "SUB": st.sub_losses, "DEC": st.dec_losses},
            "distance_rate": db.distance_rate(fid), "stats": db.career_stats(fid),
        }

    def fighter(self, id: str = "", name: str = "", fights: str = "15") -> dict:
        db = self.db
        fid = id if id in db.states else db.find(name or id)
        out = self._side(fid, pd.Timestamp.today().normalize())
        st_name = db.states[fid].name
        log = db.fight_log(fid).head(int(fights))
        out["log"] = [{
            "date": r.date, "opponent": r.opponent, "opponent_id": r.opponent_id, "result": r.result,
            "method": r.method, "round": r.round, "time": r.time, "event": r.event,
            "sig": None if pd.isna(r.sig_landed) else f"{int(r.sig_landed)}-{int(r.opp_sig_landed)}",
            "td": None if pd.isna(r.td_landed) else f"{int(r.td_landed)}/{int(r.td_att)}",
            "watch": footage.links(st_name, r.opponent, r.event),
        } for r in log.itertuples()]
        out["watch"] = footage.fighter_links(st_name)
        return out

    def matchup(self, a: str = "", b: str = "", odds_a: str = "", odds_b: str = "", live: str = "",
                weight_class: str = "", bankroll: str = "", kelly: str = "0.25") -> dict:
        db = self.db
        a_id, b_id = db.find(a), db.find(b)
        live_info = None
        date = None
        if live == "1" and not (odds_a and odds_b):
            found = self._cached(("live", a_id, b_id), 300, lambda: upcoming.live_odds_for(db, a_id, b_id))
            if found:
                ev_name, ev_date, oa, ob, books, n = found
                odds_a, odds_b, date = oa, ob, ev_date
                live_info = {"event": ev_name, "date": ev_date, "books": n,
                             "book_a": books[0], "book_b": books[1]}
        pred = db.predict(a_id, b_id, date, weight_class or None)
        out = {
            "a": self._side(a_id, pred.date), "b": self._side(b_id, pred.date),
            "p_a": pred.p_a, "methods": pred.methods, "notes": pred.notes, "live": live_info,
            "drivers": [{"factor": f, "favours": w} for f, w in db.drivers(pred)],
            "h2h": [{"date": r.date, "result": r.result, "method": r.method, "round": r.round,
                     "event": r.event, "watch": footage.links(pred.a.name, pred.b.name, r.event)}
                    for r in db.head_to_head(a_id, b_id).itertuples()],
            "common": db.common_opponents(a_id, b_id).head(10),
            "watch": {"a": footage.fighter_links(pred.a.name), "b": footage.fighter_links(pred.b.name)},
        }
        if odds_a or odds_b:
            priced = db.price(pred, odds_a or None, odds_b or None,
                              float(bankroll) if bankroll else None, float(kelly), MAX_STAKE)
            out["priced"] = priced
            out["priced_used"] = priced.attrs.get("used")
            out["vig"] = priced.attrs.get("vig")
        return out

    def upcoming(self, news: str = "", unscheduled: str = "", min_ev: str = "0.05") -> dict:
        with_news, with_unsched = news == "1", unscheduled == "1"

        def run():
            analyses = upcoming.analyse(self.db, None, with_unsched, with_news, verbose=False)
            return {
                "fetched_at": pd.Timestamp.now(),
                "events": [{
                    "name": ea.name, "date": ea.date, "url": ea.url, "fights": ea.fights,
                    "news": {k: [_headline(h) for h in v] for k, v in ea.news.items()},
                } for ea in analyses],
                "value_bets": upcoming.value_bets(analyses, 0.0),
            }
        data = self._cached(("upcoming", with_news, with_unsched), 600 if with_news else 300, run)
        data = dict(data)
        vb = data["value_bets"]
        data["value_bets"] = vb[vb["EV"] >= float(min_ev)] if len(vb) else vb
        return data

    def news(self, fighter: str = "") -> dict:
        if fighter:
            name = fighter
            try:
                name = self.db.states[self.db.find(fighter)].name
            except LookupError_:
                pass
            hs = self._cached(("news", name), 1800, lambda: news.fighter_news(name, days=30, limit=15))
            return {"fighter": name, "headlines": [_headline(h) for h in hs]}
        hs = self._cached(("news",), 900, lambda: news.general_news(30))
        return {"headlines": [_headline(h) for h in hs]}

    def leaders(self, division: str = "", limit: str = "25") -> list:
        return self.db.leaders(division or None, limit=int(limit))


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------

def _png(size: int = 180) -> bytes:
    """App icon: a red tile with a white ring, encoded as PNG with zlib only."""
    c = (size - 1) / 2
    yy, xx = np.mgrid[0:size, 0:size]
    r = np.hypot(xx - c, yy - c) / size
    img = np.zeros((size, size, 3), np.uint8)
    img[:] = (178, 24, 44)
    img[(r > 0.25) & (r < 0.34)] = (255, 255, 255)
    img[r < 0.13] = (255, 255, 255)
    raw = b"".join(b"\x00" + row.tobytes() for row in img)

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


MANIFEST = {
    "name": "Ball Out Gamba", "short_name": "BallOut", "start_url": "/", "display": "standalone",
    "background_color": "#111214", "theme_color": "#b2182c",
    "icons": [{"src": "/icon.png", "sizes": "180x180", "type": "image/png"}],
}


def make_handler(app: App):
    icon = _png()
    routes = {"search": app.search, "fighter": app.fighter, "matchup": app.matchup,
              "upcoming": app.upcoming, "news": app.news, "leaders": app.leaders,
              "status": app.status, "update": app.update, "update_status": app.update_status,
              "phone": app.phone}

    class Handler(BaseHTTPRequestHandler):
        server_version = "ballout"

        def _send(self, status: int, body: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            if url.path in ("/", "/index.html"):
                return self._send(200, INDEX_HTML.encode(), "text/html; charset=utf-8")
            if url.path == "/icon.png":
                return self._send(200, icon, "image/png")
            if url.path == "/manifest.webmanifest":
                return self._send(200, json.dumps(MANIFEST).encode(), "application/manifest+json")
            if url.path.startswith("/api/"):
                fn = routes.get(url.path[5:])
                if fn is None:
                    return self._send(404, b'{"error": "unknown endpoint"}', "application/json")
                params = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query).items()}
                try:
                    payload, status = clean(fn(**params)), 200
                except NoData as e:
                    payload, status = {"error": str(e), "no_data": True}, 409
                except (LookupError_, ValueError, TypeError) as e:
                    payload, status = {"error": str(e)}, 400
                except Exception as e:  # network errors etc. - keep the server up
                    payload, status = {"error": f"{type(e).__name__}: {e}"}, 500
                return self._send(status, json.dumps(payload).encode(), "application/json")
            self._send(404, b"not found", "text/plain")

        def log_message(self, fmt, *args):
            if args and str(args[1]).startswith("5") and sys.stderr is not None:
                super().log_message(fmt, *args)

    return Handler


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; just picks the outbound interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def make_server(app: App, host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.daemon_threads = True
    return server


def serve(host: str = "0.0.0.0", port: int = 8765, open_browser: bool = False) -> None:
    app = App()
    if config.MODEL_PATH.exists():
        print("Loading fight database...")
        app.db  # load now so the first page is fast
    else:
        print("No data yet - the page will offer to download it.")
    server = make_server(app, host, port)
    lan = f"http://{lan_ip()}:{port}" if host in ("0.0.0.0", "") else None
    app.phone_url = lan
    print(f"\nBall Out Gamba is running.\n  On this computer:  http://localhost:{port}")
    if lan:
        print(f"  On your iPhone:    {lan}   (same Wi-Fi; then Share -> Add to Home Screen)")
    print("Press Ctrl+C to stop.\n")
    if open_browser:
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        server.server_close()
