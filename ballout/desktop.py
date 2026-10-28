"""Desktop app: the same interface as the phone app, in its own window.

The pages are served privately on this computer (127.0.0.1) and shown with
pywebview, which uses the Edge WebView2 engine built into Windows 10/11
(WebKit on macOS). Phone access can be switched on from Settings.
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from . import config, web

TITLE = "Ball Out Gamba"


def _redirect_missing_streams() -> None:
    """A windowed .exe has no console (sys.stdout is None), so send output to a
    log file in the data folder instead of crashing on the first print."""
    if sys.stdout is None or sys.stderr is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        log = open(config.DATA_DIR / "app.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


def run(selftest: Path | None = None) -> int:
    _redirect_missing_streams()
    import webview  # optional dependency: pip install pywebview

    app = web.App(desktop=True)
    server = web.make_server(app, "127.0.0.1", 0)  # any free port, this computer only
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"

    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True  # watch links etc. open in your browser
    window = webview.create_window(TITLE, url, width=1240, height=860, min_size=(420, 600))
    result = {"ok": False, "detail": "window never loaded"}

    def check():
        """--selftest: wait for the page, confirm the app rendered, then close."""
        if window.events.loaded.wait(90):
            title = window.evaluate_js("document.title")
            nav = window.evaluate_js("document.querySelectorAll('nav button').length")
            result.update(ok=title == TITLE and bool(nav), detail=f"title={title!r} nav_buttons={nav}")
        selftest.write_text(("OK " if result["ok"] else "FAIL ") + result["detail"])
        window.destroy()

    storage = config.DATA_DIR / "webview"
    storage.mkdir(parents=True, exist_ok=True)
    webview.start(check if selftest else None, private_mode=False, storage_path=str(storage))
    server.shutdown()
    if app.phone_server is not None:
        app.phone_server.shutdown()
    return 0 if (result["ok"] or not selftest) else 1


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="BallOutGamba", description="Ball Out Gamba desktop app")
    p.add_argument("--selftest", type=Path, help="open, check the page loaded, write the result here and exit")
    args = p.parse_args(argv)
    sys.exit(run(args.selftest))


if __name__ == "__main__":
    main()
