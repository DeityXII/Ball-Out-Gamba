"""Paths and data source locations."""

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("BALLOUT_DATA_DIR", Path.cwd() / "data"))
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
