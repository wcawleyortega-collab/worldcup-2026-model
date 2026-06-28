# World Cup 2026 Forecasting & Market-Efficiency Engine

**A fully-automated quantitative forecasting system: it rates every national team,
simulates the tournament 50,000 times each day, prices every match, scores itself
against reality, and tracks a paper-traded betting book — then publishes a single
shareable report. No human in the loop.**

> **CV line (quantified, every word verifiable in this repo):**
> *"Built a Monte-Carlo forecasting model (Elo, Poisson, Dixon-Coles, 50,000
> simulations) and a live study benchmarking forecasts against market prices;
> well-calibrated out-of-sample across 70+ live matches (RPS 0.17 vs 0.22 baseline).
> Automated twice-daily data collection, model updates, and a self-publishing
> report (GitHub Actions + Pages)."

---

## Why this is worth a look

Most "prediction model" projects stop at a single notebook that fits some data and
prints a number. This one is built like a **production research system** and, more
importantly, it **grades itself honestly**:

| What employers look for | Where it shows up here |
|---|---|
| Statistical modeling depth | Elo rating engine, Poisson goal GLM, Dixon-Coles draw correction, Monte-Carlo tournament simulator — the same architecture the academic/industry literature converges on (538 SPI, Dixon-Coles 1997, Zeileis/Groll). |
| Rigorous validation | Frozen pre-tournament backtests on WC 2018 & 2022 (RPS 0.209 / 0.222, beating uniform), **plus live out-of-sample scoring** as the 2026 tournament plays out. |
| Calibration, not just accuracy | The model's forecast probabilities match realized frequencies bucket-by-bucket on 60 resolved games (see below). |
| Data engineering & automation | Self-updating macOS LaunchAgent runs the whole pipeline twice daily; fault-tolerant data fetch; Polymarket API ingestion; everything logged before it can resolve. |
| **Intellectual honesty** | The headline finding is *negative* and that's the point — see "The honest result." |

---

## Live model skill (out-of-sample, updates every day)

Scored on **all 72 group-stage matches** (full group stage), forecasts logged *before* kickoff:

| Metric | This model | Uniform baseline | Read |
|---|--:|--:|---|
| Ranked Probability Score | **0.167** | 0.222 | 25% better than baseline |
| Log-loss | **0.903** | 1.099 | competitive with published academic models |
| Avg P(actual outcome) | **45.0%** | 33.3% | the right result was the model's pick far more often than chance |

**Calibration** — when the model says 60–80%, it happens ~77% of the time:

| Forecast bucket | Forecast avg | Realized | n |
|---|--:|--:|--:|
| 0–20% | 12% | 14% | 44 |
| 20–40% | 28% | 22% | 109 |
| 40–60% | 48% | 60% | 35 |
| 60–80% | 67% | 77% | 22 |

*(Numbers above are regenerated automatically into `outputs/report.html` on every run.)*

---

## The honest result (the part a quant interviewer will respect)

I built this partly to answer: **can a well-calibrated model beat the betting market?**

The disciplined, evidence-based answer is **no** — and saying so is the signal.
Backtesting and live tracking show the model performs *at* bookmaker level but **not
sharper than the closing line**; it lacks the team-news/lineup/injury information the
market prices in. So a model-vs-market probability gap is **noise dressed as value**,
not a tradeable edge. The paper betting book proves it: chasing those "edges" loses
(settled record currently negative), so the operating rule became **"default to no
bet; only act on specific information the market hasn't moved on yet."**

That is exactly the lesson that separates someone who understands markets from someone
who overfits a model and assumes they've found free money.

---

## Optimization study (knowing when *not* to add complexity)

I ran a controlled experiment (`tune_goals.py`) testing the textbook next
improvement — **Dixon-Coles exponential time-decay** weighting of the goal model —
against the current uniform fit, refitting the whole pipeline *before* each World
Cup and scoring it out-of-sample:

| Goal-fit policy | WC2018 RPS | WC2022 RPS | WC2026 RPS | Mean |
|---|--:|--:|--:|--:|
| Current (uniform, 2010+) | 0.2092 | 0.2211 | 0.1669 | **0.1991** |
| + time-decay (4–12y half-life) | 0.2089–0.2092 | 0.2212–0.2216 | 0.1668–0.1673 | 0.1991 |

The decay is **neutral** (4th-decimal noise), so it ships **disabled by default** —
the running Elo already absorbs recency, leaving nothing for the goal map to gain.
Likewise, a holdout refit (`eval_models.py`) chose a *flatter* probability scale
than the base, confirming the model is **not** under-confident and should not be
sharpened. **Recognizing a saturated model and declining to over-engineer it is
itself the result.** The lesson it pointed to: you don't beat a saturated model by
re-tuning the data it already has — you beat it by adding *orthogonal* information.
So I tested exactly that.

## The covariate that did help: squad market value (out-of-sample)

The literature (Peeters 2018; Gerhards & Mutz) finds aggregate **squad market value**
is among the strongest single predictors of international results. I added a real
Transfermarkt snapshot of all 48 squads (`data/squad_values.csv`) and tested —
with Elo frozen *before* the tournament, exactly as above — whether value carries
information Elo does not (`tune_squad.py`):

- **Redundant?** Cross-sectionally, log(squad value) explains **R² = 0.61** of the
  Elo rating — overlapping, but 39% is *not* shared.
- **Predictive?** Blending the value-implied rating into Elo and scoring W/D/L on
  the 72 played WC2026 group games:

| Elo / value mix | RPS | Read |
|---|--:|---|
| Pure Elo (current) | 0.1669 | baseline |
| 70% Elo / 30% value *(shipped)* | 0.1598 | **4% better** |
| ~30% Elo / 70% value *(in-sample optimum)* | 0.1568 | 6% better |
| Pure value | 0.1588 | worse than the mix |

The curve has an **interior optimum** and turns back up toward pure value — the
signature of *real, complementary signal*, not over-fit noise (over-fitting would
keep improving as you trust Elo less; it doesn't). Squad value corrects Elo's known
lags — confederation inflation, slow adjustment for fast-rising sides. This is the
**first tested change that beats the model out of sample**, and the contrast with
the time-decay null is the point: re-tuning the same data did nothing; new
information did.

**Shipped honestly and conservatively.** The blend goes live at a **0.7 Elo / 0.3
value** weight — deliberately *not* the in-sample optimum (~0.3), because one
tournament (n = 72) can't pin the weight, and a conservative tilt captures a real
share of the gain while staying close to the battle-tested rating model. Caveats
stated up front: single-tournament validation, and partial overlap with the
bookmaker-consensus layer (applied before it, so the market fit re-absorbs the
rest). **xG was the other named covariate — and I left it out on purpose:** no
public per-team international xG history exists for all 48 sides, so adding it would
mean inventing data, which this project won't do.

## Architecture

```
 martj42/international_results  ──┐         Polymarket Gamma API
 (49,000+ internationals)        │                  │  (144 live contracts)
                                 ▼                  ▼
                        ┌──────────────────────────────────┐
                        │  update_predictions.py (daily)    │
                        │  Elo ──▶ Poisson GLM ──▶ Dixon-   │
                        │  Coles ──▶ 50k Monte-Carlo sims   │
                        │  ⊕ bookmaker-consensus blend      │
                        └──────────────────────────────────┘
                                 │
        ┌────────────────────────┼─────────────────────────┐
        ▼                        ▼                          ▼
 team_probabilities      match_forecast_history       polymarket_history
 (champion odds)         (logged pre-kickoff)         (market panel)
        │                        │                          │
        └──────────┬─────────────┴──────────────────────────┘
                   ▼
        daily_report.py  ──▶  outputs/report.html  (shareable, self-contained)
                              + evaluate_forecasts.py (skill vs market)
```

**Stack:** Python · pandas · numpy · scipy (MLE fitting) · matplotlib · macOS
`launchd`. ~1,000 lines of model + pipeline code, no framework bloat.

---

## What's automated (the "set it and forget it" part)

A LaunchAgent (`com.worldcup.predictions`) fires **twice daily (06:30 / 23:30)** and:

1. Pulls the latest match results (fault-tolerant: a failed fetch keeps the cached copy).
2. Re-rates every team through all completed games and re-simulates the tournament 50k times.
3. Snapshots all 144 Polymarket contracts for the efficiency study.
4. Logs every forecast *before* it can resolve (so scoring is honestly out-of-sample).
5. **Regenerates `outputs/report.html`** — the single artifact you can send to anyone.

Manual run of the whole thing: `./run_daily.sh`

---

## How to demo it in 30 seconds

```bash
.venv/bin/python daily_report.py      # regenerate the report from live data
open outputs/report.html              # the shareable scorecard
.venv/bin/python evaluate_forecasts.py  # model skill vs market, printed
```

Then point to: **`RESEARCH.md`** (the literature survey the design follows),
**`RESEARCH_DESIGN.md`** (the pre-registered market-efficiency study), and the live
**`outputs/report.html`**.

---

## Skills this demonstrates

`Statistical modeling` · `Monte-Carlo simulation` · `Maximum-likelihood estimation`
· `Model calibration & backtesting` · `Time-series / panel data collection`
· `Market microstructure & efficiency testing` · `Data-pipeline engineering`
· `Job scheduling / automation` · `Honest, adversarial self-evaluation`
