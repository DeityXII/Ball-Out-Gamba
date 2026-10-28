"""User preferences, saved as settings.json in the data folder so the desktop
app, the phone app and the command line all share them."""

from __future__ import annotations

import json

from . import config

FILE = "settings.json"

# Books BestFightOdds lists today; anything new it starts showing is picked up too.
SPORTSBOOKS = ["FanDuel", "DraftKings", "BetMGM", "Caesars", "BetRivers", "BetWay", "Unibet"]
PREDICTION_MARKETS = ["Polymarket", "Kalshi"]
DEFAULT_BOOKS = SPORTSBOOKS  # prediction markets are thin and off unless chosen


def load() -> dict:
    path = config.DATA_DIR / FILE
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save(values: dict) -> dict:
    current = load()
    current.update(values)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / FILE).write_text(json.dumps(current, indent=2))
    return current


def books() -> list[str]:
    """The sportsbooks to take prices from (best price, EV, value bets)."""
    chosen = load().get("books")
    return list(chosen) if chosen else list(DEFAULT_BOOKS)


def set_books(names: list[str] | None) -> list[str]:
    """Save a selection (matched case-insensitively to known names); None resets."""
    if not names:
        save({"books": None})
        return books()
    known = {b.lower(): b for b in SPORTSBOOKS + PREDICTION_MARKETS}
    cleaned = []
    for n in names:
        n = n.strip()
        if n and known.get(n.lower(), n) not in cleaned:
            cleaned.append(known.get(n.lower(), n))
    save({"books": cleaned or None})
    return books()
