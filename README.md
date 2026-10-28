# Ball Out Gamba 🥊

A command-line tool that builds a clean database of **every UFC fight in history**
(1994 → last weekend) and uses it to help you bet UFC cards:

- fighter profiles, career stats and fight logs
- side-by-side matchup breakdowns, head-to-head history and common opponents
- a win-probability model plus KO / submission / decision estimates
- a model + betting-market blend, learned from ~3,200 historical lines, that beats the
  market on its own
- edge, expected value and Kelly stake sizing against your sportsbook's odds
- whole-card analysis from a CSV, with value bets ranked
- an honest walk-forward backtest so you know how much to trust it

## Setup

```bash
pip install -r requirements.txt     # numpy, pandas, requests
python -m ballout update            # download data, build tables, train model (~10 s)
```

Re-run `update` after each event to pull the latest results. (Or `pip install -e .`
and use the `ballout` command instead of `python -m ballout`.)

## Data

Fight data comes from [ufcstats.com](http://ufcstats.com) (the UFC's official stats
provider) via the community-maintained mirror at
[Greco1899/scrape_ufc_stats](https://github.com/Greco1899/scrape_ufc_stats), which is
refreshed regularly. Historical betting odds (late 2014–2023) come from
[jansen88/ufc-data](https://github.com/jansen88/ufc-data). `update` cleans and joins
everything into `data/processed/`:

| file | contents |
|---|---|
| `fights.csv` | one row per fight: date, event, fighters, winner, method, round, time, weight class, title bout, referee, judges' scores |
| `fighter_fights.csv` | one row per fighter per fight, with their totals **and** their opponent's (sig. strikes by target/position, takedowns, knockdowns, sub attempts, control time) |
| `rounds.csv` | the same stats round by round |
| `fighters.csv` | height, weight, reach, stance, date of birth, nickname |
| `events.csv` | event dates and locations |
| `odds.csv` | historical decimal odds matched to fight ids |
| `prefight_features.csv` | each fighter's stats *as they stood before* every fight, for your own modelling |

The CSVs open directly in Excel / Google Sheets / pandas if you want to dig yourself.

## Commands

```bash
python -m ballout fighter "Islam Makhachev"                # profile + last 10 fights
python -m ballout search silva                             # find fighters by partial name
python -m ballout matchup "Ilia Topuria" "Islam Makhachev"   # full breakdown + model
python -m ballout matchup "Ilia Topuria" "Makhachev" --odds +105 -125 --bankroll 500
python -m ballout card examples/sample_card.csv --bankroll 500 --out picks.csv
python -m ballout leaders --division lightweight           # top active fighters by Elo
python -m ballout event "UFC 333"                          # results of a past event
python -m ballout backtest                                 # how accurate is the model?
```

Names are forgiving: case, accents and small typos are fine (`makhachv`, `conor mcgregr`).
Where two fighters share a name (e.g. the two Bruno Silvas) you'll be shown both with
their ids; pass the id instead of the name.

### Analysing a card

Make a CSV with one row per fight (odds are optional, American or decimal). See
`examples/sample_card.csv`; its matchups and odds are made up for demonstration.

```csv
fighter_a,fighter_b,odds_a,odds_b,weight_class
Ilia Topuria,Islam Makhachev,+105,-125,Lightweight
Max Holloway,Justin Gaethje,-160,+135,Lightweight
```

`card` prints the pick for every bout, then a **value bets** table: every side where our
estimate beats the bookmaker's no-vig probability by at least `--min-edge` (default 5
points, the level that was profitable in the backtest), with EV per $100 and a stake.
Add `--detail` for the full matchup breakdown of every fight.

### Reading the betting numbers

- **model %**: the stats model on its own.
- **market %**: the bookmaker's probability with their margin (vig) removed.
- **blend %**: model and market combined; this is the number the edge, EV and stake use.
  You need odds for both fighters to get it.
- **fair line**: the odds at which the estimate breaks even.
- **edge %**: blend probability minus market probability.
- **EV/$100**: expected profit per $100 staked at the book's price.
- **kelly %**: share of bankroll to stake, using quarter Kelly (`--kelly`) and capped at 5%.

## How the model works

1. **Chronological replay.** Every fight is processed in date order. Before each fight,
   each fighter's record and stats are snapshotted *as of that moment*, so the model never
   sees the result it's predicting.
2. **Features.** For each fighter: Elo rating, age, reach, height, UFC experience, win
   rate, recent form, streak, layoff, strikes landed/absorbed per minute, striking
   accuracy/defence, takedowns per 15 min, takedown accuracy/defence, submission attempts,
   knockdowns, control time, how often they've been KO'd, finish rate and 5-round experience,
   plus strength of schedule (average Elo of past opponents), recency-weighted striking,
   takedown and knockdown rates, an age curve, and moves up or down in weight.
   Small samples are pulled toward league averages so a 1-0 debutant doesn't look like a
   world-beater.
3. **Win model.** Logistic regression on the difference between the two fighters'
   features. It is trained on both orderings of every fight, so it can't pick up on
   ufcstats listing the winner first.
4. **Market blend.** With odds for both sides, the model's probability is combined with the
   market's no-vig probability on the log-odds scale. The weights (currently market 1.00,
   model 0.22) are learned from historical lines; see below.
5. **Method model.** P(KO / SUB / DEC | win) blends how each fighter usually wins with how
   their opponent usually loses, shrunk toward the weight-class average.

### Track record (walk-forward backtest)

Run `python -m ballout backtest` to reproduce. Each year is predicted by a model trained
only on the fights before it.

**Stats model alone**

| | 2012–2026 (7,011 fights) | 2020–2026 (3,440 fights) |
|---|---|---|
| picks correct | **61.5%** | **62.8%** |
| Elo alone | 56.2% | 57.1% |
| log loss (coin flip = 0.693, lower is better) | 0.653 | 0.645 |

It is well calibrated: fights it calls 60–70% were won by its pick 65% of the time.

**Against the betting market** (2,726 fights with odds, 2016–2023)

| | picks correct | log loss |
|---|---|---|
| betting market (no-vig) | 66.1% | 0.6095 |
| stats model alone | 61.9% | 0.6508 |
| **model + market blend** | **66.4%** | **0.6090** |

**Did betting the edges make money?** (flat 1-unit bets, same fights)

| min edge | stats model alone | model + market blend |
|---|---|---|
| 0% | 2,726 bets, −5.8% ROI | 2,726 bets, +0.3% ROI |
| 3% | 2,266 bets, −5.3% | 635 bets, +0.5% |
| 5% | 1,981 bets, −7.1% | 118 bets, **+18.5%** |

What this means:

- **Never bet the raw stats model against the line.** Its "edges" are mostly underdogs the
  market has correctly priced low, and it lost 5–7% across the board. That's why the
  tool now edges against the blend.
- **The market is the stronger signal, but the model adds real information on top.** The
  blend beats the market alone, and the model's weight (0.22 ± 0.09) is clearly above
  zero. Part of what it learns is that the market slightly underprices big favourites:
  fighters the market rated 70–80% won 79.6% of the time.
- **Blend edges of 5%+ were profitable, but the sample is small.** 118 bets over 8 years
  is about 15 a year, and +18.5% ± 12.5% on 118 bets is only about 1.5 standard errors
  from zero: encouraging, but it could still be luck. Treat it as a filter for where to
  look, not a money printer.
- **The historical odds carry about 1% bookmaker margin.** A typical sportsbook charges
  4–5%, which costs another 2–3 points of ROI. Shop around for the best line.
- **None of this knows about injuries, short-notice replacements or bad weight cuts.**
  Check the news before betting.

## Tests

```bash
python -m unittest
```

---

Gamble responsibly. Never bet more than you can afford to lose. If gambling stops being
fun, call 1-800-GAMBLER (US) or visit a local support service.
