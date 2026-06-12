"""Fit the model, backtest on WC 2018/2022, and forecast the 2026 World Cup."""

import os
import sys

import numpy as np
import pandas as pd

from wc_model.elo import compute_elo, win_expectancy, HOME_ADV
from wc_model.goals import GoalsModel
from wc_model.market import load_market_probs, fit_market_adjustments, blend_ratings
from wc_model.tournament import GROUPS, ROUNDS, Simulator

DATA = "data/results.csv"
ODDS = "data/market_odds.csv"
MARKET_WEIGHT = 0.5
N_SIMS = int(sys.argv[1]) if len(sys.argv) > 1 else 20000


def load():
    df = pd.read_csv(DATA, na_values=["NA"])
    df["neutral"] = df["neutral"].astype(str).str.upper() == "TRUE"
    return df


def backtest(df, start, end, label):
    """Frozen pre-tournament fit, evaluated on that World Cup's matches."""
    ratings, log = compute_elo(df, as_of=start)
    gm = GoalsModel().fit(log[log["date"] < start])
    wc = df[(df["tournament"] == "FIFA World Cup") & (df["date"] >= start)
            & (df["date"] <= end)].dropna(subset=["home_score", "away_score"])

    rps_model, rps_uniform, ll_model, n = 0.0, 0.0, 0.0, 0
    for h, a, hs, as_, neu in wc[["home_team", "away_team", "home_score",
                                  "away_score", "neutral"]].itertuples(index=False):
        we = win_expectancy(ratings.get(h, 1500) - ratings.get(a, 1500)
                            + (0 if neu else HOME_ADV))
        pw, pd_, pl = gm.outcome_probs(we, not neu)
        obs = 0 if hs > as_ else (1 if hs == as_ else 2)
        o = np.zeros(3); o[obs] = 1
        p = np.array([pw, pd_, pl])
        rps_model += 0.5 * ((np.cumsum(p) - np.cumsum(o))[:2] ** 2).sum()
        u = np.array([1 / 3] * 3)
        rps_uniform += 0.5 * ((np.cumsum(u) - np.cumsum(o))[:2] ** 2).sum()
        ll_model += -np.log(max(p[obs], 1e-12))
        n += 1
    print(f"  {label}: n={n}  RPS={rps_model/n:.4f} (uniform {rps_uniform/n:.4f})  "
          f"log-loss={ll_model/n:.4f} (uniform {np.log(3):.4f})")


def main():
    df = load()
    cutoff = "2026-06-11"

    print("== Backtests (frozen pre-tournament fits) ==")
    backtest(df, "2018-06-14", "2018-07-15", "WC 2018")
    backtest(df, "2022-11-20", "2022-12-18", "WC 2022")

    print("\n== Fitting on full history to 2026-06-11 ==")
    ratings, log = compute_elo(df, as_of=cutoff)
    gm = GoalsModel().fit(log)
    print(f"  Dixon-Coles rho = {gm.rho:.4f}")
    print(f"  GLM beta = {np.round(gm.beta, 3)}")

    wc26 = df[(df["tournament"] == "FIFA World Cup") & (df["date"] >= cutoff)]
    fixtures = [(h, a, neu) for h, a, neu in
                wc26[["home_team", "away_team", "neutral"]].itertuples(index=False)]
    teams = {t for g in GROUPS.values() for t in g}
    missing = teams - set(ratings)
    fx_teams = {t for h, a, _ in fixtures for t in (h, a)}
    assert not missing, f"teams without ratings: {missing}"
    assert fx_teams == teams, f"fixture/group mismatch: {fx_teams ^ teams}"
    assert len(fixtures) == 72, len(fixtures)

    print("\n== Pre-tournament Elo (top 15) ==")
    for t in sorted(teams, key=lambda t: -ratings[t])[:15]:
        print(f"  {t:<22}{ratings[t]:7.0f}")

    # match-level predictions for all 72 group fixtures
    sim = Simulator(ratings, gm, fixtures)
    rows = []
    for h, a, neu in fixtures:
        we = win_expectancy(sim._dr(h, a, not neu))
        lam_h, lam_a = gm.expected_goals(we, not neu)
        pw, pdr, pl = gm.outcome_probs(we, not neu)
        rows.append((h, a, round(lam_h, 2), round(lam_a, 2),
                     round(pw, 3), round(pdr, 3), round(pl, 3)))
    pd.DataFrame(rows, columns=["home", "away", "xg_home", "xg_away",
                                "p_home", "p_draw", "p_away"]
                 ).to_csv("outputs/match_predictions.csv", index=False)

    def forecast(rt, label, outfile):
        print(f"\n== Simulating tournament {N_SIMS:,} times ({label}) ==")
        res = Simulator(rt, gm, fixtures).simulate(N_SIMS)
        n = res["n"]
        out = []
        for g, ts in GROUPS.items():
            for t in ts:
                r = res["reach"][t]
                out.append({"team": t, "group": g, "elo": round(rt[t]),
                            "win_group": res["positions"][t][0] / n,
                            **{f"reach_{k}": r[k] / n for k in ROUNDS[1:]}})
        tab = pd.DataFrame(out).sort_values("reach_champion", ascending=False)
        tab.to_csv(outfile, index=False)

        print(f"\n{'Team':<22}{'Grp':<5}{'Elo':<6}{'R32':>7}{'R16':>7}{'QF':>7}"
              f"{'SF':>7}{'Final':>7}{'Champ':>7}")
        for _, r in tab.head(20).iterrows():
            print(f"{r['team']:<22}{r['group']:<5}{r['elo']:<6.0f}"
                  f"{r['reach_r32']:>7.1%}{r['reach_r16']:>7.1%}{r['reach_qf']:>7.1%}"
                  f"{r['reach_sf']:>7.1%}{r['reach_final']:>7.1%}{r['reach_champion']:>7.1%}")
        return tab

    pure = forecast(ratings, "pure rating model", "outputs/team_probabilities_pure.csv")

    if os.path.exists(ODDS):
        market = load_market_probs(ODDS)
        assert set(market) == teams, f"odds/team mismatch: {set(market) ^ teams}"
        print(f"\n== Calibrating to bookmaker consensus (inverse simulation) ==")
        delta = fit_market_adjustments(
            lambda rt: Simulator(rt, gm, fixtures), ratings, market, sims=20000)
        pd.DataFrame(sorted(delta.items()), columns=["team", "delta_elo"]
                     ).to_csv("outputs/market_deltas.csv", index=False)
        blended_ratings = blend_ratings(ratings, delta, MARKET_WEIGHT)
        tab = forecast(blended_ratings,
                       f"blended, market weight {MARKET_WEIGHT}",
                       "outputs/team_probabilities.csv")

        cmp_ = pure[["team", "reach_champion"]].rename(
            columns={"reach_champion": "p_pure"}).merge(
            tab[["team", "reach_champion"]].rename(columns={"reach_champion": "p_blend"}),
            on="team")
        cmp_["p_market"] = cmp_["team"].map(market)
        cmp_["delta_elo"] = cmp_["team"].map(delta).round(0)
        cmp_ = cmp_.sort_values("p_blend", ascending=False)
        cmp_.to_csv("outputs/market_comparison.csv", index=False)
        print(f"\n{'Team':<22}{'pure':>8}{'market':>8}{'blend':>8}{'dElo':>7}")
        for _, r in cmp_.head(12).iterrows():
            print(f"{r['team']:<22}{r['p_pure']:>8.1%}{r['p_market']:>8.1%}"
                  f"{r['p_blend']:>8.1%}{r['delta_elo']:>7.0f}")
    else:
        pure.to_csv("outputs/team_probabilities.csv", index=False)
        print(f"\n(no {ODDS} found — headline forecast is the pure rating model)")


if __name__ == "__main__":
    main()
