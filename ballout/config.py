"""Paths and data source locations."""

import os
import sys
from pathlib import Path


def _default_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Packaged executable: keep data next to the program so the folder is portable.
        return Path(sys.executable).resolve().parent / "ballout-data"
    return Path.cwd() / "data"


DATA_DIR = Path(os.environ.get("BALLOUT_DATA_DIR", _default_data_dir()))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_PATH = DATA_DIR / "model.json"

# Community-maintained mirror of every completed event on ufcstats.com,
# refreshed regularly: https://github.com/Greco1899/scrape_ufc_stats
SOURCE_BASE = "https://raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main"
SOURCE_FILES = [
    "ufc_event_details.csv",
    "ufc_fight_details.csv",
    "ufc_fight_results.csv",
    "ufc_fight_stats.csv",
    "ufc_fighter_details.csv",
    "ufc_fighter_tott.csv",
]

# Historical decimal odds (late 2014 - 2023) for the market comparison and
# the model/market blend: https://github.com/jansen88/ufc-data
ODDS_URL = "https://raw.githubusercontent.com/jansen88/ufc-data/master/data/complete_ufc_data.csv"
ODDS_FILE = "historical_odds.csv"
