"""Does squad market value improve the model beyond Elo? An out-of-sample test
validated across THREE World Cups (2018, 2022, 2026).

For each tournament the squad values are the *period-correct* Transfermarkt
snapshot (2018 / 2022 / 2026 — applying one year's values to another would be
anachronistic), Elo is frozen *before* the tournament, and the goal model is fit
strictly on pre-tournament data — the same out-of-sample protocol as tune_goals.py.

Three checks per tournament:
  1. Redundancy    — cross-sectional R^2 of Elo on log(squad value).
  2. Residual info — Pearson r of Elo-residual vs value gap, with p-value.
  3. Prediction    — blend the value-implied rating into Elo at weight (1-alpha)
                     and score W/D/L RPS. alpha=1 is pure Elo (current model). A
                     real, complementary signal shows an *interior* optimum that
                     replicates across tournaments; over-fit noise would not.
"""
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

from wc_model.elo import compute_elo, win_expectancy, HOME_ADV
from wc_model.goals import GoalsModel
from wc_model.squad import load_values, fit_value_to_elo, blended_ratings

TOURNAMENTS = [
    ("WC2018", "2018-06-14", "2018-07-15", "data/squad_values_2018.csv"),
    ("WC2022", "2022-11-20", "2022-12-18", "data/squad_values_2022.csv"),
    ("WC2026", "2026-06-11", "2026-06-28", "data/squad_values.csv"),
]
ALPHAS = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0]
# 2018 bottom-table squads whose euro value is approximate (see CSV source notes);
# used for a robustness check that the verdict doesn't ride on them.
APPROX_2018 = {"Peru", "Australia", "Costa Rica", "Tunisia", "Saudi Arabia", "Iran", "Panama"}

df = pd.read_csv("data/results.csv", na_values=["NA"])
df["neutral"] = df["neutral"].astype(str).str.upper() == "TRUE"


def matches(start, end):
    return df[(df["tournament"] == "FIFA World Cup") & (df["date"] >= start)
              & (df["date"] <= end)].dropna(subset=["home_score", "away_score"])


def rps_of(ratings, gm, wc, values, exclude=frozenset()):
    rps = n = 0
    for h, a, hs, as_, neu in wc[["home_team", "away_team", "home_score",
                                  "away_score", "neutral"]].itertuples(index=False):
        if h not in values or a not in values or h in exclude or a in exclude:
            continue
        we = win_expectancy(ratings.get(h, 1500) - ratings.get(a, 1500) + (0 if neu else HOME_ADV))
        p = np.array(gm.outcome_probs(we, not neu))
        obs = 0 if hs > as_ else (1 if hs == as_ else 2)
        o = np.zeros(3); o[obs] = 1
        rps += 0.5 * ((np.cumsum(p) - np.cumsum(o))[:2] ** 2).sum(); n += 1
    return (rps / n if n else float("nan")), n


def evaluate(start, end, vpath):
    ratings, log = compute_elo(df, as_of=start)
    gm = GoalsModel().fit(log[log["date"] < start])
    values = load_values(vpath)
    wc = matches(start, end)

    _, st = fit_value_to_elo(ratings, values)

    resid, vgap = [], []
    for h, a, hs, as_, neu in wc[["home_team", "away_team", "home_score",
                                  "away_score", "neutral"]].itertuples(index=False):
        if h not in values or a not in values:
            continue
        we = win_expectancy(ratings.get(h, 1500) - ratings.get(a, 1500) + (0 if neu else HOME_ADV))
        p = np.array(gm.outcome_probs(we, not neu))
        exp = p[0] - p[2]
        act = 1.0 if hs > as_ else (0.0 if hs == as_ else -1.0)
        resid.append(act - exp); vgap.append(np.log(values[h]) - np.log(values[a]))
    r, pv = pearsonr(vgap, resid)

    sweep = {}
    for al in ALPHAS:
        rt = ratings if al == 1.0 else blended_ratings(ratings, values, al)
        sweep[al], n = rps_of(rt, gm, wc, values)
    return {"r2": st["r2"], "corr": r, "p": pv, "sweep": sweep, "n": n,
            "ratings": ratings, "gm": gm, "values": values, "wc": wc}


print("Out-of-sample squad-value test, frozen pre-tournament (Elo + goal fit):\n")
results = {name: evaluate(s, e, p) for name, s, e, p in TOURNAMENTS}

print("[1] Redundancy & residual signal")
print(f"    {'tournament':<10}{'games':>6}{'R2(Elo~logval)':>16}{'corr(resid,gap)':>17}{'p':>7}")
for name in results:
    r = results[name]
    print(f"    {name:<10}{r['n']:>6}{r['r2']:>16.2f}{r['corr']:>17.3f}{r['p']:>7.3f}")

print("\n[2] Prediction — W/D/L RPS by Elo/value mix (alpha = Elo weight)")
hdr = "".join(f"{n:>9}" for n in results) + f"{'MEAN':>9}"
print(f"    {'alpha':<7}{hdr}")
for al in ALPHAS:
    row = [results[n]["sweep"][al] for n in results]
    tag = "  <- pure Elo" if al == 1.0 else ""
    print(f"    {al:<7.1f}" + "".join(f"{v:>9.4f}" for v in row)
          + f"{np.mean(row):>9.4f}{tag}")

print("\n[3] Best mix per tournament (lower RPS = better)")
for name in results:
    sw = results[name]["sweep"]
    best = min(sw, key=sw.get)
    gain = (sw[1.0] - sw[best]) / sw[1.0] * 100
    interior = "interior" if 0.0 < best < 1.0 else "boundary"
    print(f"    {name}:  pure Elo {sw[1.0]:.4f}  ->  best {sw[best]:.4f} at alpha={best:.1f} "
          f"({gain:+.1f}%, {interior} optimum)")

# Robustness: re-score WC2018 dropping games that involve an approximate-value team.
r18 = results["WC2018"]
sweep_firm = {}
for al in ALPHAS:
    rt = r18["ratings"] if al == 1.0 else blended_ratings(r18["ratings"], r18["values"], al)
    sweep_firm[al], n_firm = rps_of(rt, r18["gm"], r18["wc"], r18["values"], exclude=APPROX_2018)
best_firm = min(sweep_firm, key=sweep_firm.get)
print(f"\n[4] Robustness — WC2018 using only firmly-sourced squads "
      f"(drop {len(APPROX_2018)} approx teams, {n_firm} games):")
print(f"    pure Elo {sweep_firm[1.0]:.4f}  ->  best {sweep_firm[best_firm]:.4f} at "
      f"alpha={best_firm:.1f}  (verdict unchanged if still an interior gain).")
