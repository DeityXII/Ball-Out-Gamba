"""Odds conversion, vig removal, expected value and Kelly sizing."""

from __future__ import annotations

import math


def parse_odds(value) -> float:
    """Return decimal odds from American (-150, +130, '130') or decimal (2.3).

    Anything with magnitude >= 100 is treated as American, anything between
    1 and 100 as decimal.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        raise ValueError("no odds given")
    s = str(value).strip().replace(" ", "")
    if not s:
        raise ValueError("no odds given")
    x = float(s)
    if abs(x) >= 100:
        return 1 + (x / 100.0 if x > 0 else 100.0 / -x)
    if x > 1:
        return x
    raise ValueError(f"can't interpret odds {value!r}")


def decimal_to_american(dec: float) -> str:
    if dec <= 1:
        return "n/a"
    if dec >= 2:
        return f"+{round((dec - 1) * 100)}"
    return f"{round(-100 / (dec - 1))}"


def prob_to_american(p: float) -> str:
    if p <= 0 or p >= 1:
        return "n/a"
    return decimal_to_american(1 / p)


def implied_prob(dec: float) -> float:
    return 1.0 / dec


def no_vig(dec_a: float, dec_b: float) -> tuple[float, float, float]:
    """Fair two-way probabilities and the bookmaker's overround."""
    ia, ib = implied_prob(dec_a), implied_prob(dec_b)
    total = ia + ib
    return ia / total, ib / total, total - 1.0


def expected_value(p: float, dec: float) -> float:
    """Expected profit per 1 unit staked."""
    return p * (dec - 1) - (1 - p)


def kelly_fraction(p: float, dec: float) -> float:
    """Full-Kelly fraction of bankroll (0 when there is no edge)."""
    b = dec - 1
    return max(0.0, (b * p - (1 - p)) / b) if b > 0 else 0.0
