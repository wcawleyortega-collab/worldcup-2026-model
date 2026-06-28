"""Does squad market value improve the model beyond Elo? An out-of-sample test.

The README named squad/xG covariates as the honest ceiling for this architecture.
This script actually tests the squad-value half of that claim on the played
WC2026 group stage, with Elo frozen *before* the tournament (so the test is
out-of-sample exactly as in `tune_goals.py`).

Three honest checks:
  1. Redundancy   — cross-sectional R^2 of Elo on log(squad value). High R^2 means
                    the two are mostly the same signal.
  2. Residual info — does the value gap explain match outcomes that Elo misses?
                    (Pearson r of Elo-residual vs value gap, with p-value.)
  3. Prediction    — blend the value-implied rating into Elo at weight (1-alpha)
                    and score W/D/L (RPS / log-loss / avg p(actual)). If pure Elo
                    (alpha=1) is not beaten, the covariate adds nothing predictive.
"""
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

from wc_model.elo import compute_elo, win_expectancy, HOME_ADV
from wc_model.goals import GoalsModel
from wc_model.squad import load_values, fit_value_to_elo, blended_ratings

WC_START, WC_END = "2026-06-11", "2026-06-28"

df = pd.read_csv("data/results.csv", na_values=["NA"])
df["neutral"] = df["neutral"].astype(str).str.upper() == "TRUE"
values = load_values()

# Frozen pre-tournament state (same protocol as tune_goals.py).
ratings, log = compute_elo(df, as_of=WC_START)
gm = GoalsModel().fit(log[log["date"] < WC_START])

# Played group games.
wc = df[(df["tournament"] == "FIFA World Cup") & (df["date"] >= WC_START)
        & (df["date"] <= WC_END)].dropna(subset=["home_score", "away_score"])

# ---------------------------------------------------------------- 1. redundancy
_, st = fit_value_to_elo(ratings, values)
print(f"[1] Redundancy:  Elo = {st['intercept']:.0f} + {st['slope']:.1f}*log(value)"
      f"   R^2 = {st['r2']:.3f}  (n={st['n']} teams)")
print(f"    -> squad value already explains {st['r2']:.0%} of the Elo rating.\n")

# ---------------------------------------------------------------- 2. residual info
resid, vgap = [], []
for h, a, hs, as_, neu in wc[["home_team", "away_team", "home_score",
                              "away_score", "neutral"]].itertuples(index=False):
    if h not in values or a not in values:
        continue
    we = win_expectancy(ratings.get(h, 1500) - ratings.get(a, 1500)
                        + (0 if neu else HOME_ADV))
    p = np.array(gm.outcome_probs(we, not neu))
    exp_pts = p[0] * 1 + p[1] * 0.5 + p[2] * 0.0
    act_pts = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
    resid.append(act_pts - exp_pts)
    vgap.append(np.log(values[h]) - np.log(values[a]))
r, pval = pearsonr(vgap, resid)
print(f"[2] Residual info:  corr(value gap, Elo residual) = {r:+.3f}  p = {pval:.2f}"
      f"   (n={len(resid)} games)")
verdict = "adds signal Elo misses" if pval < 0.05 else "NO signal beyond Elo (redundant)"
print(f"    -> {verdict}.\n")

# ---------------------------------------------------------------- 3. prediction
def score(rt):
    rps = ll = pa = n = 0
    for h, a, hs, as_, neu in wc[["home_team", "away_team", "home_score",
                                  "away_score", "neutral"]].itertuples(index=False):
        we = win_expectancy(rt.get(h, 1500) - rt.get(a, 1500) + (0 if neu else HOME_ADV))
        p = np.array(gm.outcome_probs(we, not neu))
        obs = 0 if hs > as_ else (1 if hs == as_ else 2)
        o = np.zeros(3); o[obs] = 1
        rps += 0.5 * ((np.cumsum(p) - np.cumsum(o))[:2] ** 2).sum()
        ll += -np.log(max(p[obs], 1e-12)); pa += p[obs]; n += 1
    return rps / n, ll / n, pa / n

print("[3] Prediction (blend value-implied rating into Elo):")
print(f"    {'alpha (Elo weight)':<22}{'RPS':>9}{'log-loss':>11}{'avg p':>8}")
for alpha in [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]:
    rt = ratings if alpha == 1.0 else blended_ratings(ratings, values, alpha)
    rps, ll, pa = score(rt)
    tag = "  <- pure Elo (current model)" if alpha == 1.0 else ""
    print(f"    {alpha:<22.1f}{rps:>9.4f}{ll:>11.3f}{pa:>8.0%}{tag}")
print("\n    lower RPS & log-loss = better. If alpha=1 is not beaten, squad value")
print("    carries no predictive edge over Elo on this sample.")
