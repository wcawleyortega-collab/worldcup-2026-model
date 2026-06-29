# 🏆 World Cup 2026 — Model Report · 2026-06-29

*A fully-automated quant forecasting system: it rates every national team, runs 50,000 Monte-Carlo simulations of the tournament every day, prices every match, and grades its own forecasts against reality — no human in the loop. The honest headline finding: it is well-calibrated but not sharper than the betting market. Full write-up in PORTFOLIO.md.*

<div class="cards"><div class="card"><div class="k">Current favourite</div><div class="v">France</div><div class="s">16.6% chance to win the cup</div></div><div class="card"><div class="k">Forecast accuracy</div><div class="v"><span class="ticker" data-to="0.16676064020833334" data-dec="3" data-suffix="" data-prefix="">0.167</span></div><div class="s">RPS — 25% better than guessing (72 games)</div></div><div class="card"><div class="k">Hit rate</div><div class="v"><span class="ticker" data-to="45.038611111111116" data-dec="0" data-suffix="%" data-prefix="">45%</span></div><div class="s">avg confidence in the result that actually happened</div></div><div class="card"><div class="k">Paper betting</div><div class="v">2W–2L</div><div class="s">net −€90 · tracked honestly, no real money</div></div></div>

## Championship leaderboard
> Each team's simulated chance of reaching each knockout round and lifting the trophy, from 50,000 tournament simulations. Darker cells = more likely. Each probability carries a Monte-Carlo 95% margin of ≤ ±0.4 pp from the 50,000 draws.

| Team | Grp | Elo | R16 | QF | SF | Final | **Champ** |
|---|---|--:|--:|--:|--:|--:|--:|
| France | I | 2187 | 78.7% | 56.2% | 40.2% | 26.2% | **16.6%** |
| Argentina | J | 2134 | 88.2% | 71.5% | 50.1% | 29.2% | **15.9%** |
| Spain | H | 2149 | 76.8% | 47.2% | 32.8% | 18.6% | **11.2%** |
| England | L | 2131 | 80.8% | 53.5% | 32.7% | 19.7% | **10.7%** |
| Brazil | C | 2113 | 65.4% | 41.4% | 23.0% | 13.5% | **7.0%** |
| Portugal | K | 2099 | 65.3% | 32.8% | 20.6% | 10.5% | **5.5%** |
| Netherlands | F | 2075 | 55.4% | 36.9% | 16.8% | 8.7% | **4.4%** |
| Germany | E | 2062 | 71.3% | 29.0% | 16.4% | 8.2% | **3.9%** |
| Colombia | K | 2019 | 64.8% | 37.2% | 16.9% | 7.5% | **3.1%** |
| United States | D | 1934 | 70.8% | 38.5% | 16.0% | 6.7% | **2.9%** |
| Norway | I | 2027 | 57.4% | 26.3% | 12.0% | 5.7% | **2.4%** |
| Mexico | A | 1928 | 57.4% | 24.5% | 11.6% | 5.5% | **2.2%** |

## Title odds over time
> How each contender's championship chance has moved as results came in.

*(chart — view the HTML report)*

## Round of 32 — match by match
> Advance % is the model's chance of winning the tie (including extra time and penalties). W/D/L, scorelines, BTTS and O2.5 are the 90-minute picture. (H) marks the host side, which gets home advantage.

| Tie (advance %) | W/D/L 90′ | xG | Most likely scores | BTTS | O2.5 |
|---|--:|--:|---|--:|--:|
| Brazil 65% v Japan 35% | 50/27/23 | 1.5–1.0 | 1–1 (13%), 1–0 (12%), 2–0 (10%) | 49% | 45% |
| Germany 71% v Paraguay 29% | 56/25/19 | 1.7–0.9 | 1–0 (13%), 1–1 (12%), 2–0 (11%) | 47% | 46% |
| Netherlands 55% v Morocco 45% | 41/28/31 | 1.3–1.1 | 1–1 (13%), 1–0 (11%), 0–0 (9%) | 50% | 44% |
| Ivory Coast 43% v Norway 57% | 30/28/42 | 1.1–1.4 | 1–1 (13%), 0–1 (11%), 0–0 (9%) | 50% | 44% |
| France 79% v Sweden 21% | 64/23/14 | 1.9–0.7 | 1–0 (13%), 2–0 (13%), 1–1 (11%) | 45% | 49% |
| Mexico (H) 57% v Ecuador 43% | 42/28/29 | 1.4–1.1 | 1–1 (13%), 1–0 (11%), 0–0 (9%) | 50% | 44% |
| England 81% v DR Congo 19% | 66/22/12 | 1.9–0.7 | 2–0 (13%), 1–0 (13%), 1–1 (10%) | 44% | 49% |
| Belgium 55% v Senegal 45% | 39/28/32 | 1.3–1.1 | 1–1 (14%), 1–0 (11%), 0–1 (9%) | 50% | 44% |
| United States (H) 71% v Bosnia and Herzegovina 29% | 55/26/19 | 1.6–0.9 | 1–0 (13%), 1–1 (12%), 2–0 (11%) | 47% | 46% |
| Spain 77% v Austria 23% | 62/23/15 | 1.8–0.8 | 1–0 (13%), 2–0 (12%), 1–1 (11%) | 45% | 48% |
| Portugal 65% v Croatia 35% | 50/27/23 | 1.5–1.0 | 1–1 (13%), 1–0 (12%), 2–0 (10%) | 49% | 45% |
| Switzerland 58% v Algeria 42% | 43/28/29 | 1.4–1.1 | 1–1 (13%), 1–0 (11%), 0–0 (9%) | 50% | 44% |
| Australia 46% v Egypt 54% | 33/29/39 | 1.2–1.3 | 1–1 (14%), 0–1 (11%), 1–0 (9%) | 50% | 44% |
| Argentina 88% v Cape Verde 12% | 76/17/7 | 2.3–0.6 | 2–0 (15%), 1–0 (13%), 3–0 (11%) | 40% | 55% |
| Colombia 65% v Ghana 35% | 49/27/24 | 1.5–1.0 | 1–1 (13%), 1–0 (12%), 2–0 (10%) | 49% | 45% |

## How accurate is it? (72 resolved games)
> Pre-kickoff forecasts scored against reality, versus blindly guessing 33/33/33. On every metric, lower is better except hit rate.

| Metric | Model | Guessing |
|---|--:|--:|
| RPS | **0.1668** | 0.2222 |
| log-loss | **0.9032** | 1.0986 |
| Brier | **0.5370** | 0.6667 |
| Hit rate (avg P of actual) | **45.0%** | 33.3% |

### Calibration check
> When the model says X%, does it happen about X% of the time? Points on the diagonal are perfectly calibrated; the bars are 95% bands implied by each bucket's sample size, and bigger dots hold more games.

*(chart — view the HTML report)*

| Forecast bucket | n | Model said | Actually happened |
|---|--:|--:|--:|
| (0.0, 0.2] | 44 | 12.3% | 13.6% |
| (0.2, 0.4] | 109 | 27.5% | 22.0% |
| (0.4, 0.6] | 35 | 48.2% | 60.0% |
| (0.6, 0.8] | 22 | 66.8% | 77.3% |
| (0.8, 1.0] | 6 | 83.8% | 66.7% |

## Model vs the betting market
> Championship odds: the model against Polymarket (overround stripped). Points on the dashed line mean they agree; the table shows where they disagree most.

*(chart — view the HTML report)*

| Biggest disagreement | Model | Market | Gap |
|---|--:|--:|--:|
| France | 16.6% | 23.0% | -6.4 |
| Argentina | 15.9% | 20.4% | -4.5 |
| Brazil | 7.0% | 5.5% | +1.4 |
| Mexico | 2.2% | 1.2% | +1.0 |
| Canada | 1.2% | 0.2% | +0.9 |
| Switzerland | 1.8% | 0.9% | +0.8 |
| Morocco | 2.1% | 1.3% | +0.8 |
| England | 10.7% | 10.0% | +0.7 |

**Who called advancement better?** Scored on who actually reached the Round of 32 (n=48): model Brier **0.180** vs Polymarket **0.154** — the market edged the model, consistent with the project's honest finding that the model is well-calibrated but not sharper than the market.

> Brier skill score versus a no-skill climatology forecast (always predict the base rate, Brier 0.234): model **+23.2%**, market **+34.4%** — both beat chance, the market by more.

## Betting ledger (paper, honest)
> A paper-traded book — no real money — kept to test honestly whether any model-vs-market edge is actually real. So far: no.

- **Settled:** 2W–2L  ·  staked 300  ·  returned 210  ·  **net -89.80** (ROI -29.9%)
- **Scratched** (no stake, pre-kickoff): 3
- **Open:** 9 bets, 650 staked

| Open bet | Odds | Stake |
|---|--:|--:|
| Spain win  /  Uruguay win  /  Iran win | 3.1 | 50 |
| Norway vs France - Over 2.5 goals | 1.65 | 100 |
| Spain to beat Uruguay | 1.5 | 100 |
| Belgium to beat New Zealand | 1.18 | 50 |
| Senegal to beat Iraq | 1.24 | 50 |
| England -1.5 vs Panama (win by 2+) | 1.5 | 90 |
| Croatia vs Ghana - Under 2.5 goals | 1.58 | 80 |
| Algeria vs Austria - Draw | 2.15 | 70 |
| DR Congo to beat Uzbekistan | 2.55 | 60 |

---
*Auto-generated by `daily_report.py` from the live pipeline. Model: Elo → Poisson → Dixon-Coles → Monte-Carlo, blended with bookmaker consensus. Forecasts are logged before kickoff; the ledger is paper-traded and tracked honestly.*