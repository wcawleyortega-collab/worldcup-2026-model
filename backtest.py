"""Walk-forward backtest of the Elo->W/D/L calibration.

Diagnosis to test: the live model is under-confident on favourites (avg 39.4%
on actual outcomes over the first 12 WC games). The two direct levers are home
advantage (HA) and the logistic temperature (scale s). We recompute Elo over all
history for each HA, then fit an ordered-logistic W/D/L map P(H/D/A | dr) on a
training period and score it out-of-sample by log-loss and RPS.

Ordered model (symmetric draw band):
    P(home) = L((dr - theta)/s)
    P(away) = L((-dr - theta)/s)
    P(draw) = 1 - P(home) - P(away)
s = temperature (smaller -> sharper favourites); theta = draw-band half width.
The CURRENT model's home/away split is a /400 base-10 logistic, i.e. natural
scale s0 = 400/ln(10) = 173.7 with no temperature tuning -> that's the baseline.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from wc_model.elo import k_factor, goal_multiplier, INITIAL_RATING

S0 = 400.0 / np.log(10)  # 173.7: the current model's implied logistic scale

df = pd.read_csv("data/results.csv", na_values=["NA"])
df = df.dropna(subset=["home_score", "away_score"]).copy()
df["neutral"] = df["neutral"].astype(str).str.upper() == "TRUE"
df = df.sort_values("date").reset_index(drop=True)
df["home_score"] = df["home_score"].astype(int)
df["away_score"] = df["away_score"].astype(int)
# outcome: 2=home win, 1=draw, 0=away win
df["outcome"] = np.sign(df["home_score"] - df["away_score"]).astype(int) + 1
df["competitive"] = df["tournament"] != "Friendly"


def run_elo(ha):
    """Walk forward, return dr (pre-match rating diff incl. HA) per match."""
    ratings = {}
    dr = np.empty(len(df))
    homes = df["home_team"].values
    aways = df["away_team"].values
    hs = df["home_score"].values
    as_ = df["away_score"].values
    neu = df["neutral"].values
    tour = df["tournament"].values
    for i in range(len(df)):
        rh = ratings.get(homes[i], INITIAL_RATING)
        ra = ratings.get(aways[i], INITIAL_RATING)
        h = 0.0 if neu[i] else ha
        d = rh - ra + h
        dr[i] = d
        we = 1.0 / (1.0 + 10 ** (-d / 400.0))
        w = 1.0 if hs[i] > as_[i] else (0.5 if hs[i] == as_[i] else 0.0)
        delta = k_factor(tour[i]) * goal_multiplier(abs(hs[i] - as_[i])) * (w - we)
        ratings[homes[i]] = rh + delta
        ratings[aways[i]] = ra - delta
    return dr


def probs(dr, s, theta):
    L = lambda z: 1.0 / (1.0 + np.exp(-z))
    ph = L((dr - theta) / s)
    pa = L((-dr - theta) / s)
    pd_ = np.clip(1 - ph - pa, 1e-9, None)
    P = np.stack([pa, pd_, ph], axis=1)
    return P / P.sum(axis=1, keepdims=True)


def nll(params, dr, y):
    s, theta = params
    if s <= 1 or theta < 0:
        return 1e12
    P = probs(dr, s, theta)
    return -np.log(P[np.arange(len(y)), y] + 1e-12).sum()


def log_loss(P, y):
    return -np.log(P[np.arange(len(y)), y] + 1e-12).mean()


def rps(P, y):
    # ranked probability score for ordered 3-outcome
    cum_p = np.cumsum(P, axis=1)
    oh = np.zeros_like(P)
    oh[np.arange(len(y)), y] = 1
    cum_o = np.cumsum(oh, axis=1)
    return ((cum_p - cum_o) ** 2).sum(axis=1).mean() / 2


TRAIN_END = "2018-01-01"
TEST_END = "2026-06-11"  # hold out the live 2026 WC entirely
dates = df["date"].values
train_mask = dates < TRAIN_END
test_mask = (dates >= TRAIN_END) & (dates < TEST_END)
comp = df["competitive"].values
y = df["outcome"].values

print(f"train: {train_mask.sum()} matches (<{TRAIN_END}), "
      f"test: {test_mask.sum()} ({TRAIN_END}..{TEST_END})")
print(f"test competitive-only: {(test_mask & comp).sum()}\n")
print(f"{'HA':>4} {'s_fit':>7} {'theta':>7} | {'test logloss':>12} {'test RPS':>9} "
      f"| {'comp logloss':>12} {'comp RPS':>9}")

results = []
for ha in [0, 40, 60, 80, 100, 120, 140]:
    dr = run_elo(ha)
    # fit on train (all matches), report on test (all) and test (competitive)
    res = minimize(nll, [S0, 60.0], args=(dr[train_mask], y[train_mask]),
                   method="Nelder-Mead")
    s, theta = res.x
    Pt = probs(dr[test_mask], s, theta)
    Pc = probs(dr[test_mask & comp], s, theta)
    ll_t, rps_t = log_loss(Pt, y[test_mask]), rps(Pt, y[test_mask])
    ll_c, rps_c = log_loss(Pc, y[test_mask & comp]), rps(Pc, y[test_mask & comp])
    results.append((ha, s, theta, ll_t, rps_t, ll_c, rps_c))
    print(f"{ha:>4} {s:>7.1f} {theta:>7.1f} | {ll_t:>12.4f} {rps_t:>9.4f} "
          f"| {ll_c:>12.4f} {rps_c:>9.4f}")

# baseline = current model's fixed scale s0, theta free, at HA=100
dr100 = run_elo(100)
resb = minimize(lambda th: nll([S0, th[0]], dr100[train_mask], y[train_mask]),
                [60.0], method="Nelder-Mead")
thb = resb.x[0]
Pb = probs(dr100[test_mask], S0, thb)
Pbc = probs(dr100[test_mask & comp], S0, thb)
print(f"\nBASELINE (current scale s0={S0:.1f}, HA=100, theta={thb:.1f}):")
print(f"  test logloss {log_loss(Pb, y[test_mask]):.4f}  RPS {rps(Pb, y[test_mask]):.4f} "
      f"| comp logloss {log_loss(Pbc, y[test_mask & comp]):.4f}  "
      f"RPS {rps(Pbc, y[test_mask & comp]):.4f}")

best = min(results, key=lambda r: r[5])  # by competitive log-loss
print(f"\nBEST by competitive log-loss: HA={best[0]}, s={best[1]:.1f}, theta={best[2]:.1f}")
print(f"  -> s/s0 ratio = {best[1]/S0:.3f}  ({'sharper' if best[1] < S0 else 'flatter'} than current)")
