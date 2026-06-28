"""Daily in-tournament update: pull fresh results, condition the forecast on
everything played so far, and refresh outputs.

- Elo ratings are recomputed through the latest completed matches (so World Cup
  results move ratings with K=60, as eloratings.net does).
- Completed group games are held fixed in every simulation; completed knockout
  games fix the winner (penalty shootouts resolved via shootouts.csv).
- Once the real round-of-32 pairings exist in the data, the actual third-place
  slotting overrides the model's constraint-matching allocation.
- The pre-tournament bookmaker deltas (outputs/market_deltas.csv) keep being
  applied at MARKET_WEIGHT; in-tournament odds react to results we already
  condition on, so the prior is not re-fit.

Run: .venv/bin/python update_predictions.py [n_sims]
"""

import datetime
import os
import subprocess
import sys

import pandas as pd

from wc_model.elo import compute_elo
from wc_model.goals import GoalsModel
from wc_model.market import blend_ratings
from wc_model.tournament import GROUPS, R32, ROUNDS, Simulator

BASE = os.path.dirname(os.path.abspath(__file__))
RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
SHOOTOUTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/shootouts.csv"
WC_START, GROUP_END, WC_END = "2026-06-11", "2026-06-28", "2026-07-20"
MARKET_WEIGHT = 0.5
N_SIMS = int(sys.argv[1]) if len(sys.argv) > 1 else 50000


def refresh_data():
    """Fetch latest results/shootouts. A failed fetch is non-fatal: keep the
    cached copy and warn, so one transient curl timeout can't stall the
    pipeline for days (as it did June 13-15, exit 28)."""
    for url, name in [(RESULTS_URL, "results.csv"), (SHOOTOUTS_URL, "shootouts.csv")]:
        dest = os.path.join(BASE, "data", name)
        tmp = dest + ".tmp"
        try:
            subprocess.run(
                ["curl", "-sL", "--fail", "--connect-timeout", "20",
                 "--max-time", "90", "--retry", "3", "--retry-delay", "5",
                 "-o", tmp, url],
                check=True, timeout=300)
            os.replace(tmp, dest)  # atomic; only overwrite cache on success
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            print(f"WARN: fetch of {name} failed ({e}); using cached copy", flush=True)


def knockout_winners(ko: pd.DataFrame) -> dict:
    """{frozenset({a, b}): winner} for completed knockout matches."""
    try:
        so = pd.read_csv(os.path.join(BASE, "data", "shootouts.csv"))
        shootout = {(r.date, r.home_team, r.away_team): r.winner for r in so.itertuples()}
    except FileNotFoundError:
        shootout = {}
    out = {}
    for r in ko.dropna(subset=["home_score", "away_score"]).itertuples():
        if r.home_score > r.away_score:
            out[frozenset((r.home_team, r.away_team))] = r.home_team
        elif r.home_score < r.away_score:
            out[frozenset((r.home_team, r.away_team))] = r.away_team
        else:  # decided on penalties (dataset records the 90'/120' score)
            w = shootout.get((r.date, r.home_team, r.away_team))
            if w:
                out[frozenset((r.home_team, r.away_team))] = w
    return out


def real_third_allocation(group_played: dict, fixtures, ko: pd.DataFrame, sim) -> dict | None:
    """Derive the actual third-place slotting once FIFA's R32 pairings are known."""
    if len(group_played) < len(fixtures) or len(ko) < 16:
        return None
    r32_real = ko.sort_values("date").head(16)
    opponents = {}
    for r in r32_real.itertuples():
        opponents[r.home_team] = r.away_team
        opponents[r.away_team] = r.home_team
    # real group standings (all games played -> deterministic up to fair-play ties)
    res = sim.simulate(1, played=group_played)
    winners = {g: max(ts, key=lambda t: res["positions"][t][0]) for g, ts in GROUPS.items()}
    alloc = {}
    for m, (s1, s2) in R32.items():
        if s2[0] == "3":
            w = winners[s1[1]]
            opp = opponents.get(w)
            if opp is None or opp not in sim.team_group:
                return None
            alloc[m] = sim.team_group[opp]
    return alloc


def main():
    today = datetime.date.today().isoformat()
    if today > WC_END:
        print(f"{today}: tournament over — nothing to update. "
              "Remove the LaunchAgent: launchctl bootout gui/$(id -u)/com.worldcup.predictions")
        return
    print(f"=== Update {today} ===")
    refresh_data()
    try:
        import log_polymarket
        log_polymarket.main()
    except Exception as e:  # market snapshot is best-effort; never block the forecast
        print(f"  warn: polymarket snapshot failed: {e}")

    df = pd.read_csv(os.path.join(BASE, "data", "results.csv"), na_values=["NA"])
    df["neutral"] = df["neutral"].astype(str).str.upper() == "TRUE"

    ratings, log = compute_elo(df)  # through all completed matches
    gm = GoalsModel().fit(log)

    wc = df[(df["tournament"] == "FIFA World Cup") & (df["date"] >= WC_START)
            & (df["date"] <= WC_END)]
    group = wc[wc["date"] < GROUP_END]
    ko = wc[wc["date"] >= GROUP_END]

    fixtures = [(h, a, neu) for h, a, neu in
                group[["home_team", "away_team", "neutral"]].itertuples(index=False)]
    fixture_date = {(r.home_team, r.away_team): str(r.date) for r in group.itertuples()}
    played = {(r.home_team, r.away_team): (int(r.home_score), int(r.away_score))
              for r in group.dropna(subset=["home_score", "away_score"]).itertuples()}
    ko_res = knockout_winners(ko)
    print(f"  group games played: {len(played)}/{len(fixtures)}; "
          f"knockout results: {len(ko_res)}")

    deltas_path = os.path.join(BASE, "outputs", "market_deltas.csv")
    if os.path.exists(deltas_path):
        dd = pd.read_csv(deltas_path)
        ratings = blend_ratings(ratings, dict(zip(dd["team"], dd["delta_elo"])), MARKET_WEIGHT)
        print(f"  applied bookmaker deltas at weight {MARKET_WEIGHT}")

    sim = Simulator(ratings, gm, fixtures)
    alloc = real_third_allocation(played, fixtures, ko, sim)
    if alloc:
        print("  using real round-of-32 third-place slotting")

    res = sim.simulate(N_SIMS, played=played, ko_results=ko_res, alloc_override=alloc)
    n = res["n"]
    out = []
    for g, ts in GROUPS.items():
        for t in ts:
            r = res["reach"][t]
            out.append({"date": today, "team": t, "group": g,
                        "elo": round(ratings[t]),
                        "win_group": res["positions"][t][0] / n,
                        **{f"reach_{k}": r[k] / n for k in ROUNDS[1:]}})
    tab = pd.DataFrame(out).sort_values("reach_champion", ascending=False)
    tab.drop(columns="date").to_csv(os.path.join(BASE, "outputs", "team_probabilities.csv"),
                                    index=False)

    # Per-match availability adjustments (suspensions/injuries the Elo prior can't
    # see). data/availability.csv: date,team,delta_elo,note — negative delta_elo
    # weakens the team for that one fixture only. Applied to the logged forecast
    # (what we price bets off); season-long ratings stay untouched because a
    # suspension is a one-game effect, not a lasting strength change.
    avail_path = os.path.join(BASE, "data", "availability.csv")
    avail = {}
    if os.path.exists(avail_path):
        av = pd.read_csv(avail_path)
        avail = {(str(r.date), r.team): float(r.delta_elo) for r in av.itertuples()}
        if avail:
            print(f"  loaded {len(avail)} availability adjustment(s)")

    # log today's forecasts for not-yet-played group games (for later scoring)
    from wc_model.elo import win_expectancy
    mrows = []
    for h, a, neu in fixtures:
        if (h, a) in played:
            continue
        dr = sim._dr(h, a, not neu)
        # availability is tied to the real match date, not the forecast date,
        # so a one-game suspension doesn't bleed onto the team's later fixtures
        mdate = fixture_date.get((h, a), today)
        adj = avail.get((mdate, h), 0.0) - avail.get((mdate, a), 0.0)
        if adj:
            print(f"  availability: {h} v {a} ({mdate}) dr {dr:+.0f} -> {dr + adj:+.0f} "
                  f"(home {avail.get((mdate, h), 0.0):+.0f}, "
                  f"away {avail.get((mdate, a), 0.0):+.0f})")
        we = win_expectancy(dr + adj)
        lam_h, lam_a = gm.expected_goals(we, not neu)
        pw, pdr, pl = gm.outcome_probs(we, not neu)
        mrows.append((today, h, a, round(lam_h, 3), round(lam_a, 3),
                      round(pw, 4), round(pdr, 4), round(pl, 4)))
    mf_path = os.path.join(BASE, "outputs", "match_forecast_history.csv")
    mf = pd.DataFrame(mrows, columns=["date", "home", "away", "xg_home", "xg_away",
                                      "p_home", "p_draw", "p_away"])
    if os.path.exists(mf_path):
        prev = pd.read_csv(mf_path)
        mf = pd.concat([prev[prev["date"] != today], mf], ignore_index=True)
    mf.to_csv(mf_path, index=False)

    hist_path = os.path.join(BASE, "outputs", "history.csv")
    if os.path.exists(hist_path):
        prev = pd.read_csv(hist_path)
        prev = prev[prev["date"] != today]  # re-running on the same day overwrites
        hist = pd.concat([prev, tab], ignore_index=True)
    else:
        hist = tab
    hist.to_csv(hist_path, index=False)

    print(f"\n{'Team':<22}{'R32':>7}{'R16':>7}{'QF':>7}{'SF':>7}{'Final':>7}{'Champ':>7}")
    for _, r in tab.head(12).iterrows():
        print(f"{r['team']:<22}{r['reach_r32']:>7.1%}{r['reach_r16']:>7.1%}"
              f"{r['reach_qf']:>7.1%}{r['reach_sf']:>7.1%}{r['reach_final']:>7.1%}"
              f"{r['reach_champion']:>7.1%}")


if __name__ == "__main__":
    main()
