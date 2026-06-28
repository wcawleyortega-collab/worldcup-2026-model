"""Squad market-value covariate.

The literature (Peeters 2018; Gerhards & Mutz) finds aggregate squad market value
is among the strongest single predictors of international results. This module
loads a Transfermarkt squad-value snapshot (``data/squad_values.csv``) and maps it
onto the Elo scale so it can be *tested against* the rating model — does it carry
information Elo does not already have?

Value enters as log(value): football strength is multiplicative, and the marginal
Elo gain from a €50m squad bump is far larger for Qatar than for France.
"""

import numpy as np
import pandas as pd


def load_values(path: str = "data/squad_values.csv") -> dict[str, float]:
    df = pd.read_csv(path)
    return dict(zip(df["team"], df["squad_value_eur_m"].astype(float)))


def fit_value_to_elo(ratings: dict[str, float], values: dict[str, float]):
    """Cross-sectional OLS of Elo on log(squad value) over the teams in both dicts.

    Returns (predict, stats) where predict(value)->Elo-scale strength and stats
    carries the slope, intercept and R^2. A high R^2 means squad value and Elo are
    largely the *same* signal (redundant); the residual is the only place value
    could add to the rating model.
    """
    teams = [t for t in values if t in ratings]
    x = np.log(np.array([values[t] for t in teams]))
    y = np.array([ratings[t] for t in teams])
    slope, intercept = np.polyfit(x, y, 1)
    pred = intercept + slope * x
    ss_res = ((y - pred) ** 2).sum()
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot
    stats = {"slope": float(slope), "intercept": float(intercept),
             "r2": float(r2), "n": len(teams)}
    return (lambda v: intercept + slope * np.log(v)), stats


def blended_ratings(ratings: dict[str, float], values: dict[str, float],
                    alpha: float) -> dict[str, float]:
    """R = alpha * Elo + (1-alpha) * (value-implied Elo).

    alpha=1 -> pure Elo (current model); alpha<1 mixes in the squad-value prior on
    the same scale. Teams with no value fall back to pure Elo.
    """
    predict, _ = fit_value_to_elo(ratings, values)
    out = {}
    for t, r in ratings.items():
        if t in values:
            out[t] = alpha * r + (1 - alpha) * predict(values[t])
        else:
            out[t] = r
    return out
