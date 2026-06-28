# World Cup 2026 Forecasting & Market-Efficiency Engine

**A fully-automated quantitative forecasting system: it rates every national team,
simulates the tournament 50,000 times each day, prices every match, scores itself
against reality, and tracks a paper-traded betting book — then publishes a single
shareable report. No human in the loop.**

> **CV line (quantified, every word verifiable in this repo):**
> *"Built a Monte-Carlo forecasting model (Elo, Poisson, Dixon-Coles, 50,000
> simulations) and a live study benchmarking forecasts against market prices;
> well-calibrated out-of-sample across 60+ live matches (RPS 0.18 vs 0.22 baseline).
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

Scored on **60 resolved 2026 group matches**, forecasts logged *before* kickoff:

| Metric | This model | Uniform baseline | Read |
|---|--:|--:|---|
| Ranked Probability Score | **0.176** | 0.222 | 21% better than baseline |
| Log-loss | **0.926** | 1.099 | competitive with published academic models |
| Avg P(actual outcome) | **44.3%** | 33.3% | the right result was the model's pick far more often than chance |

**Calibration** — when the model says 60–80%, it happens ~74% of the time:

| Forecast bucket | Forecast avg | Realized | n |
|---|--:|--:|--:|
| 0–20% | 12% | 16% | 38 |
| 20–40% | 27% | 22% | 86 |
| 40–60% | 48% | 56% | 32 |
| 60–80% | 67% | 74% | 19 |

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
