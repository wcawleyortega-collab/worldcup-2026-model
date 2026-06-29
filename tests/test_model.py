"""Unit tests for the core forecasting math.

Hermetic: every test builds its own synthetic inputs (no dependence on the live
data CSVs), so the suite runs fast and deterministically in CI. Run from the
repo root with:  python -m pytest
"""

import math

import numpy as np
import pandas as pd
import pytest

from wc_model.elo import (HOME_ADV, INITIAL_RATING, compute_elo, goal_multiplier,
                          k_factor, win_expectancy)
from wc_model.goals import GoalsModel
from wc_model.market import blend_ratings, load_market_probs
from wc_model.squad import blended_ratings, fit_value_to_elo, load_values


# --------------------------------------------------------------------- Elo
def test_win_expectancy_even_match():
    assert win_expectancy(0.0) == pytest.approx(0.5)


def test_win_expectancy_symmetric():
    for dr in (50.0, 100.0, 250.0, -75.0):
        assert win_expectancy(dr) + win_expectancy(-dr) == pytest.approx(1.0)


def test_win_expectancy_monotone():
    assert win_expectancy(200) > win_expectancy(100) > win_expectancy(0)


def test_k_factor_mapping():
    assert k_factor("FIFA World Cup") == 60
    assert k_factor("UEFA Euro") == 50
    assert k_factor("FIFA World Cup qualification") == 40
    assert k_factor("UEFA Nations League") == 40
    assert k_factor("Friendly") == 20
    assert k_factor("Some Regional Cup") == 30


def test_goal_multiplier():
    assert goal_multiplier(0) == 1.0
    assert goal_multiplier(1) == 1.0
    assert goal_multiplier(2) == 1.5
    assert goal_multiplier(4) == pytest.approx((11 + 4) / 8)


def _matches():
    rows = [
        ("2011-01-01", "A", "B", 2, 1, "Friendly", False),
        ("2011-02-01", "B", "C", 0, 0, "Friendly", True),
        ("2011-03-01", "A", "C", 3, 0, "FIFA World Cup", True),
    ]
    return pd.DataFrame(rows, columns=["date", "home_team", "away_team",
                                       "home_score", "away_score", "tournament", "neutral"])


def test_compute_elo_is_zero_sum():
    ratings, log = compute_elo(_matches())
    # Every update moves the same delta between two teams, so total points are
    # conserved at INITIAL_RATING per team that has appeared.
    assert sum(ratings.values()) == pytest.approx(INITIAL_RATING * len(ratings))
    assert ((log["we_home"] > 0) & (log["we_home"] < 1)).all()


def test_compute_elo_winner_gains():
    ratings, _ = compute_elo(_matches())
    assert ratings["A"] > INITIAL_RATING  # A won both its games


def test_compute_elo_as_of_filters_future():
    _, log = compute_elo(_matches(), as_of="2011-02-15")
    assert len(log) == 2


def test_home_advantage_constant_is_used():
    assert HOME_ADV == 100.0  # the calibrated value the model ships with


# ------------------------------------------------------------------- goals
def _gm(rho=-0.05):
    gm = GoalsModel()
    gm.beta = np.array([math.log(1.4), 0.8, 0.0, 0.0, 0.15])
    gm.rho = rho
    return gm


def test_score_matrix_is_a_distribution():
    m = _gm().score_matrix(1.6, 1.1)
    assert m.sum() == pytest.approx(1.0)
    assert (m >= 0).all()


def test_outcome_probs_sum_to_one():
    p = _gm().outcome_probs(0.6, a_at_home=True)
    assert sum(p) == pytest.approx(1.0)
    assert all(0.0 <= x <= 1.0 for x in p)


def test_stronger_team_scores_more():
    gm = _gm()
    assert gm.expected_goals(0.7)[0] > gm.expected_goals(0.3)[0] > 0


def test_fit_produces_finite_coefficients():
    rng = np.random.default_rng(0)
    teams = list("ABCDEFGH")
    strength = {t: i for i, t in enumerate(teams)}
    dates = pd.date_range("2012-01-01", periods=400, freq="3D").astype(str)
    rows = []
    for d in dates:
        h, a = rng.choice(teams, size=2, replace=False)
        lam_h = math.exp(0.2 + 0.15 * (strength[h] - strength[a]) / 2 + 0.1)
        lam_a = math.exp(0.2 + 0.15 * (strength[a] - strength[h]) / 2)
        rows.append((d, h, a, int(rng.poisson(lam_h)), int(rng.poisson(lam_a)),
                     "Friendly", False))
    matches = pd.DataFrame(rows, columns=["date", "home_team", "away_team",
                                          "home_score", "away_score", "tournament", "neutral"])
    _, log = compute_elo(matches)
    gm = GoalsModel().fit(log, since="2010-01-01")
    assert np.all(np.isfinite(gm.beta))
    assert -0.3 <= gm.rho <= 0.3
    assert sum(gm.outcome_probs(0.65)) == pytest.approx(1.0)


# ------------------------------------------------------------------ market
def test_load_market_probs_strips_overround(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("team,decimal_odds\nA,2.0\nB,4.0\nC,4.0\n")
    probs = load_market_probs(str(p))
    assert sum(probs.values()) == pytest.approx(1.0)
    # proportional removal preserves the inverse-odds ratio (A is twice as likely as B)
    assert probs["A"] == pytest.approx(2 * probs["B"])


def test_blend_ratings_weight_zero_is_identity():
    base = {"A": 1800.0, "B": 1500.0}
    delta = {"A": 50.0, "B": -30.0}
    assert blend_ratings(base, delta, 0.0) == base


def test_blend_ratings_applies_weighted_delta():
    out = blend_ratings({"A": 1800.0}, {"A": 50.0}, 0.5)
    assert out["A"] == pytest.approx(1825.0)


# ------------------------------------------------------------------- squad
def test_fit_value_to_elo_recovers_perfect_line():
    values = {"A": 100.0, "B": 200.0, "C": 400.0, "D": 800.0}
    slope, intercept = 50.0, 1000.0
    ratings = {t: intercept + slope * math.log(v) for t, v in values.items()}
    predict, stats = fit_value_to_elo(ratings, values)
    assert stats["r2"] == pytest.approx(1.0)
    assert stats["n"] == 4
    assert predict(100.0) == pytest.approx(ratings["A"])


def test_blended_ratings_alpha_endpoints():
    values = {"A": 100.0, "B": 800.0}
    ratings = {"A": 1500.0, "B": 1900.0}
    assert blended_ratings(ratings, values, 1.0) == ratings  # pure Elo
    predict, _ = fit_value_to_elo(ratings, values)
    assert blended_ratings(ratings, values, 0.0)["A"] == pytest.approx(predict(100.0))


def test_blended_ratings_falls_back_without_value():
    ratings = {"A": 1500.0, "B": 1900.0, "Z": 1234.0}
    out = blended_ratings(ratings, {"A": 100.0, "B": 800.0}, 0.3)
    assert out["Z"] == 1234.0


def test_load_values(tmp_path):
    p = tmp_path / "v.csv"
    p.write_text("team,squad_value_eur_m\nFrance,1200\nQatar,40\n")
    assert load_values(str(p)) == {"France": 1200.0, "Qatar": 40.0}
