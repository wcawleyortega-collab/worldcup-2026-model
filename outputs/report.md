# 🏆 World Cup 2026 — Model Report · 2026-06-29

*A fully-automated quant forecasting system: it rates every national team, runs 50,000 Monte-Carlo simulations of the tournament every day, prices every match, and grades its own forecasts against reality — no human in the loop. The honest headline finding: it is well-calibrated but not sharper than the betting market. Full write-up in PORTFOLIO.md.*

## Championship leaderboard (blended forecast)

| Team | Grp | Elo | R16 | QF | SF | Final | **Champ** |
|---|---|--:|--:|--:|--:|--:|--:|
| France | I | 2187 | 79.1% | 56.3% | 40.7% | 26.2% | **16.8%** |
| Argentina | J | 2134 | 88.2% | 71.3% | 50.1% | 29.0% | **15.7%** |
| Spain | H | 2149 | 76.9% | 46.8% | 32.5% | 18.6% | **11.0%** |
| England | L | 2131 | 80.8% | 53.7% | 32.6% | 19.8% | **10.7%** |
| Brazil | C | 2113 | 65.8% | 41.9% | 23.4% | 13.7% | **7.2%** |
| Portugal | K | 2099 | 65.2% | 32.9% | 20.6% | 10.4% | **5.5%** |
| Netherlands | F | 2075 | 55.6% | 40.7% | 18.5% | 9.5% | **4.9%** |
| Germany | E | 2062 | 71.6% | 29.1% | 16.5% | 8.2% | **3.9%** |
| United States | D | 1934 | 70.6% | 38.3% | 16.2% | 6.9% | **3.0%** |
| Colombia | K | 2018 | 64.9% | 36.8% | 16.6% | 7.4% | **3.0%** |
| Morocco | C | 2026 | 44.4% | 29.7% | 11.6% | 5.3% | **2.3%** |
| Norway | I | 2027 | 57.3% | 25.6% | 11.7% | 5.6% | **2.3%** |

## Title odds over time

*(chart — view the HTML report)*

## Round of 32 — model match detail

Advance % is the model's simulated probability of winning the tie (incl. extra time / penalties); W/D/L, scorelines, BTTS and over-2.5 are the 90-minute Poisson–Dixon-Coles distribution. *(H) = host (home advantage).*

| Tie (advance %) | W/D/L 90′ | xG | Most likely scores | BTTS | O2.5 |
|---|--:|--:|---|--:|--:|
| Brazil 66% v Japan 34% | 50/27/23 | 1.5–1.0 | 1–1 (13%), 1–0 (12%), 2–0 (10%) | 49% | 45% |
| Germany 72% v Paraguay 28% | 56/25/19 | 1.7–0.9 | 1–0 (13%), 1–1 (12%), 2–0 (11%) | 47% | 46% |
| Netherlands 56% v Morocco 44% | 41/28/31 | 1.3–1.1 | 1–1 (13%), 1–0 (11%), 0–0 (9%) | 50% | 44% |
| Ivory Coast 43% v Norway 57% | 30/28/42 | 1.1–1.4 | 1–1 (13%), 0–1 (11%), 0–0 (9%) | 50% | 44% |
| France 79% v Sweden 21% | 64/23/14 | 1.9–0.7 | 1–0 (13%), 2–0 (13%), 1–1 (11%) | 45% | 49% |
| Mexico (H) 57% v Ecuador 43% | 42/28/29 | 1.4–1.1 | 1–1 (13%), 1–0 (11%), 0–0 (9%) | 50% | 44% |
| England 81% v DR Congo 19% | 66/22/12 | 1.9–0.7 | 2–0 (13%), 1–0 (13%), 1–1 (10%) | 44% | 49% |
| Belgium 54% v Senegal 46% | 39/29/32 | 1.3–1.1 | 1–1 (14%), 1–0 (11%), 0–1 (9%) | 50% | 44% |
| United States (H) 71% v Bosnia and Herzegovina 29% | 55/26/19 | 1.6–0.9 | 1–0 (13%), 1–1 (12%), 2–0 (11%) | 47% | 46% |
| Spain 77% v Austria 23% | 62/23/15 | 1.8–0.8 | 1–0 (13%), 2–0 (12%), 1–1 (11%) | 45% | 48% |
| Portugal 65% v Croatia 35% | 50/27/23 | 1.5–1.0 | 1–1 (13%), 1–0 (12%), 2–0 (10%) | 49% | 45% |
| Switzerland 59% v Algeria 41% | 43/28/29 | 1.4–1.1 | 1–1 (13%), 1–0 (11%), 0–0 (9%) | 50% | 44% |
| Australia 46% v Egypt 54% | 33/29/39 | 1.2–1.3 | 1–1 (14%), 0–1 (11%), 1–0 (9%) | 50% | 44% |
| Argentina 88% v Cape Verde 12% | 76/17/7 | 2.3–0.6 | 2–0 (15%), 1–0 (13%), 3–0 (11%) | 40% | 55% |
| Colombia 65% v Ghana 35% | 49/27/24 | 1.5–1.0 | 1–1 (13%), 1–0 (12%), 2–0 (10%) | 49% | 45% |

## Model skill — 72 resolved group games

| Metric | Model | Uniform baseline |
|---|--:|--:|
| RPS (lower better) | **0.1668** | 0.2222 |
| Log-loss | **0.9032** | 1.0986 |
| Brier | **0.5370** | 0.6667 |
| Avg P(actual outcome) | **45.0%** | 33.3% |

### Calibration (forecast prob vs realized frequency)

| Bucket | n | Forecast | Realized |
|---|--:|--:|--:|
| (0.0, 0.2] | 44 | 12.3% | 13.6% |
| (0.2, 0.4] | 109 | 27.5% | 22.0% |
| (0.4, 0.6] | 35 | 48.2% | 60.0% |
| (0.6, 0.8] | 22 | 66.8% | 77.3% |
| (0.8, 1.0] | 6 | 83.8% | 66.7% |

## Model vs market (live efficiency study)

Championship odds: the model against Polymarket (overround stripped). Points on the dashed line mean agreement; the table lists where they diverge most.

*(chart — view the HTML report)*

| Biggest disagreement | Model | Market | Gap |
|---|--:|--:|--:|
| France | 16.8% | 22.6% | -5.7 |
| Argentina | 15.7% | 20.5% | -4.8 |
| Brazil | 7.2% | 5.9% | +1.2 |
| Mexico | 2.2% | 1.1% | +1.0 |
| Morocco | 2.3% | 1.3% | +1.0 |
| Switzerland | 1.8% | 0.9% | +0.9 |
| United States | 3.0% | 2.2% | +0.8 |
| England | 10.7% | 10.1% | +0.6 |

**Advancement (pre-tournament priors, scored on who reached the Round of 32, n=48):** model Brier **0.180** vs Polymarket **0.154** — the market edged the model, consistent with the project's honest finding that the model is well-calibrated but not sharper than the market.

## Betting ledger (paper, honest)

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