# Ball Out Gamba 🥊

A command-line tool that builds a clean database of **every UFC fight in history**
(1994 → last weekend) and uses it to help you bet UFC cards:

- fighter profiles, career stats and fight logs
- side-by-side matchup breakdowns, head-to-head history and common opponents
- a win-probability model plus KO / submission / decision estimates
- **live odds for upcoming UFC cards** from every major US sportsbook, with the best
  price on each fighter, line movement, and the market's method-of-victory props
- **news checks** that flag injuries, withdrawals, short-notice replacements, weight
  misses and suspensions for every fighter on a card
- a model + betting-market blend, learned from ~4,900 historical closing lines
  (2014 → last weekend), that beats the market on its own
- edge, expected value and Kelly stake sizing at the best available price
- whole-card analysis from a CSV of your own odds, with value bets ranked
- an honest walk-forward backtest so you know how much to trust it

## Setup

```bash
pip install -r requirements.txt     # numpy, pandas, requests, beautifulsoup4, lxml
python -m ballout update            # download data, odds history, train model
```

The first `update` takes about 8 minutes because it downloads closing lines for every UFC
event since 2023, one page per second. Later runs only fetch new events and take about
15 seconds (`--no-live-odds` skips this step). Re-run `update` after each event to pull
the latest results. (Or `pip install -e .`
and use the `ballout` command instead of `python -m ballout`.)

## Data

Fight data comes from [ufcstats.com](http://ufcstats.com) (the UFC's official stats
provider) via the community-maintained mirror at
[Greco1899/scrape_ufc_stats](https://github.com/Greco1899/scrape_ufc_stats), which is
refreshed regularly. Betting odds come from two places:

- **2014–2023:** [jansen88/ufc-data](https://github.com/jansen88/ufc-data).
- **2023–today and upcoming fights:** [BestFightOdds](https://www.bestfightodds.com), which
  collects lines from FanDuel, DraftKings, BetMGM, Caesars, BetRivers, BetWay, Unibet and
  the prediction markets (its robots.txt allows crawling; the tool waits one second
  between requests and caches completed events).

News comes from Google News search (per fighter), ESPN and Sherdog. `update` cleans and
joins everything into `data/processed/`:

| file | contents |
|---|---|
| `fights.csv` | one row per fight: date, event, fighters, winner, method, round, time, weight class, title bout, referee, judges' scores |
| `fighter_fights.csv` | one row per fighter per fight, with their totals **and** their opponent's (sig. strikes by target/position, takedowns, knockdowns, sub attempts, control time) |
| `rounds.csv` | the same stats round by round |
| `fighters.csv` | height, weight, reach, stance, date of birth, nickname |
| `events.csv` | event dates and locations |
| `odds.csv` | closing odds matched to fight ids: typical (median) price per fighter, and best price for 2023+ |
| `bfo_closing.csv` | BestFightOdds closing lines per fight, with book count and best price and book |
| `prefight_features.csv` | each fighter's stats *as they stood before* every fight, for your own modelling |

The CSVs open directly in Excel / Google Sheets / pandas if you want to dig yourself.

## Commands

```bash
python -m ballout upcoming                                 # every upcoming UFC card, live odds
python -m ballout upcoming --event "UFC 334" --news --bankroll 500
python -m ballout news "Amanda Nunes"                      # recent headlines + red flags
python -m ballout news                                     # latest UFC headlines
python -m ballout fighter "Islam Makhachev"                # profile + last 10 fights
python -m ballout footage "Islam Makhachev"                # links to watch each of their fights
python -m ballout search silva                             # find fighters by partial name
python -m ballout matchup "Ilia Topuria" "Islam Makhachev"   # full breakdown + model
python -m ballout matchup "Ilia Topuria" "Makhachev" --odds +105 -125 --bankroll 500
python -m ballout matchup "Ciryl Gane" "Josh Hokit" --live --news   # uses today's best prices
python -m ballout card examples/sample_card.csv --bankroll 500 --out picks.csv
python -m ballout leaders --division lightweight           # top active fighters by Elo
python -m ballout event "UFC 333"                          # results of a past event
python -m ballout backtest                                 # how accurate is the model?
```

Names are forgiving: case, accents and small typos are fine (`makhachv`, `conor mcgregr`).
Where two fighters share a name (e.g. the two Bruno Silvas) you'll be shown both with
their ids; pass the id instead of the name.

### Fight footage

The UFC owns its fight footage, so the tool doesn't download or host video. `footage`
(and the "Where to watch" section of `matchup`) links each fight to the official UFC
YouTube channel (free fights and highlights), UFC Fight Pass (the full library, by
subscription) and a general YouTube search.

### Upcoming cards (live odds)

`upcoming` pulls every scheduled UFC event from BestFightOdds and, for each fight, shows:

- the **market** probability: the median no-vig line across sportsbooks;
- the stats **model** and **ours** (the model and market blended);
- the **best price** on each fighter and which book has it, plus the expected value there;
- **moved**: how much the line has shifted since you first ran `upcoming` on that fight.
  Snapshots are kept in `data/odds_snapshots.csv`, so run it every day or two before a
  card to watch the money move;
- **how the market expects it to end**: decision, KO and submission chances for each
  fighter, taken from the sportsbooks' prop bets;
- a **value bets** list: sides with at least `--min-ev` expected return (default 5%) at the
  best available price. A price far above every other book's is flagged as possibly stale.

Add `--news` to scan every fighter's last three weeks of headlines for injury, withdrawal,
weight and suspension red flags. Add `--unscheduled` to include announced fights that don't
have a date yet. Their lines are often stale, so those fights never count as value bets.

Debutants with no UFC history are shown at the market price only.

### Analysing your own card

Make a CSV with one row per fight (odds are optional, American or decimal). See
`examples/sample_card.csv`; its matchups and odds are made up for demonstration.

```csv
fighter_a,fighter_b,odds_a,odds_b,weight_class
Ilia Topuria,Islam Makhachev,+105,-125,Lightweight
Max Holloway,Justin Gaethje,-160,+135,Lightweight
```

`card` prints the pick for every bout, then a **value bets** table: every side whose
expected return at your price is at least `--min-ev` (default 5%), with a stake. Add
`--detail` for the full matchup breakdown of every fight.

### Reading the betting numbers

- **model %**: the stats model on its own.
- **market %**: the bookmaker's probability with their margin (vig) removed.
- **blend % / ours**: model and market combined; this is the number the edge, EV and stake
  use. You need odds for both fighters to get it.
- **fair line**: the odds at which the estimate breaks even.
- **edge %**: blend probability minus market probability.
- **EV**: expected profit per $1 (or per $100) staked at that price.
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
   market's no-vig probability on the log-odds scale. The weights (currently market 1.03,
   model 0.21) are learned from historical closing lines; see below.
5. **Method model.** P(KO / SUB / DEC | win) blends how each fighter usually wins with how
   their opponent usually loses, shrunk toward the weight-class average. Against
   2023–26 prop prices it was *worse* than the market at calling decisions (log loss 0.707
   vs 0.641), so `upcoming` shows the market's props and never calls a prop a value bet.

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

**Against the betting market** (4,376 fights with closing odds, 2016–2026)

| | picks correct | log loss |
|---|---|---|
| betting market (no-vig) | 67.6% | 0.6012 |
| stats model alone | 62.6% | 0.6460 |
| **model + market blend** | **67.6%** | **0.6001** |

On 2023–26 alone, newer data the blend was never tuned on, the market scores 0.5882 and
the blend 0.5859.

**Did betting it make money?** Flat 1-unit bets on every side with at least the given
expected return:

| min expected return | stats model, typical price | blend, typical price | blend, **best price** (2023–26) |
|---|---|---|---|
| 0% | 4,074 bets, −7.6% | 2,577 bets, +0.5% | 1,365 bets, **+3.9%** |
| 3% | 3,748 bets, −7.5% | 1,209 bets, +0.2% | 556 bets, **+4.5%** |
| 5% | 3,538 bets, −7.7% | 751 bets, −1.7% | 318 bets, **+11.3%** |

What this means:

- **Never bet the raw stats model against the line.** Its "edges" are mostly underdogs the
  market has correctly priced low, and it lost about 8% across the board.
- **The market is the stronger signal, but the model adds real information on top.** The
  model's blend weight is 0.21 ± 0.07 (3 standard errors from zero). Part of what it learns
  is that the market underprices big favourites: fighters the market rated 70–80% won
  78.4% of the time, and 80–90% favourites won 86.9%.
- **At a typical sportsbook price, the blend roughly breaks even.** The bookmaker's margin
  eats the small edge.
- **Line shopping is where the money is.** Taking the best price across books turned the
  same picks positive: +3.9% on 1,365 bets (±2.8%), and +11.3% on the 318 with 5%+
  expected return (±7.7%). This assumes you hold accounts at several books. Closing "best
  prices" can include brief quotes you couldn't actually get, so treat these as upper
  bounds: promising, not proven.
- **Check the news.** The stats know nothing about injuries, short-notice replacements or
  bad weight cuts. `--news` exists because those are exactly what moves lines.

## Tests

```bash
python -m unittest
```

---

Gamble responsibly. Never bet more than you can afford to lose. If gambling stops being
fun, call 1-800-GAMBLER (US) or visit a local support service.
