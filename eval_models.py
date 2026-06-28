"""Which W/D/L map is best? Compare three predictors on (a) 2018-2026 holdout
and (b) the 24 actual 2026 WC group games that prompted this:
  1. RECAL  - recalibrated ordered-logit on Elo dr (HA=100, s=193.3, theta=114.6)
  2. GOALS  - the live pipeline's path: Elo -> Poisson GLM -> Dixon-Coles -> W/D/L
  3. BASE   - ordered-logit at the current implied scale s0=173.7
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from wc_model.elo import k_factor, goal_multiplier, INITIAL_RATING
from wc_model.goals import GoalsModel

S0 = 400.0 / np.log(10)

df = pd.read_csv("data/results.csv", na_values=["NA"]).dropna(subset=["home_score", "away_score"]).copy()
df["neutral"] = df["neutral"].astype(str).str.upper() == "TRUE"
df = df.sort_values("date").reset_index(drop=True)
df["home_score"] = df["home_score"].astype(int); df["away_score"] = df["away_score"].astype(int)
df["outcome"] = np.sign(df["home_score"] - df["away_score"]).astype(int) + 1

homes, aways = df["home_team"].values, df["away_team"].values
hs, as_, neu, tour = df["home_score"].values, df["away_score"].values, df["neutral"].values, df["tournament"].values
ratings = {}; dr = np.empty(len(df)); we_home = np.empty(len(df))
for i in range(len(df)):
    rh = ratings.get(homes[i], INITIAL_RATING); ra = ratings.get(aways[i], INITIAL_RATING)
    d = rh - ra + (0.0 if neu[i] else 100.0); dr[i] = d
    we = 1.0 / (1.0 + 10 ** (-d / 400.0)); we_home[i] = we
    w = 1.0 if hs[i] > as_[i] else (0.5 if hs[i] == as_[i] else 0.0)
    delta = k_factor(tour[i]) * goal_multiplier(abs(hs[i] - as_[i])) * (w - we)
    ratings[homes[i]] = rh + delta; ratings[aways[i]] = ra - delta
df["dr"] = dr; df["we_home"] = we_home

def ol_probs(dr, s, theta):
    L = lambda z: 1.0 / (1.0 + np.exp(-z))
    ph, pa = L((dr - theta) / s), L((-dr - theta) / s)
    pd_ = np.clip(1 - ph - pa, 1e-9, None)
    P = np.stack([pa, pd_, ph], 1); return P / P.sum(1, keepdims=True)

def metrics(P, y):
    ll = -np.log(P[np.arange(len(y)), y] + 1e-12).mean()
    pobs = P[np.arange(len(y)), y].mean()
    cp, oh = np.cumsum(P, 1), np.zeros_like(P); oh[np.arange(len(y)), y] = 1
    r = ((cp - np.cumsum(oh, 1)) ** 2).sum(1).mean() / 2
    return ll, r, pobs

dates = df["date"].values; y = df["outcome"].values
train = dates < "2018-01-01"; test = (dates >= "2018-01-01") & (dates < "2026-06-11")

# fit ordered-logit on train
res = minimize(lambda p: (1e12 if p[0] <= 1 or p[1] < 0 else
               -np.log(ol_probs(dr[train], p[0], p[1])[np.arange(train.sum()), y[train]] + 1e-12).sum()),
               [S0, 60.0], method="Nelder-Mead")
s_fit, th_fit = res.x

# fit goals model on train (its own pipeline)
gm = GoalsModel().fit(df[train][["date", "home_score", "away_score", "neutral", "we_home"]])
def goals_probs(rows):
    out = []
    for we, ne in zip(rows["we_home"].values, rows["neutral"].values):
        pw, pdr, pl = gm.outcome_probs(we, not ne)  # home perspective
        out.append([pl, pdr, pw])  # [away, draw, home]
    return np.array(out)

print(f"recalibrated ordered-logit: s={s_fit:.1f}, theta={th_fit:.1f}\n")
print(f"{'predictor':<8}{'logloss':>9}{'RPS':>8}{'avg p(actual)':>15}")
for name, P in [("RECAL", ol_probs(dr[test], s_fit, th_fit)),
                ("BASE", ol_probs(dr[test], S0, th_fit)),
                ("GOALS", goals_probs(df[test]))]:
    ll, r, po = metrics(P, y[test])
    print(f"{name:<8}{ll:>9.4f}{r:>8.4f}{po:>14.1%}   [2018-2026 holdout, n={test.sum()}]")

# ---- the 24 actual 2026 WC group games ----
wc = (dates >= "2026-06-11") & (dates < "2026-06-20")
print(f"\n--- 2026 WC group games played, n={wc.sum()} ---")
print(f"{'predictor':<8}{'logloss':>9}{'avg p(actual)':>15}")
for name, P in [("RECAL", ol_probs(dr[wc], s_fit, th_fit)),
                ("GOALS", goals_probs(df[wc]))]:
    ll, r, po = metrics(P, y[wc])
    print(f"{name:<8}{ll:>9.4f}{po:>14.1%}")
print("(live logged avg p(actual) over first 12 was 39.4%)")
