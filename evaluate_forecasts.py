"""Score the logged daily forecasts against realized outcomes.

Run anytime; it evaluates whatever has resolved so far:
1. Match-level (model): RPS / log-loss / Brier on W-D-L for every group game
   that was forecast before being played (outputs/match_forecast_history.csv).
   The forecast used is the latest one issued strictly before the match date.
2. Advancement (model vs Polymarket): Brier score by snapshot date for
   "team reaches the Round of 32", scored per team-day against the realized
   outcome — teams' reach_r32 from outputs/history.csv vs the 'advance'
   prices in data/polymarket_history.csv. Resolves after June 27; partial
   resolution (mathematically eliminated/qualified teams) is ignored until
   the official Round-of-32 field is in the data.
3. Calibration table for the model's match forecasts.

This is the analysis backbone for the market-efficiency study (RESEARCH_DESIGN.md).
"""

import os

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
GROUP_END = "2026-06-28"


def load_results():
    df = pd.read_csv(os.path.join(BASE, "data", "results.csv"), na_values=["NA"])
    wc = df[(df["tournament"] == "FIFA World Cup") & (df["date"] >= "2026-06-11")]
    return wc.dropna(subset=["home_score", "away_score"])


def score_matches():
    path = os.path.join(BASE, "outputs", "match_forecast_history.csv")
    if not os.path.exists(path):
        print("no match forecast history yet")
        return
    fc = pd.read_csv(path)
    played = load_results()
    played = played[played["date"] < GROUP_END]

    rows = []
    for r in played.itertuples():
        f = fc[(fc["home"] == r.home_team) & (fc["away"] == r.away_team)
               & (fc["date"] < r.date)].sort_values("date")
        if f.empty:
            continue
        f = f.iloc[-1]
        p = np.array([f.p_home, f.p_draw, f.p_away])
        obs_i = 0 if r.home_score > r.away_score else (1 if r.home_score == r.away_score else 2)
        o = np.zeros(3); o[obs_i] = 1
        rps = 0.5 * ((np.cumsum(p) - np.cumsum(o))[:2] ** 2).sum()
        rows.append((r.date, r.home_team, r.away_team, f"{int(r.home_score)}-{int(r.away_score)}",
                     p[obs_i], rps, -np.log(max(p[obs_i], 1e-12)), ((p - o) ** 2).sum()))
    if not rows:
        print("no scoreable matches yet")
        return
    t = pd.DataFrame(rows, columns=["date", "home", "away", "score",
                                    "p_observed", "rps", "log_loss", "brier"])
    n = len(t)
    print(f"== Match-level model skill ({n} matches) ==")
    print(f"  RPS      {t.rps.mean():.4f}   (uniform baseline 0.2222)")
    print(f"  log-loss {t.log_loss.mean():.4f}   (uniform baseline {np.log(3):.4f})")
    print(f"  Brier    {t.brier.mean():.4f}   (uniform baseline 0.6667)")
    t.to_csv(os.path.join(BASE, "outputs", "match_scores.csv"), index=False)

    # calibration: bucket forecast probabilities vs realized frequencies
    probs, hits = [], []
    for r in played.itertuples():
        f = fc[(fc["home"] == r.home_team) & (fc["away"] == r.away_team)
               & (fc["date"] < r.date)].sort_values("date")
        if f.empty:
            continue
        f = f.iloc[-1]
        obs_i = 0 if r.home_score > r.away_score else (1 if r.home_score == r.away_score else 2)
        for i, p in enumerate([f.p_home, f.p_draw, f.p_away]):
            probs.append(p); hits.append(1.0 if i == obs_i else 0.0)
    cal = pd.DataFrame({"p": probs, "hit": hits})
    cal["bucket"] = pd.cut(cal["p"], [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1])
    print("\n== Calibration (forecast prob vs realized frequency) ==")
    g = cal.groupby("bucket", observed=True).agg(n=("hit", "size"),
                                                 forecast=("p", "mean"),
                                                 realized=("hit", "mean"))
    print(g.round(3).to_string())


def score_advancement():
    pm_path = os.path.join(BASE, "data", "polymarket_history.csv")
    hist_path = os.path.join(BASE, "outputs", "history.csv")
    if not (os.path.exists(pm_path) and os.path.exists(hist_path)):
        return
    played = load_results()
    ko = played[played["date"] >= GROUP_END]
    if len(ko) < 16:
        print("\n(advancement not yet resolved — Round of 32 field unknown)")
        return
    r32_teams = set(ko.sort_values("date").head(16)[["home_team", "away_team"]].values.ravel())

    model = pd.read_csv(hist_path)[["date", "team", "reach_r32"]]
    model["outcome"] = model["team"].isin(r32_teams).astype(float)
    model["brier"] = (model["reach_r32"] - model["outcome"]) ** 2

    pm = pd.read_csv(pm_path)
    pm = pm[pm["market"] == "advance"].copy()
    pm["date"] = pm["ts_utc"].str[:10]
    pm = pm.groupby(["date", "team"], as_index=False)["price"].mean()
    pm["outcome"] = pm["team"].isin(r32_teams).astype(float)
    pm["brier"] = (pm["price"] - pm["outcome"]) ** 2

    print("\n== Advancement Brier by forecast date (model vs Polymarket) ==")
    m = model.groupby("date")["brier"].mean().rename("model")
    p = pm.groupby("date")["brier"].mean().rename("polymarket")
    print(pd.concat([m, p], axis=1).round(4).to_string())


if __name__ == "__main__":
    score_matches()
    score_advancement()
