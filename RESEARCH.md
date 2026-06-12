# World Cup Prediction Methodologies: A Technical Survey

*Survey of world-class forecasting systems, compiled June 2026 to guide the model in this repo. Sources linked per section.*

---

## 1. FiveThirtyEight's Soccer Power Index (SPI)

Every team carries an **offensive rating** (expected goals scored vs an average team on neutral ground) and a **defensive rating** (expected goals conceded). These collapse into a single SPI = expected share of available points vs an average opponent.

**Match prediction:** projected goals λ_A = f(OFF_A, DEF_B, venue, rest); goals assumed independent Poisson; build the score matrix M[i][j] = P(A=i)·P(B=j); sum below/on/above the diagonal for win/draw/loss. 538 noted independent Poisson *underestimates draws* and applied a diagonal inflation (the problem Dixon-Coles solves analytically).

**Updates** move ratings toward observed performance measured on adjusted goals, shot xG, and non-shot xG, weighted by match importance.

**World Cup specifics:** international ratings were a **75/25 blend** of match-based SPI and roster-based (club) SPI; Russia 2018 got ≈ **+0.4 goals** host advantage and all UEFA teams ≈ a third of that as a regional bonus. Tournament forecast = Monte Carlo over the full bracket with FIFA tiebreakers, re-run after every matchday; knockout extra-time/penalty win probability modeled as a function of SPI difference.

538 was shut down in 2023 — no official 2026 forecast exists (Nate Silver publishes "PELE" ratings on Substack).

Sources: [2022 methodology](https://fivethirtyeight.com/features/how-our-2022-world-cup-predictions-work/) · [2018 methodology](https://fivethirtyeight.com/features/how-our-2018-world-cup-predictions-work/) · [data on GitHub](https://github.com/fivethirtyeight/data/tree/master/world-cup-predictions)

## 2. World Football Elo Ratings (eloratings.net)

```
R_new = R_old + K · G · (W − W_e),   W_e = 1 / (1 + 10^(−dr/400))
dr = R_home − R_away + 100·(home advantage; 0 if neutral)
```

| Match type | K |
|---|---|
| World Cup finals | 60 |
| Continental finals & major intercontinental | 50 |
| WC/continental qualifiers; Nations League | 40 |
| Other tournaments | 30 |
| Friendlies | 20 |

Goal-difference multiplier G: 1 (margin ≤ 1), 1.5 (= 2), (11+N)/8 (N ≥ 3).

**Elo → goals bridge:** the published academic approach (Csató 2025, 48-team WC simulations; football-rankings.info) regresses each team's goals on its win expectancy W_e — a low-order polynomial fitted on ~40,000 internationals, separately for home/away/neutral — then draws scores from Poissons. Rule of thumb: total ≈ 2.6 goals neutral; expected goal difference ≈ ±1 at ±150–200 Elo.

Strengths: reproducible from public data back to 1872; hard to beat as a single-number strength measure. Weaknesses: no attack/defense split; no native scoreline distribution; K-ladder and +100 HA are conventions.

Sources: [eloratings.net](https://eloratings.net/) · [Wikipedia](https://en.wikipedia.org/wiki/World_Football_Elo_Ratings) · [Csató, arXiv 2502.08565](https://arxiv.org/abs/2502.08565)

## 3. Dixon-Coles (1997)

*JRSS-C 46(2), 265–280.* For home i vs away j:

```
P(X=x, Y=y) = τ_{λ,μ}(x,y) · Pois(x; λ) · Pois(y; μ)
λ = α_i β_j γ   (home attack × away defense × home advantage)
μ = α_j β_i
```

Low-score dependence correction (only the 0-0/1-0/0-1/1-1 cells):

```
τ(0,0) = 1 − λμρ;  τ(0,1) = 1 + λρ;  τ(1,0) = 1 + μρ;  τ(1,1) = 1 − ρ;  else 1
```

ρ < 0 inflates 0-0 and 1-1 (draws); fitted values ≈ **−0.05 to −0.15**.

**Time decay:** maximize a weighted pseudo-likelihood with φ(Δt) = exp(−ξΔt); original ξ = 0.0065/half-week ≈ 0.0018/day (half-life ≈ 380 days); for internationals ξ ≈ 0.001–0.002/day over ~8 years. ξ is tuned by out-of-sample predictive log-likelihood, not inside the likelihood.

Caveat for internationals: inter-confederation matches are rare, so attack/defense parameters are weakly identified across confederations — anchor to Elo or regularize.

Sources: [Dixon & Coles 1997](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/1467-9876.00065) · [opisthokonta ξ replication](https://opisthokonta.net/?p=1013) · [penaltyblog (Python)](https://pena.lt/y/2021/06/24/predicting-football-results-using-python-and-dixon-and-coles/)

## 4. Bookmaker Consensus Model (Leitner-Zeileis-Hornik)

1. Strip the overround per bookmaker: p̃ = (1/o) / (1+δ), 1+δ = Σ 1/o.
2. Average on the log-odds scale across ~24–28 bookmakers.
3. **Invert the tournament**: find Bradley-Terry abilities such that simulating the full tournament (actual groups/bracket, 100k runs) reproduces the consensus winning probabilities. The resulting abilities are draw-free and usable for match-level prediction.

Empirically the strongest single predictor in every Groll/Zeileis comparison (it embeds injury/news information no historical model has), but only available near the tournament and inherits market biases (longshot bias, England sentiment).

Sources: [Zeileis 2022 multiverse](https://www.zeileis.org/news/fifa2022/) · [2026 forecast](https://www.r-bloggers.com/2026/06/football-meets-machine-learning-forecasting-the-2026-fifa-world-cup/)

## 5. ML Hybrids (Groll et al.) and Published 2026 Forecasts

Evolution: regularized Poisson regression (WC 2014) → random forest on covariate differences (WC 2018, arXiv 1806.03208) → **hybrid random forest** (JQAS 2019): feed model-based ability estimates (time-decayed bivariate Poisson abilities, bookmaker-consensus abilities, plus-minus player ratings) into the forest alongside covariates (market value, FIFA rank, Elo, age, GDP...). The forest predicts per-team goal rates; a bivariate Poisson gives the score distribution; 100,000 tournament simulations give the "multiverse."

**Published pre-tournament 2026 forecasts (sanity anchors):**

| Source | Favorite | Next |
|---|---|---|
| Groll/Zeileis hybrid RF | Spain 14.5% | England 12.4%, France 12.4%, Germany 11.2% |
| Opta supercomputer | Spain 16.1% | France 13.0%, England 11.2%, Argentina 10.4%, Portugal 7.0%, Brazil 6.6% |
| Bookmakers (FanDuel, June 10) | Spain +450 | France +500, England +700, Brazil/Portugal +850, Argentina +1000 |

## 6. Key Empirical Calibration Targets

| Quantity | Value |
|---|---|
| Home advantage (Elo / goals) | +100 points / ≈ +0.3–0.45 goals |
| Host overperformance | hosts beat own baseline in 16 of 22 WCs |
| Regional (same-confederation) advantage | ≈ 1/3 of host advantage (538's 2018 treatment) |
| Draw frequency | ≈ 22% of WC group matches; ≈ 27% of knockouts level after 90' |
| Goals per match (recent WCs) | 2.3–2.7 (2018: 2.64; 2022: 2.69) |
| Dixon-Coles ρ | −0.05 to −0.15 |
| Penalty shootouts | ≈ 50/50, tiny skill edge |

## 7. Recommended Architecture (implemented in this repo)

**A goal-rate Poisson core, driven by Elo, corrected à la Dixon-Coles, wrapped in Monte Carlo:**

1. **Elo layer** — full history (1872–), K ladder, margin multiplier, +100 HA.
2. **Match engine** — Poisson GLM mapping win expectancy → expected goals (cubic in W_e + home dummy, ML-fitted on 1990+ internationals); Dixon-Coles τ correction with ρ fitted by ML.
3. **Venue layer** — hosts get full Elo home advantage in their home fixtures (encoded in the fixture list); non-host CONCACAF sides get ≈ +33 Elo regional bonus on neutral North American soil.
4. **Tournament Monte Carlo** — exact 2026 format: 12 groups, FIFA tiebreakers, best-8 thirds via constraint matching to the official bracket slots, official matches 73–104; knockout draws resolved by extra time at ⅓ scoring rate then a near-coin-flip shootout.
5. **Validation** — frozen pre-tournament backtests on WC 2018/2022 scored by RPS and log-loss vs baselines; 2026 output sanity-checked against the published consensus.

Extensions that would close the remaining gap to the state of the art: bookmaker-consensus blending (the market deserves the largest weight), squad market-value covariates, and an xG-based update rule.
