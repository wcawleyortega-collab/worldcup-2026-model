"""World Football Elo ratings (eloratings.net formulation).

R_new = R_old + K * G * (W - W_e)
  W_e = 1 / (1 + 10 ** (-dr / 400)),  dr = R_home - R_away + HA (HA=100 if not neutral)
  K   = 60 WC finals / 50 continental finals / 40 qualifiers & Nations League
        / 30 other tournaments / 20 friendlies
  G   = 1 (margin<=1), 1.5 (=2), (11+N)/8 (N>=3)
"""

import pandas as pd

HOME_ADV = 100.0
INITIAL_RATING = 1500.0

K_WORLD_CUP = 60
K_CONTINENTAL = 50
K_QUALIFIER = 40
K_OTHER = 30
K_FRIENDLY = 20

CONTINENTAL_FINALS = {
    "UEFA Euro", "Copa América", "African Cup of Nations", "AFC Asian Cup",
    "CONCACAF Championship", "Gold Cup", "Oceania Nations Cup",
    "Confederations Cup", "FIFA Confederations Cup",
}


def k_factor(tournament: str) -> float:
    t = tournament
    if t == "FIFA World Cup":
        return K_WORLD_CUP
    if t in CONTINENTAL_FINALS:
        return K_CONTINENTAL
    if "qualification" in t or "Nations League" in t:
        return K_QUALIFIER
    if t == "Friendly":
        return K_FRIENDLY
    return K_OTHER


def goal_multiplier(margin: int) -> float:
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return (11 + margin) / 8


def win_expectancy(dr: float) -> float:
    return 1.0 / (1.0 + 10 ** (-dr / 400.0))


def compute_elo(matches: pd.DataFrame, as_of: str | None = None) -> tuple[dict, pd.DataFrame]:
    """Run Elo over completed matches (sorted by date). Returns (ratings, per-match log).

    The per-match log carries each side's pre-match rating and win expectancy,
    which the goals model fits against.
    """
    df = matches.dropna(subset=["home_score", "away_score"]).sort_values("date")
    if as_of is not None:
        df = df[df["date"] < as_of]

    ratings: dict[str, float] = {}
    rows = []
    for date, home, away, hs, as_, tournament, neutral in df[
        ["date", "home_team", "away_team", "home_score", "away_score", "tournament", "neutral"]
    ].itertuples(index=False):
        rh = ratings.get(home, INITIAL_RATING)
        ra = ratings.get(away, INITIAL_RATING)
        ha = 0.0 if neutral else HOME_ADV
        we_home = win_expectancy(rh - ra + ha)

        hs, as_ = int(hs), int(as_)
        w = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        delta = k_factor(tournament) * goal_multiplier(abs(hs - as_)) * (w - we_home)
        ratings[home] = rh + delta
        ratings[away] = ra - delta

        rows.append((date, home, away, hs, as_, neutral, rh, ra, we_home))

    log = pd.DataFrame(
        rows,
        columns=["date", "home_team", "away_team", "home_score", "away_score",
                 "neutral", "elo_home_pre", "elo_away_pre", "we_home"],
    )
    return ratings, log
