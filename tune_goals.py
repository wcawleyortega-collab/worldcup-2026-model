"""A/B the goals-model fitting policy on frozen pre-tournament backtests.

Baseline = current shipped fit (uniform weights, matches since 2010).
Variants = Dixon-Coles exponential time decay (wider window since 1994, several
half-lives). For each policy we refit the FULL pipeline strictly before each
tournament and score that tournament's matches out-of-sample (RPS / log-loss /
avg p(actual)). Keep a change only if it beats the baseline across tournaments.
"""
import numpy as np
import pandas as pd

from wc_model.elo import compute_elo, win_expectancy, HOME_ADV
from wc_model.goals import GoalsModel

df = pd.read_csv("data/results.csv", na_values=["NA"])
df["neutral"] = df["neutral"].astype(str).str.upper() == "TRUE"

TOURNAMENTS = [
    ("WC2018", "2018-06-14", "2018-07-15"),
    ("WC2022", "2022-11-20", "2022-12-18"),
    ("WC2026", "2026-06-11", "2026-07-20"),
]

POLICIES = [
    ("baseline 2010/uniform", dict(since="2010-01-01", half_life=None)),
    ("decay hl=4y",  dict(since="1994-01-01", half_life=4)),
    ("decay hl=6y",  dict(since="1994-01-01", half_life=6)),
    ("decay hl=8y",  dict(since="1994-01-01", half_life=8)),
    ("decay hl=10y", dict(since="1994-01-01", half_life=10)),
    ("decay hl=12y", dict(since="1994-01-01", half_life=12)),
]


def score(ratings, gm, start, end):
    wc = df[(df["tournament"] == "FIFA World Cup") & (df["date"] >= start)
            & (df["date"] <= end)].dropna(subset=["home_score", "away_score"])
    rps = ll = pa = n = 0
    for h, a, hs, as_, neu in wc[["home_team", "away_team", "home_score",
                                  "away_score", "neutral"]].itertuples(index=False):
        we = win_expectancy(ratings.get(h, 1500) - ratings.get(a, 1500)
                            + (0 if neu else HOME_ADV))
        p = np.array(gm.outcome_probs(we, not neu))
        obs = 0 if hs > as_ else (1 if hs == as_ else 2)
        o = np.zeros(3); o[obs] = 1
        rps += 0.5 * ((np.cumsum(p) - np.cumsum(o))[:2] ** 2).sum()
        ll += -np.log(max(p[obs], 1e-12)); pa += p[obs]; n += 1
    return rps / n, ll / n, pa / n, n


print(f"{'policy':<22}" + "".join(f"{t[0]:>22}" for t in TOURNAMENTS) + f"{'MEAN RPS':>12}")
for name, kw in POLICIES:
    cells, rps_all = [], []
    for _, start, end in TOURNAMENTS:
        ratings, log = compute_elo(df, as_of=start)
        gm = GoalsModel().fit(log[log["date"] < start], **kw)
        rps, ll, pa, n = score(ratings, gm, start, end)
        cells.append(f"{rps:.4f}/{ll:.3f}/{pa:.0%}")
        rps_all.append(rps)
    print(f"{name:<22}" + "".join(f"{c:>22}" for c in cells)
          + f"{np.mean(rps_all):>12.4f}")
print("\ncell = RPS / log-loss / avg p(actual);  lower RPS & log-loss = better")
