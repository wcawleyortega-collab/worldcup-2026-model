# 2026 World Cup Prediction Model

A research-guided forecasting model for the 2026 FIFA World Cup (USA/Mexico/Canada, June 11 – July 19, 2026), built on the architecture that the academic and industry literature converges on: an **Elo rating core → Poisson goal model → Dixon-Coles draw correction → Monte Carlo tournament simulation**. See `RESEARCH.md` for the full survey of world-class systems this design follows (FiveThirtyEight SPI, eloratings.net, Dixon-Coles 1997, the Zeileis/Groll bookmaker-consensus + hybrid random forest line of work, Opta, Gracenote).

## Headline forecast (50,000 simulations, 50% bookmaker-consensus blend)

| Team | Champion (blend) | Champion (pure model) | Market-implied | Final | Semifinal |
|---|---|---|---|---|---|
| Spain | **21.4%** | 26.9% | 15.2% | 32.3% | 46.3% |
| Argentina | **13.1%** | 19.1% | 8.1% | 22.6% | 35.9% |
| France | **12.2%** | 9.4% | 14.2% | 20.5% | 34.3% |
| England | **8.6%** | 6.1% | 10.4% | 16.2% | 27.4% |
| Brazil | **6.5%** | 4.5% | 8.1% | 12.4% | 22.9% |
| Portugal | **6.2%** | 3.1% | 9.3% | 12.2% | 22.3% |
| Germany | **3.6%** | 1.9% | 5.6% | 7.7% | 16.4% |
| Mexico | **3.3%** | 6.3% | 1.3% | 7.6% | 15.9% |

The headline numbers blend the pure rating model 50/50 with the bookmaker consensus (median of complete 48-team outright lists from BetMGM via Yahoo, June 10, and DraftKings via ESPN, June 11, 2026; overround stripped), following Leitner-Zeileis-Hornik: market-implied championship probabilities are inverted into per-team Elo adjustments via fixed-point tournament simulation, then half of each adjustment is applied. This lands the forecast between the sharp Elo view (Spain 27%, Argentina 19%) and the market (Spain 15%, Argentina 8%), and close to the published model consensus (Opta 16.1%, Zeileis hybrid RF 14.5% for Spain). The model and the market disagree most about Argentina, Mexico, Colombia and Ecuador (model higher) versus Portugal, Germany and Netherlands (market higher).

## How it works

1. **Elo ratings** (`wc_model/elo.py`) — eloratings.net formulation run over all 49,000+ internationals since 1872: K = 60/50/40/30/20 by match importance, goal-margin multiplier G = 1 / 1.5 / (11+N)/8, +100 home advantage.
2. **Goal model** (`wc_model/goals.py`) — Poisson GLM mapping Elo win expectancy → expected goals (cubic polynomial in W_e + home dummy), maximum-likelihood fitted on internationals since 1990; Dixon-Coles τ correction with ρ = −0.057 (ML-fitted) inflating low-score draws.
3. **Bookmaker consensus layer** (`wc_model/market.py`) — outright odds for all 48 teams (`data/market_odds.csv`) are converted to probabilities with proportional overround removal, then inverted into Elo-scale adjustments by iterating: simulate the tournament, compare model vs market championship probabilities, nudge each team's rating by `lr * log(p_market / p_model)`, repeat until the gap is within Monte Carlo noise. Blended ratings = Elo + 0.5 × adjustment (`MARKET_WEIGHT` in `run_predictions.py`).
4. **Tournament engine** (`wc_model/tournament.py`) — exact 2026 format: the verified 12 groups from the Dec 2025 draw (+ March 2026 playoff winners), the official 72-fixture schedule from the data, FIFA tiebreakers (points → GD → GF, random jitter proxying fair-play/lots), best-8 third-place ranking, allocation of thirds to the official bracket slots (matches 73–88) by constraint-satisfaction matching, knockout rounds per the official matches 89–104. Knockout draws: extra time at ⅓ scoring rate, then a shootout with a tiny Elo tilt. Hosts get home advantage in their (non-neutral) fixtures; non-host CONCACAF sides get a +33 Elo regional bonus (1/3 of home advantage, following 538's 2018 treatment of UEFA teams in Russia).

## Validation

Frozen pre-tournament backtests (model fitted only on data before each tournament):

| Tournament | RPS (model) | RPS (uniform) | Log-loss (model) | Log-loss (uniform) |
|---|---|---|---|---|
| WC 2018 (64 matches) | **0.209** | 0.244 | **0.983** | 1.099 |
| WC 2022 (64 matches) | **0.222** | 0.239 | **1.064** | 1.099 |

These are in the range achieved by the published academic models on the same tournaments.

## Usage

```bash
uv venv && uv pip install pandas numpy scipy matplotlib
.venv/bin/python run_predictions.py 50000   # arg = number of simulations
```

Outputs land in `outputs/`:
- `team_probabilities.csv` — headline (blended) forecast: all 48 teams × P(reach each round), P(win group)
- `team_probabilities_pure.csv` — same, pure rating model (no market input)
- `market_comparison.csv` — pure vs market vs blend champion probabilities + Elo adjustments
- `match_predictions.csv` — all 72 group fixtures: expected goals + W/D/L probabilities (pure model)
- `champion_probabilities.png` — top-15 chart, blended vs pure
- `run_log.txt` — full run log incl. backtests and Elo top-15

If `data/market_odds.csv` is absent, the run falls back to the pure rating model.

Data: [martj42/international_results](https://github.com/martj42/international_results) (`data/results.csv`), which includes the official 2026 fixture list.

## Live updates during the tournament

`update_predictions.py` re-forecasts the tournament conditioned on real results, and a macOS LaunchAgent (`~/Library/LaunchAgents/com.worldcup.predictions.plist`) runs it **every morning at 6:30** through July 20:

1. Pulls the latest `results.csv` + `shootouts.csv` from the martj42 repo (updated with World Cup scores as they're played).
2. Recomputes Elo through all completed matches — tournament results move ratings with K=60.
3. Holds played group games fixed in every simulation; fixes winners of completed knockout games (shootout winners resolved from `shootouts.csv`); once FIFA's real round-of-32 pairings appear in the data, the actual third-place slotting overrides the model's constraint matching.
4. Keeps applying the pre-tournament bookmaker deltas (`outputs/market_deltas.csv`) at weight 0.5 — in-tournament odds react to results we already condition on, so the prior is not re-fit.
5. Overwrites `outputs/team_probabilities.csv` and appends the day's probabilities to `outputs/history.csv` (one row per team per day — the data for a 538-style probability tracker).

Manual run: `.venv/bin/python update_predictions.py`. Check the schedule: `launchctl list | grep worldcup`. Remove after the final: `launchctl bootout gui/$(id -u)/com.worldcup.predictions && rm ~/Library/LaunchAgents/com.worldcup.predictions.plist`. The script exits on its own after July 20.

## Research study (live data collection)

The twice-daily automation (06:30 and 23:30) also snapshots **Polymarket prices** for all 144 World Cup contracts (48 advancement, 48 group-winner, 48 outright) via the Gamma API into `data/polymarket_history.csv`, and logs every model forecast before it can resolve (`outputs/history.csv`, `outputs/match_forecast_history.csv`). Together these form a live-collected panel for a prediction-market efficiency study — calibration, model-vs-market accuracy (Diebold-Mariano), speed of news incorporation, favorite-longshot bias, and exact-vs-traded qualification probabilities on final matchdays. Design, hypotheses, and methods: **`RESEARCH_DESIGN.md`**. Score everything resolved so far with:

```bash
.venv/bin/python evaluate_forecasts.py
```

## Limitations / extensions

- **Market data quality.** The odds snapshot is a two-book median (BetMGM + DraftKings, June 10–11), not the 24-bookmaker scrape Zeileis uses; the books disagree most on mid-tier longshots (e.g. Jordan 1000-1 vs 2500-1). Match-level predictions in `match_predictions.csv` use the pure model; only the tournament forecast is blended.
- **No squad covariates** (Transfermarkt value, age, club minutes) and no xG — international xG history is hard to source for all 48 teams.
- **Host treatment in knockouts** is approximate: hosts are assumed to keep home advantage whenever they survive (mostly true given the bracket's venue paths, not guaranteed).
- **Third-place bracket allocation** reproduces FIFA's slot constraints via backtracking matching rather than the literal 495-row table; assignments can differ from FIFA's within the allowed sets.
- Mexico's 6.3% reflects a high Elo (~1980, top-13) plus home advantage in every match; the market is more skeptical (~3%). Decide for yourself whether that's signal or rating inflation from Gold Cup competition.
