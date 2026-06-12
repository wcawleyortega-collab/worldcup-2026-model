"""Bookmaker consensus layer (Leitner-Zeileis-Hornik).

1. Strip the overround from outright tournament-winner odds proportionally:
   p_i = (1/o_i) / sum_j (1/o_j).
2. Invert the tournament: find per-team Elo adjustments delta_i such that
   simulating the full tournament with R_i + delta_i reproduces the market's
   championship probabilities. (Zeileis et al. do this with Bradley-Terry
   abilities; on the Elo scale the same fixed-point iteration applies, since
   championship probability is monotone in a team's rating.)
3. Blend: R_blend = R_elo + w * delta, with market weight w. At w=1 the
   tournament forecast matches the market; at w=0 it is the pure rating model.
"""

import numpy as np
import pandas as pd


def load_market_probs(path: str) -> dict[str, float]:
    df = pd.read_csv(path)
    inv = 1.0 / df["decimal_odds"].astype(float)
    probs = inv / inv.sum()  # proportional overround removal + normalization
    return dict(zip(df["team"], probs))


def fit_market_adjustments(make_simulator, ratings: dict, market: dict[str, float],
                           iters: int = 12, sims: int = 20000,
                           lr: float = 70.0, verbose: bool = True) -> dict[str, float]:
    """Fixed-point iteration: delta_i += lr * log(p_market / p_model), damped.

    make_simulator(adjusted_ratings) must return a Simulator. Champion
    probabilities are floored at half a count to keep the log stable for
    longshots; total adjustment is capped at +-400 Elo.
    """
    teams = list(market)
    delta = dict.fromkeys(teams, 0.0)
    floor = 0.5 / sims
    for it in range(iters):
        adj = dict(ratings)
        for t in teams:
            adj[t] = adj.get(t, 1500.0) + delta[t]
        sim = make_simulator(adj)
        res = sim.simulate(sims)
        q = {t: max(res["reach"][t]["champion"] / sims, floor) for t in teams}
        eta = lr / (1 + 0.25 * it)
        err = 0.0
        for t in teams:
            p = max(market[t], floor)
            delta[t] = float(np.clip(delta[t] + eta * np.log(p / q[t]), -400, 400))
            err += abs(p - q[t])
        if verbose:
            print(f"  iter {it + 1:2d}: sum|p_mkt - p_model| = {err:.4f}, "
                  f"max|delta| = {max(abs(d) for d in delta.values()):.0f}")
        if err < 0.02:
            break
    return delta


def blend_ratings(ratings: dict, delta: dict[str, float], weight: float) -> dict:
    out = dict(ratings)
    for t, d in delta.items():
        out[t] = out.get(t, 1500.0) + weight * d
    return out
