# Are Prediction Markets Efficient? Live Evidence from the 2026 FIFA World Cup

*Research design — drafted June 12, 2026 (day 2 of the tournament). The dataset this
study needs is being collected live by this repo's automation; it cannot be
reconstructed after the fact.*

## Motivation

Prediction markets are increasingly cited as probability oracles (elections,
macro events, sports), but clean tests of their calibration are rare because
they require (a) many comparable contracts resolving on a short horizon and
(b) a credible model benchmark constructed *ex ante*. The 2026 World Cup is an
unusually good laboratory: 104 matches in 39 days, 48 simultaneous binary
advancement contracts plus 12 group-winner books and an outright market on
Polymarket, dense bookmaker quotes, and enough public data to build a
transparent statistical benchmark before the tournament starts — which this
repo did (see README.md, RESEARCH.md).

## Data (collected live, twice daily at 06:30 and 23:30 via launchd)

| Series | Source | Contents |
|---|---|---|
| `data/polymarket_history.csv` | Polymarket Gamma API | 144 contracts/snapshot: 48 advancement, 48 group-winner, 48 outright; price, bid/ask, last trade, volume, liquidity |
| `outputs/history.csv` | this model | daily P(reach each round) for all 48 teams, conditioned on results so far |
| `outputs/match_forecast_history.csv` | this model | pre-match W/D/L probabilities + xG for every group fixture |
| `data/market_odds.csv` | BetMGM + DraftKings | pre-tournament outright odds (the blend prior) |
| `data/results.csv`, `data/shootouts.csv` | martj42 GitHub | realized outcomes |

The model benchmark (Elo + Dixon-Coles Poisson, 50% pre-tournament bookmaker
blend, 50k Monte Carlo) is frozen in design before the tournament; its daily
output changes only through conditioning on results — no parameter is tuned
mid-tournament. This is the key identification feature: any model-vs-market
divergence in accuracy is not the product of in-sample fitting.

## Research questions

**RQ1 — Calibration.** Are Polymarket advancement prices well calibrated?
Among contracts priced at p, do a fraction p resolve Yes? Same question for
the model. Method: reliability diagrams + Brier decomposition
(uncertainty / reliability / resolution; Murphy 1973).

**RQ2 — Relative accuracy.** Does the market beat the transparent model?
Daily Brier scores per team-contract, model vs market, with Diebold-Mariano
tests on the loss differentials (clustered by team; matches within group are
correlated). Repeat by horizon: pre-tournament, after matchday 1, 2, final
matchday. Hypothesis from the literature (Leitner-Zeileis-Hornik; Groll et
al.): the market wins pre-tournament (it embeds squad news), but the gap
shrinks once results dominate — and may invert late in the group stage when
qualification scenarios require combinatorial tiebreaker reasoning that a
simulator does exactly and traders do approximately.

**RQ3 — Speed of incorporation.** How fast do advancement prices absorb match
results? The 23:30 snapshot prices vs the model's post-result conditioned
probabilities; overnight drift (23:30 → 06:30) as a measure of slow
adjustment. Event-study around the ~3 matches/day.

**RQ4 — Favorite-longshot bias.** Plot price vs realized frequency across the
48 advancement and 48 outright contracts; compare with the documented bias in
bookmaker odds (here: the overround-stripped two-book consensus). Prediction
markets are claimed to suffer less FLB than bookmakers — testable directly.

**RQ5 (stretch) — The tiebreaker anomaly.** On each group's final matchday,
compute exact qualification probabilities by simulation (the model does this
natively, including the 8-best-thirds ranking and FIFA's 495-combination
bracket allocation) and compare with market prices during the simultaneous
final games. Any systematic mispricing here is the cleanest possible evidence
of bounded rationality in market microstructure terms — the information is
public and the computation is mechanical, just hard for humans.

## Methods checklist

- Proper scoring rules: Brier, log score, RPS (match level)
- Reliability diagrams with bootstrap CIs; Brier decomposition
- Diebold-Mariano forecast comparison tests (HAC/cluster-robust)
- Mincer-Zarnowitz regressions: outcome on forecast (α=0, β=1 under efficiency)
- Event-study around match results for RQ3
- Robustness: mid prices vs last trade; liquidity-weighted; excluding
  thin contracts (<$10k volume)

## Deliverables and timeline

1. **During tournament (June 11 – July 19):** automation collects; optional
   short posts tracking model vs market (content for LinkedIn/blog; each post
   is a pre-registered prediction, which strengthens the paper).
2. **Late July:** run `evaluate_forecasts.py` final scoring; write up results
   (~8-10k words). Target: BSc-portfolio paper / ESE MSc seminar paper /
   SSRN working paper. Realistic journal targets if results are clean:
   *International Journal of Forecasting* (where the bookmaker-consensus
   literature lives), *Journal of Sports Economics*, or *Economics Letters*
   (if one sharp result, e.g. RQ5).
3. **Repo as portfolio piece:** the public GitHub repo demonstrates the full
   quant workflow — model design from literature, MLE estimation, Monte Carlo,
   market calibration, automated data collection, proper-scoring evaluation.

## Pre-registration note

This design is committed to git before outcomes are known (first commit:
June 12, 2026, two group matches played). The git history is the timestamp.
Analysis choices made after data collection will be flagged as exploratory
in the write-up.

## Known limitations (state them, don't hide them)

- One tournament: 48 advancement contracts but heavy cross-sectional
  correlation within groups → effective sample is smaller; DM tests must
  cluster. Frame as a case study with exact inference where possible.
- Polymarket prices include a 3% taker fee and finite depth; "mispricing"
  below transaction costs is consistent with no-arbitrage efficiency.
- The model's pre-tournament blend uses bookmaker odds, so pre-tournament
  model-vs-market comparisons partially compare the market with itself; the
  clean comparisons start at matchday 1, and the pure-model series
  (`team_probabilities_pure.csv`) is retained as a market-free benchmark.
- The 06:30/23:30 sampling grid limits RQ3's resolution to overnight windows.
