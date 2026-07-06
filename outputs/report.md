# 🏆 World Cup 2026 — Model Report · 2026-07-06

*A fully-automated quant forecasting system: it rates every national team, runs 50,000 Monte-Carlo simulations of the tournament every day, prices every match, and grades its own forecasts against reality — no human in the loop. The honest headline finding: it is well-calibrated but not sharper than the betting market. Full write-up in PORTFOLIO.md.*

<div class="cards"><div class="card"><div class="k">Current favourite</div><div class="v">France</div><div class="s">26.2% chance to win the cup</div></div><div class="card"><div class="k">Forecast accuracy</div><div class="v"><span class="ticker" data-to="0.16676064020833334" data-dec="3" data-suffix="" data-prefix="">0.167</span></div><div class="s">RPS — 25% better than guessing (72 games)</div></div><div class="card"><div class="k">Hit rate</div><div class="v"><span class="ticker" data-to="45.038611111111116" data-dec="0" data-suffix="%" data-prefix="">45%</span></div><div class="s">avg confidence in the result that actually happened</div></div><div class="card"><div class="k">Paper betting</div><div class="v">2W–2L</div><div class="s">net −€90 · tracked honestly, no real money</div></div></div>

## Championship leaderboard
> Each team's simulated chance of reaching each knockout round and lifting the trophy, from 50,000 tournament simulations. Darker cells = more likely. Each probability carries a Monte-Carlo 95% margin of ≤ ±0.4 pp from the 50,000 draws.

| Team | Grp | Elo | R16 | QF | SF | Final | **Champ** |
|---|---|--:|--:|--:|--:|--:|--:|
| France | I | 2203 | 100.0% | 100.0% | 69.0% | 42.8% | **26.2%** |
| England | L | 2162 | 100.0% | 100.0% | 60.5% | 37.0% | **19.4%** |
| Argentina | J | 2137 | 100.0% | 79.6% | 51.3% | 26.5% | **13.0%** |
| Spain | H | 2161 | 100.0% | 55.4% | 36.1% | 18.4% | **10.4%** |
| Norway | I | 2070 | 100.0% | 100.0% | 39.5% | 19.8% | **8.1%** |
| Portugal | K | 2116 | 100.0% | 44.6% | 26.6% | 12.2% | **6.2%** |
| Morocco | C | 2050 | 100.0% | 100.0% | 31.0% | 13.7% | **5.9%** |
| United States | D | 1944 | 100.0% | 51.7% | 19.8% | 7.2% | **3.1%** |
| Colombia | K | 2023 | 100.0% | 51.4% | 21.5% | 8.2% | **2.9%** |
| Switzerland | B | 2010 | 100.0% | 48.6% | 19.9% | 7.0% | **2.4%** |
| Belgium | G | 2024 | 100.0% | 48.3% | 17.5% | 5.7% | **2.2%** |
| Egypt | G | 1905 | 100.0% | 20.4% | 7.3% | 1.6% | **0.3%** |

## Title odds over time
> How each contender's championship chance has moved as results came in.

*(chart — view the HTML report)*

## Round of 32 — match by match
> Advance % is the model's chance of winning the tie (including extra time and penalties). W/D/L, scorelines, BTTS and O2.5 are the 90-minute picture. (H) marks the host side, which gets home advantage.

| Tie (advance %) | W/D/L 90′ | xG | Most likely scores | BTTS | O2.5 |
|---|--:|--:|---|--:|--:|
| Brazil 100% v Japan 0% | 50/27/23 | 1.5–0.9 | 1–1 (13%), 1–0 (12%), 2–0 (10%) | 48% | 45% |
| Germany 0% v Paraguay 100% | 55/26/19 | 1.7–0.9 | 1–0 (13%), 1–1 (12%), 2–0 (11%) | 47% | 46% |
| Netherlands 0% v Morocco 100% | 38/29/33 | 1.3–1.2 | 1–1 (14%), 1–0 (10%), 0–1 (10%) | 50% | 44% |
| Ivory Coast 0% v Norway 100% | 24/27/49 | 1.0–1.5 | 1–1 (13%), 0–1 (12%), 0–2 (9%) | 49% | 45% |
| France 100% v Sweden 0% | 67/21/12 | 2.0–0.7 | 2–0 (14%), 1–0 (13%), 1–1 (10%) | 44% | 50% |
| Mexico (H) 100% v Ecuador 0% | 44/28/28 | 1.4–1.1 | 1–1 (13%), 1–0 (11%), 0–0 (9%) | 50% | 44% |
| England 100% v DR Congo 0% | 72/19/9 | 2.1–0.6 | 2–0 (14%), 1–0 (13%), 3–0 (10%) | 42% | 52% |
| Belgium 100% v Senegal 0% | 43/28/29 | 1.4–1.1 | 1–1 (13%), 1–0 (11%), 0–0 (9%) | 50% | 44% |
| United States (H) 100% v Bosnia and Herzegovina 0% | 58/25/17 | 1.7–0.8 | 1–0 (13%), 1–1 (12%), 2–0 (12%) | 47% | 47% |
| Spain 100% v Austria 0% | 65/22/13 | 1.9–0.7 | 1–0 (13%), 2–0 (13%), 1–1 (10%) | 44% | 49% |
| Portugal 100% v Croatia 0% | 54/26/20 | 1.6–0.9 | 1–0 (13%), 1–1 (12%), 2–0 (11%) | 48% | 46% |
| Switzerland 100% v Algeria 0% | 48/27/24 | 1.5–1.0 | 1–1 (13%), 1–0 (12%), 2–0 (9%) | 49% | 45% |
| Colombia 100% v Ghana 0% | 50/27/23 | 1.5–0.9 | 1–1 (13%), 1–0 (12%), 2–0 (10%) | 49% | 45% |
| Australia 0% v Egypt 100% | 32/28/39 | 1.1–1.3 | 1–1 (14%), 0–1 (11%), 1–0 (9%) | 50% | 44% |
| Argentina 100% v Cape Verde 0% | 77/16/7 | 2.3–0.6 | 2–0 (15%), 1–0 (12%), 3–0 (12%) | 40% | 55% |
| Canada (H) 100% v Morocco 100% | 23/27/50 | 0.9–1.5 | 1–1 (13%), 0–1 (12%), 0–2 (10%) | 49% | 45% |
| Paraguay 100% v France 100% | 7/17/76 | 0.6–2.3 | 0–2 (15%), 0–1 (13%), 0–3 (11%) | 40% | 55% |
| Brazil 100% v Norway 100% | 39/29/33 | 1.3–1.2 | 1–1 (14%), 1–0 (11%), 0–1 (9%) | 50% | 44% |
| Mexico (H) 100% v England 100% | 22/27/51 | 0.9–1.5 | 1–1 (13%), 0–1 (12%), 0–2 (10%) | 48% | 45% |
| Portugal 100% v Spain 100% | 31/28/40 | 1.1–1.3 | 1–1 (14%), 0–1 (11%), 0–0 (9%) | 50% | 44% |
| United States (H) 100% v Belgium 100% | 37/29/34 | 1.3–1.2 | 1–1 (14%), 1–0 (10%), 0–1 (10%) | 50% | 44% |
| Argentina 100% v Egypt 100% | 65/22/13 | 1.9–0.7 | 1–0 (13%), 2–0 (13%), 1–1 (10%) | 45% | 49% |
| Switzerland 100% v Colombia 100% | 34/29/37 | 1.2–1.2 | 1–1 (14%), 0–1 (10%), 1–0 (10%) | 50% | 44% |
| France 100% v Morocco 100% | 53/26/21 | 1.6–0.9 | 1–0 (13%), 1–1 (12%), 2–0 (10%) | 48% | 45% |
| Norway 100% v England 100% | 27/28/45 | 1.0–1.4 | 1–1 (13%), 0–1 (12%), 0–0 (9%) | 49% | 44% |

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

## Advancement skill (Round-of-32, Brier — lower better)

- Model: **0.0756** (1008 team-days)
- Polymarket: **0.0512**

## Model vs the betting market
> Championship odds: the model against Polymarket (overround stripped). Points on the dashed line mean they agree; the table shows where they disagree most.

*(chart — view the HTML report)*

| Biggest disagreement | Model | Market | Gap |
|---|--:|--:|--:|
| Spain | 10.4% | 18.1% | -7.8 |
| France | 26.2% | 33.0% | -6.8 |
| Portugal | 6.2% | 0.1% | +6.1 |
| Argentina | 13.0% | 17.1% | -4.1 |
| England | 19.4% | 15.3% | +4.1 |
| Norway | 8.1% | 4.8% | +3.4 |
| Morocco | 5.9% | 2.7% | +3.2 |
| Switzerland | 2.4% | 1.0% | +1.4 |

**Who called advancement better?** Scored on who actually reached the Round of 32 (n=48): model Brier **0.163** vs Polymarket **0.139** — the market edged the model, consistent with the project's honest finding that the model is well-calibrated but not sharper than the market.

> Brier skill score versus a no-skill climatology forecast (always predict the base rate, Brier 0.229): model **+28.8%**, market **+39.3%** — both beat chance, the market by more.

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