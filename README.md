# Ball Out Gamba 🥊

A command-line tool that builds a clean database of **every UFC fight in history**
(1994 → last weekend) and uses it to help you bet UFC cards:

- fighter profiles, career stats and fight logs
- side-by-side matchup breakdowns, head-to-head history and common opponents
- a win-probability model plus KO / submission / decision estimates
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
refreshed regularly. `update` cleans and joins it into `data/processed/`:

| file | contents |
|---|---|
| `fights.csv` | one row per fight: date, event, fighters, winner, method, round, time, weight class, title bout, referee, judges' scores |
| `fighter_fights.csv` | one row per fighter per fight, with their totals **and** their opponent's (sig. strikes by target/position, takedowns, knockdowns, sub attempts, control time) |
| `rounds.csv` | the same stats round by round |
| `fighters.csv` | height, weight, reach, stance, date of birth, nickname |
| `events.csv` | event dates and locations |
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

`card` prints the model's pick for every bout, then a **value bets** table: every side
where the model's probability beats the bookmaker's no-vig probability by at least
`--min-edge` (default 3 points), with EV per $100 and a stake. Add `--detail` for the
full matchup breakdown of every fight.

### Reading the betting numbers

- **fair line**: the odds at which the model thinks a bet breaks even.
- **no-vig %**: the bookmaker's probability with their margin removed.
- **edge %**: model probability minus no-vig probability.
- **EV/$100**: expected profit per $100 staked at the book's price.
- **kelly %**: share of bankroll to stake, using quarter Kelly (`--kelly`) and capped at 5%.

## How the model works

1. **Chronological replay.** Every fight is processed in date order. Before each fight,
   each fighter's record and stats are snapshotted *as of that moment*, so the model never
   sees the result it's predicting.
2. **Features.** For each fighter: Elo rating, age, reach, height, UFC experience, win
   rate, recent form, streak, layoff, strikes landed/absorbed per minute, striking
   accuracy/defence, takedowns per 15 min, takedown accuracy/defence, submission attempts,
   knockdowns, control time, how often they've been KO'd, finish rate and 5-round experience.
   Small samples are pulled toward league averages so a 1-0 debutant doesn't look like a
   world-beater.
3. **Win model.** Logistic regression on the difference between the two fighters'
   features. It is trained on both orderings of every fight, so it can't pick up on
   ufcstats listing the winner first.
4. **Method model.** P(KO / SUB / DEC | win) blends how each fighter usually wins with how
   their opponent usually loses, shrunk toward the weight-class average.

### Track record (walk-forward backtest)

Each year is predicted by a model trained only on the fights before it:

| | 2012–2026 (7,011 fights) | 2020–2026 |
|---|---|---|
| model picks correct | **60.9%** | **62.0%** |
| Elo alone | 55.6% | 56.3% |
| model log loss (coin flip = 0.693) | 0.658 | 0.650 |

The probabilities are well calibrated: fights the model calls 60–70% were won by the
pick 64–66% of the time.

**Keep this in perspective:** closing betting lines typically pick about two-thirds of
UFC winners, so the market is better than this model on average. The model is most
useful as a second opinion and a fast way to see the numbers behind a matchup. When it
disagrees with the market by 10+ points the tool flags it: that usually means the market
knows something the stats don't (injury, short-notice replacement, weight cut, style
matchup). The model has no odds history, so it hasn't been backtested for profit.

## Tests

```bash
python -m unittest
```

---

Gamble responsibly. Never bet more than you can afford to lose. If gambling stops being
fun, call 1-800-GAMBLER (US) or visit a local support service.
