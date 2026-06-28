"""Generate a single shareable daily report from the pipeline's outputs.

Reads the CSVs that update_predictions.py / evaluate_forecasts.py already
produce (no re-simulation — fast and cron-safe) and renders:

  outputs/report.html   self-contained, styled, send-to-anyone
  outputs/report.md      same content as Markdown

Sections
  1. Live championship leaderboard (blended forecast)
  2. Today's / next fixtures with the model's W-D-L + xG
  3. Model skill scorecard on every resolved group game
     (RPS / log-loss / Brier / avg p(actual) vs the uniform baseline)
     + a calibration table (forecast probability vs realized frequency)
  4. Advancement skill vs Polymarket (once the Round-of-32 field resolves)
  5. Honest betting ledger from outputs/bet_log.csv (settled record, ROI, open)

Run:  .venv/bin/python daily_report.py
"""

import base64
import datetime
import html
import io
import os
import re

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # headless: safe under cron / GitHub Actions
import matplotlib.pyplot as plt
from cycler import cycler

# Chart styling matched to the report's design system (navy palette, despined).
plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10.5,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": "#c8cedb", "axes.linewidth": .8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e9ecf3", "grid.linewidth": .9,
    "axes.titlesize": 12.5, "axes.titleweight": "bold", "axes.titlecolor": "#0a3d62",
    "axes.titlelocation": "left", "axes.titlepad": 10,
    "axes.labelcolor": "#5b6677", "xtick.color": "#5b6677", "ytick.color": "#5b6677",
    "axes.prop_cycle": cycler(color=["#0a3d62", "#e58e26", "#1e9b6b", "#c0392b",
                                     "#6c5ce7", "#0a6cb3", "#d6336c", "#16a085"]),
})

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "outputs")
REPO = "https://github.com/wcawleyortega-collab/worldcup-2026-model"

# Plain-language tooltips for the jargon (hover to read on the page).
GLOSSARY = {
    "RPS": "Ranked Probability Score — overall accuracy of the win/draw/loss forecasts. Lower is better.",
    "Brier": "Brier score — squared error of the probability forecasts. Lower is better.",
    "log-loss": "Log-loss — punishes confident wrong calls hard. Lower is better.",
    "Elo": "A rolling rating of team strength, updated after every match played since 1872.",
    "xG": "Expected goals — the model's average goals for each side in this match.",
    "BTTS": "Both teams to score — chance each side scores at least one goal.",
    "O2.5": "Over 2.5 goals — chance the match finishes with 3 or more goals.",
    "overround": "The bookmaker's built-in margin; stripped out so model and market compare fairly.",
    "calibration": "Whether outcomes the model calls '70% likely' actually happen about 70% of the time.",
    "ROI": "Return on investment of the paper bets.",
}
GROUP_END = "2026-06-28"
WC_START = "2026-06-11"


def _read(path, **kw):
    p = path if os.path.isabs(path) else os.path.join(BASE, path)
    return pd.read_csv(p, **kw) if os.path.exists(p) else None


# ---------------------------------------------------------------- data loaders
def load_results():
    df = _read("data/results.csv", na_values=["NA"])
    if df is None:
        return None
    return df[(df["tournament"] == "FIFA World Cup") & (df["date"] >= WC_START)]


def leaderboard(top=12):
    tab = _read("outputs/team_probabilities.csv")
    if tab is None:
        return None
    cols = ["team", "group", "elo", "reach_r16", "reach_qf", "reach_sf",
            "reach_final", "reach_champion"]
    cols = [c for c in cols if c in tab.columns]
    return tab.sort_values("reach_champion", ascending=False).head(top)[cols]


def next_fixtures():
    """Unplayed WC fixtures + the latest logged W/D/L forecast for each."""
    res = load_results()
    fc = _read("outputs/match_forecast_history.csv")
    if res is None:
        return None, None
    pend = res[res["home_score"].isna()].copy()
    if pend.empty or fc is None:
        return pend, None
    day = pend["date"].min()
    today = pend[pend["date"] == day]
    rows = []
    for r in today.itertuples():
        f = fc[(fc["home"] == r.home_team) & (fc["away"] == r.away_team)]
        if f.empty:
            continue
        f = f.sort_values("date").iloc[-1]
        rows.append((r.home_team, r.away_team, f.xg_home, f.xg_away,
                     f.p_home, f.p_draw, f.p_away))
    cols = ["home", "away", "xg_home", "xg_away", "p_home", "p_draw", "p_away"]
    return day, (pd.DataFrame(rows, columns=cols) if rows else None)


# ---------------------------------------------------------------- model skill
def match_skill():
    fc = _read("outputs/match_forecast_history.csv")
    res = load_results()
    if fc is None or res is None:
        return None, None
    played = res.dropna(subset=["home_score", "away_score"])
    played = played[played["date"] < GROUP_END]
    rows, probs, hits = [], [], []
    for r in played.itertuples():
        f = fc[(fc["home"] == r.home_team) & (fc["away"] == r.away_team)
               & (fc["date"] < r.date)].sort_values("date")
        if f.empty:
            continue
        f = f.iloc[-1]
        p = np.array([f.p_home, f.p_draw, f.p_away])
        obs = 0 if r.home_score > r.away_score else (1 if r.home_score == r.away_score else 2)
        o = np.zeros(3); o[obs] = 1
        rps = 0.5 * ((np.cumsum(p) - np.cumsum(o))[:2] ** 2).sum()
        rows.append((p[obs], rps, -np.log(max(p[obs], 1e-12)), ((p - o) ** 2).sum()))
        for i, pi in enumerate(p):
            probs.append(pi); hits.append(1.0 if i == obs else 0.0)
    if not rows:
        return None, None
    t = pd.DataFrame(rows, columns=["p_obs", "rps", "log_loss", "brier"])
    summary = {
        "n": len(t),
        "rps": t.rps.mean(), "rps_base": 0.2222,
        "log_loss": t.log_loss.mean(), "log_loss_base": float(np.log(3)),
        "brier": t.brier.mean(), "brier_base": 0.6667,
        "avg_p_actual": t.p_obs.mean(),
    }
    cal = pd.DataFrame({"p": probs, "hit": hits})
    cal["bucket"] = pd.cut(cal["p"], [0, .2, .4, .6, .8, 1])
    cal = cal.groupby("bucket", observed=True).agg(
        n=("hit", "size"), forecast=("p", "mean"), realized=("hit", "mean")).reset_index()
    return summary, cal


def advancement_skill():
    played = load_results()
    hist = _read("outputs/history.csv")
    pm = _read("data/polymarket_history.csv")
    if played is None or hist is None:
        return None
    ko = played.dropna(subset=["home_score", "away_score"])
    ko = ko[ko["date"] >= GROUP_END]
    if len(ko) < 16:
        return None
    r32 = set(ko.sort_values("date").head(16)[["home_team", "away_team"]].values.ravel())
    m = hist[["date", "team", "reach_r32"]].copy()
    m["outcome"] = m["team"].isin(r32).astype(float)
    model_brier = ((m["reach_r32"] - m["outcome"]) ** 2).mean()
    out = {"model": model_brier, "n_team_days": len(m)}
    if pm is not None and "market" in pm.columns:
        a = pm[pm["market"] == "advance"].copy()
        a["date"] = a["ts_utc"].str[:10]
        a = a.groupby(["date", "team"], as_index=False)["price"].mean()
        a["outcome"] = a["team"].isin(r32).astype(float)
        out["polymarket"] = ((a["price"] - a["outcome"]) ** 2).mean()
    return out


# ---------------------------------------------------------------- betting P&L
def betting_ledger():
    log = _read("outputs/bet_log.csv")
    if log is None:
        return None
    log["stake_eur"] = pd.to_numeric(log["stake_eur"], errors="coerce")
    log["potential_return_eur"] = pd.to_numeric(log["potential_return_eur"], errors="coerce")
    res = log["result"].astype(str).str.lower()
    won = log[res == "won"]; lost = log[res == "lost"]
    settled = log[res.isin(["won", "lost"])]
    open_bets = log[log["status"].astype(str).str.lower() == "open"]
    profit = (won["potential_return_eur"] - won["stake_eur"]).sum() - lost["stake_eur"].sum()
    staked = settled["stake_eur"].sum()
    return {
        "settled": len(settled), "won": len(won), "lost": len(lost),
        "scratched": int((log["status"].astype(str).str.lower() == "scratched").sum()),
        "staked": staked, "returned": won["potential_return_eur"].sum(),
        "profit": profit, "roi": (profit / staked * 100) if staked else 0.0,
        "open_n": len(open_bets), "open_stake": open_bets["stake_eur"].sum(),
        "open": open_bets[["bet_id", "legs", "decimal_odds", "stake_eur"]],
    }


# ---------------------------------------------------------------- model helpers
def _png(fig):
    """Render a matplotlib figure to a self-contained inline base64 <img>."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"<img alt='chart' style='max-width:100%;margin:10px 0' src='data:image/png;base64,{b64}'>"


def load_model():
    """Live blended ratings (the elo the last sim used) + a refit goal model.

    Fast (Elo pass + GLM fit, no Monte-Carlo) so the report stays cron-safe. The
    ratings already carry the squad-value and bookmaker blends; the goal model is
    the team-independent win-expectancy -> goals map."""
    tp = _read("outputs/team_probabilities.csv")
    res = _read("data/results.csv", na_values=["NA"])
    if tp is None or res is None:
        return None, None
    res["neutral"] = res["neutral"].astype(str).str.upper() == "TRUE"
    from wc_model.elo import compute_elo
    from wc_model.goals import GoalsModel
    _, log = compute_elo(res)
    gm = GoalsModel().fit(log)
    return dict(zip(tp["team"], tp["elo"].astype(float))), gm


def title_tracker():
    """Line chart of the top-8 teams' championship probability over the tournament."""
    hist = _read("outputs/history.csv")
    if hist is None or hist["date"].nunique() < 3:
        return None
    piv = hist.pivot_table(index="date", columns="team", values="reach_champion").sort_index()
    top = list(piv.iloc[-1].sort_values(ascending=False).index[:8])
    fig, ax = plt.subplots(figsize=(8, 4))
    for t in top:
        ax.plot(pd.to_datetime(piv.index), piv[t] * 100, marker="o", ms=3, lw=1.8, label=t)
    ax.set_ylabel("Championship probability (%)")
    ax.set_title("Title odds over the tournament (top 8)")
    ax.legend(fontsize=8, ncol=2, frameon=False)
    ax.grid(alpha=.25)
    fig.autofmt_xdate()
    return _png(fig)


def _market_snapshot(market, which="last"):
    pm = _read("data/polymarket_history.csv")
    if pm is None:
        return None
    a = pm[pm["market"] == market].sort_values("ts_utc")
    if a.empty:
        return None
    a = a.groupby("team", as_index=False).last() if which == "last" \
        else a.groupby("team", as_index=False).first()
    return dict(zip(a["team"], a["price"].astype(float)))


def market_vs_model():
    """Latest model vs Polymarket championship odds: scatter + biggest disagreements."""
    mk = _market_snapshot("outright", "last")
    tp = _read("outputs/team_probabilities.csv")
    if mk is None or tp is None:
        return None
    model = dict(zip(tp["team"], tp["reach_champion"].astype(float)))
    teams = [t for t in model if t in mk and mk[t] > 0]
    tot = sum(mk[t] for t in teams) or 1.0
    mkt = {t: mk[t] / tot for t in teams}  # strip overround -> compare on equal footing
    rows = sorted(((t, model[t], mkt[t], model[t] - mkt[t]) for t in teams),
                  key=lambda r: -abs(r[3]))
    fig, ax = plt.subplots(figsize=(6.2, 6))
    xs = [model[t] * 100 for t in teams]
    ys = [mkt[t] * 100 for t in teams]
    ax.scatter(xs, ys, s=20, alpha=.7, color="#0a3d62")
    lim = max(xs + ys + [1]) * 1.1
    ax.plot([0, lim], [0, lim], "--", color="#999", lw=1)
    for t, mo, ma, _ in rows[:6]:
        ax.annotate(t, (mo * 100, ma * 100), fontsize=7.5,
                    xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("Model champion %")
    ax.set_ylabel("Polymarket implied % (overround stripped)")
    ax.set_title("Model vs market — championship")
    ax.grid(alpha=.25)
    return _png(fig), rows


def market_efficiency():
    """Pre-tournament model vs market advancement priors, scored on who actually
    reached the round of 32 (now known from the bracket)."""
    res = load_results()
    if res is None:
        return None
    ko = res[res["date"] > GROUP_END]
    if ko.empty:
        return None
    advancers = set(ko["home_team"]) | set(ko["away_team"])
    mk = _market_snapshot("advance", "first")
    hist = _read("outputs/history.csv")
    if mk is None or hist is None:
        return None
    first_day = hist["date"].min()
    model0 = dict(zip(hist[hist["date"] == first_day]["team"],
                      hist[hist["date"] == first_day]["reach_r32"].astype(float)))
    teams = [t for t in model0 if t in mk]
    if len(teams) < 24:
        return None
    y = {t: (1.0 if t in advancers else 0.0) for t in teams}
    mb = np.mean([(model0[t] - y[t]) ** 2 for t in teams])
    kb = np.mean([(mk[t] - y[t]) ** 2 for t in teams])
    return {"model": float(mb), "market": float(kb), "n": len(teams)}


def knockout_board():
    """Each scheduled knockout tie with the model's W/D/L, advance %, expected
    goals, most-likely scorelines, BTTS and over-2.5 — from the live ratings."""
    res = load_results()
    tp = _read("outputs/team_probabilities.csv")
    if res is None or tp is None:
        return None
    ko = res[res["date"] > GROUP_END].copy()
    if ko.empty:
        return None
    ratings, gm = load_model()
    if ratings is None:
        return None
    from wc_model.elo import win_expectancy, HOME_ADV
    from wc_model.tournament import HOSTS
    adv = dict(zip(tp["team"], tp["reach_r16"].astype(float)))  # P(win the R32 tie)
    rows = []
    for r in ko.sort_values("date").itertuples():
        a, b = r.home_team, r.away_team
        a_home, b_home = a in HOSTS and b not in HOSTS, b in HOSTS and a not in HOSTS
        if b_home:                       # orient the home side as 'a' for the matrix
            a, b, a_home = b, a, True
        dr = ratings.get(a, 1500) - ratings.get(b, 1500) + (HOME_ADV if a_home else 0.0)
        lam_a, lam_b = gm.expected_goals(win_expectancy(dr), a_home)
        m = gm.score_matrix(lam_a, lam_b)
        flat = sorted(((m[i, j], i, j) for i in range(m.shape[0]) for j in range(m.shape[1])),
                      reverse=True)
        rows.append({
            "date": str(r.date), "a": a, "b": b,
            "adv_a": adv.get(a, float("nan")), "adv_b": adv.get(b, float("nan")),
            "pw": float(np.tril(m, -1).sum()), "pd": float(np.trace(m)),
            "pl": float(np.triu(m, 1).sum()), "lam_a": lam_a, "lam_b": lam_b,
            "top": ", ".join(f"{i}–{j} ({p:.0%})" for p, i, j in flat[:3]),
            "btts": float(m[1:, 1:].sum()),
            "over25": float(sum(m[i, j] for i in range(m.shape[0])
                                for j in range(m.shape[1]) if i + j >= 3)),
            "host": a_home})
    return rows


# ---------------------------------------------------------------- rendering
def _fmt_pct(x):
    return f"{x:.1%}" if pd.notna(x) else "—"


def _cards(lb, skill, bet):
    """An 'at a glance' summary band (raw HTML — passes through the renderer)."""
    def card(k, v, s):
        return (f'<div class="card"><div class="k">{html.escape(k)}</div>'
                f'<div class="v">{html.escape(v)}</div>'
                f'<div class="s">{html.escape(s)}</div></div>')
    c = []
    if lb is not None and len(lb):
        t = lb.iloc[0]
        c.append(card("Current favourite", str(t["team"]),
                      f"{t['reach_champion']:.1%} chance to win the cup"))
    if skill:
        better = (skill["rps_base"] - skill["rps"]) / skill["rps_base"] * 100
        c.append(card("Forecast accuracy", f"{skill['rps']:.3f}",
                      f"RPS — {better:.0f}% better than guessing ({skill['n']} games)"))
        c.append(card("Hit rate", f"{skill['avg_p_actual']:.0%}",
                      "avg confidence in the result that actually happened"))
    if bet:
        sign = "+" if bet["profit"] >= 0 else "−"
        c.append(card("Paper betting", f"{bet['won']}W–{bet['lost']}L",
                      f"net {sign}€{abs(bet['profit']):.0f} · tracked honestly, no real money"))
    return [f'<div class="cards">{"".join(c)}</div>', ""] if c else []


def build_markdown(date, lb, tracker, kb, day, fx, skill, cal, adv, mvm, eff, bet):
    L = [f"# 🏆 World Cup 2026 — Model Report · {date}", "",
         "*A fully-automated quant forecasting system: it rates every national team, "
         "runs 50,000 Monte-Carlo simulations of the tournament every day, prices every "
         "match, and grades its own forecasts against reality — no human in the loop. "
         "The honest headline finding: it is well-calibrated but not sharper than the "
         "betting market. Full write-up in PORTFOLIO.md.*", ""]
    L += _cards(lb, skill, bet)
    if lb is not None:
        L += ["## Championship leaderboard",
              "> Each team's simulated chance of reaching each knockout round and lifting "
              "the trophy, from 50,000 tournament simulations. Darker cells = more likely.",
              "",
              "| Team | Grp | Elo | R16 | QF | SF | Final | **Champ** |",
              "|---|---|--:|--:|--:|--:|--:|--:|"]
        for r in lb.itertuples(index=False):
            L.append(f"| {r.team} | {getattr(r,'group','')} | {int(r.elo)} | "
                     f"{_fmt_pct(r.reach_r16)} | {_fmt_pct(r.reach_qf)} | {_fmt_pct(r.reach_sf)} | "
                     f"{_fmt_pct(r.reach_final)} | **{_fmt_pct(r.reach_champion)}** |")
        L.append("")
    if tracker:
        L += ["## Title odds over time",
              "> How each contender's championship chance has moved as results came in.",
              "", tracker, ""]
    if kb:
        L += ["## Round of 32 — match by match",
              "> Advance % is the model's chance of winning the tie (including extra time "
              "and penalties). W/D/L, scorelines, BTTS and O2.5 are the 90-minute picture. "
              "(H) marks the host side, which gets home advantage.",
              "",
              "| Tie (advance %) | W/D/L 90′ | xG | Most likely scores | BTTS | O2.5 |",
              "|---|--:|--:|---|--:|--:|"]
        for r in kb:
            ha = " (H)" if r["host"] else ""
            tie = f"{r['a']}{ha} {r['adv_a']:.0%} v {r['b']} {r['adv_b']:.0%}"
            L.append(f"| {tie} | {r['pw']*100:.0f}/{r['pd']*100:.0f}/{r['pl']*100:.0f} | "
                     f"{r['lam_a']:.1f}–{r['lam_b']:.1f} | {r['top']} | "
                     f"{r['btts']:.0%} | {r['over25']:.0%} |")
        L.append("")
    if fx is not None:
        L += [f"## Next fixtures — {day}",
              "> The model's win / draw / loss call and expected goals for the next games.",
              "", "| Match | xG | Home | Draw | Away |", "|---|---|--:|--:|--:|"]
        for r in fx.itertuples(index=False):
            L.append(f"| {r.home} v {r.away} | {r.xg_home:.2f}–{r.xg_away:.2f} | "
                     f"{_fmt_pct(r.p_home)} | {_fmt_pct(r.p_draw)} | {_fmt_pct(r.p_away)} |")
        L.append("")
    if skill is not None:
        s = skill
        L += [f"## How accurate is it? ({s['n']} resolved games)",
              "> Pre-kickoff forecasts scored against reality, versus blindly guessing "
              "33/33/33. On every metric, lower is better except hit rate.", "",
              "| Metric | Model | Guessing |", "|---|--:|--:|",
              f"| RPS | **{s['rps']:.4f}** | {s['rps_base']:.4f} |",
              f"| log-loss | **{s['log_loss']:.4f}** | {s['log_loss_base']:.4f} |",
              f"| Brier | **{s['brier']:.4f}** | {s['brier_base']:.4f} |",
              f"| Hit rate (avg P of actual) | **{s['avg_p_actual']:.1%}** | 33.3% |", ""]
    if cal is not None:
        L += ["### Calibration check",
              "> When the model says X%, does it happen about X% of the time? Forecast "
              "vs reality, bucketed.", "",
              "| Forecast bucket | n | Model said | Actually happened |", "|---|--:|--:|--:|"]
        for r in cal.itertuples(index=False):
            L.append(f"| {r.bucket} | {int(r.n)} | {r.forecast:.1%} | {r.realized:.1%} |")
        L.append("")
    if adv is not None:
        L += ["## Advancement skill (Round-of-32, Brier — lower better)", ""]
        L.append(f"- Model: **{adv['model']:.4f}** ({adv['n_team_days']} team-days)")
        if "polymarket" in adv:
            L.append(f"- Polymarket: **{adv['polymarket']:.4f}**")
        L.append("")
    if mvm is not None:
        img, rows = mvm
        L += ["## Model vs the betting market",
              "> Championship odds: the model against Polymarket (overround stripped). "
              "Points on the dashed line mean they agree; the table shows where they "
              "disagree most.",
              "", img, "",
              "| Biggest disagreement | Model | Market | Gap |", "|---|--:|--:|--:|"]
        for t, mo, ma, d in rows[:8]:
            L.append(f"| {t} | {mo:.1%} | {ma:.1%} | {d*100:+.1f} |")
        L.append("")
        if eff is not None:
            verdict = ("the market edged the model" if eff['market'] < eff['model']
                       else "the model edged the market")
            L += [f"**Who called advancement better?** Scored on who actually reached the "
                  f"Round of 32 (n={eff['n']}): model Brier **{eff['model']:.3f}** vs "
                  f"Polymarket **{eff['market']:.3f}** — {verdict}, consistent with the "
                  f"project's honest finding that the model is well-calibrated but not "
                  f"sharper than the market.", ""]
    if bet is not None:
        b = bet
        sign = "+" if b["profit"] >= 0 else ""
        L += ["## Betting ledger (paper, honest)",
              "> A paper-traded book — no real money — kept to test honestly whether any "
              "model-vs-market edge is actually real. So far: no.", "",
              f"- **Settled:** {b['won']}W–{b['lost']}L  ·  staked {b['staked']:.0f}  ·  "
              f"returned {b['returned']:.0f}  ·  **net {sign}{b['profit']:.2f}** "
              f"(ROI {sign}{b['roi']:.1f}%)",
              f"- **Scratched** (no stake, pre-kickoff): {b['scratched']}",
              f"- **Open:** {b['open_n']} bets, {b['open_stake']:.0f} staked", ""]
        if b["open_n"]:
            L += ["| Open bet | Odds | Stake |", "|---|--:|--:|"]
            for r in b["open"].itertuples(index=False):
                legs = str(r.legs).replace("|", " / ")
                L.append(f"| {legs} | {r.decimal_odds} | {r.stake_eur:.0f} |")
            L.append("")
    L += ["---", "*Auto-generated by `daily_report.py` from the live pipeline. "
          "Model: Elo → Poisson → Dixon-Coles → Monte-Carlo, blended with bookmaker "
          "consensus. Forecasts are logged before kickoff; the ledger is paper-traded "
          "and tracked honestly.*"]
    return "\n".join(L)


CSS = """
:root{--navy:#0a3d62;--ink:#1b2433;--muted:#5b6677;--line:#e6e8ef;--bg:#f4f6fb;
  --card:#fff;--accent:#0a6cb3}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{font:16px/1.6 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;margin:0;
  color:var(--ink);background:var(--bg);-webkit-text-size-adjust:100%}
.topbar{position:sticky;top:0;z-index:20;display:flex;gap:14px;align-items:center;
  padding:10px 18px;background:rgba(10,61,98,.97);color:#fff;overflow-x:auto;
  box-shadow:0 1px 10px rgba(0,0,0,.14);scrollbar-width:none}
.topbar::-webkit-scrollbar{display:none}
.topbar .brand{font-weight:700;white-space:nowrap;font-size:15px}
.topbar nav{display:flex;gap:4px}
.topbar a{color:#cfe3f3;text-decoration:none;font-size:13px;white-space:nowrap;
  padding:5px 10px;border-radius:99px}
.topbar a:hover,.topbar a:focus{background:rgba(255,255,255,.16);color:#fff;outline:none}
main{max-width:900px;margin:0 auto;padding:6px 18px 64px}
.datebadge{display:inline-block;margin:22px 0 0;background:#e7eff7;color:var(--navy);
  font-weight:600;font-size:12px;padding:4px 11px;border-radius:99px;letter-spacing:.3px}
h1{font-size:clamp(25px,5.5vw,34px);letter-spacing:-.6px;margin:8px 0 2px;line-height:1.15}
h2{font-size:clamp(19px,3.6vw,24px);color:var(--navy);margin:42px 0 0;padding-top:14px;
  border-top:1px solid var(--line);scroll-margin-top:60px}
h3{font-size:17px;color:#2c5f86;margin:22px 0 0;scroll-margin-top:60px}
p{margin:11px 0}.li{margin:5px 0}
.sub{color:var(--muted);font-size:14.5px;margin:6px 0 4px;max-width:64ch}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
abbr{text-decoration:underline dotted;text-underline-offset:3px;cursor:help}
strong{color:var(--navy)}
.lede{margin:16px 0;padding:16px 18px;background:var(--card);border:1px solid var(--line);
  border-left:4px solid var(--navy);border-radius:12px;font-size:15px;color:#33405a;
  box-shadow:0 1px 4px rgba(10,61,98,.06)}
.lede a{font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:18px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;
  box-shadow:0 1px 4px rgba(10,61,98,.05)}
.card .k{font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted)}
.card .v{font-size:25px;font-weight:700;color:var(--navy);margin:4px 0;line-height:1.1}
.card .s{font-size:12.5px;color:var(--muted);line-height:1.4}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:14px 0;border:1px solid var(--line);
  border-radius:14px;box-shadow:0 1px 4px rgba(10,61,98,.05)}
table{border-collapse:collapse;width:100%;font-size:14px;background:var(--card)}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{background:var(--navy);color:#fff;border:none;font-weight:600}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:#eef4fa}
img{max-width:100%;height:auto;display:block;margin:14px 0;border:1px solid var(--line);
  border-radius:14px;background:#fff;padding:6px}
hr{border:none;border-top:1px solid var(--line);margin:36px 0 14px}
footer{color:var(--muted);font-size:12.5px;max-width:66ch;line-height:1.5}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""


def md_to_html(md, date):
    """Self-contained renderer for the Markdown subset the report emits, styled for
    clarity and for reading on a phone or a desktop."""
    body, in_tbl, lede_done, toc, seen = [], False, False, [], {}
    term_re = re.compile(r"\b(" + "|".join(re.escape(t) for t in
                         sorted(GLOSSARY, key=len, reverse=True)) + r")\b")

    def inline(s):
        s = html.escape(s)
        while "**" in s:
            s = s.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
        return term_re.sub(lambda m: f'<abbr title="{GLOSSARY[m.group(1)]}">{m.group(1)}</abbr>', s)

    def cell(c, head=False):
        if head:
            return f"<th>{inline(c)}</th>"
        style = ""
        m = re.fullmatch(r"\*{0,2}(\d{1,3}(?:\.\d+)?)%\*{0,2}", c.strip())
        if m:  # shade single-percentage cells: darker = more likely
            v = min(float(m.group(1)), 100) / 100
            style = (f' style="background:rgba(10,61,98,{0.06 + 0.46 * v:.2f})'
                     + (';color:#fff"' if v > 0.62 else '"'))
        return f"<td{style}>{inline(c)}</td>"

    def slug(t):
        s = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "sec"
        if s in seen:
            seen[s] += 1; s = f"{s}-{seen[s]}"
        else:
            seen[s] = 0
        return s

    for ln in md.split("\n"):
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-:| "):
                continue
            if not in_tbl:
                body.append('<div class="tw"><table><thead><tr>'
                            + "".join(cell(c, True) for c in cells) + "</tr></thead><tbody>")
                in_tbl = True
            else:
                body.append("<tr>" + "".join(cell(c) for c in cells) + "</tr>")
            continue
        if in_tbl:
            body.append("</tbody></table></div>"); in_tbl = False
        if ln.lstrip().startswith("<"):     # raw HTML passthrough (cards, charts)
            body.append(ln); continue
        if ln.startswith("# "):
            body.append(f"<h1>{inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            sid = slug(ln[3:])
            toc.append((sid, re.split(r"[(—]", ln[3:])[0].strip()))
            body.append(f'<h2 id="{sid}">{inline(ln[3:])}</h2>')
        elif ln.startswith("### "):
            body.append(f"<h3>{inline(ln[4:])}</h3>")
        elif ln.startswith("> "):
            body.append(f'<p class="sub">{inline(ln[2:])}</p>')
        elif ln.startswith("- "):
            body.append(f'<p class="li">• {inline(ln[2:])}</p>')
        elif ln.strip() == "---":
            body.append("<hr>")
        elif ln.startswith("*") and ln.endswith("*"):
            if not lede_done and any("<h1" in b for b in body):
                body.append(
                    f"<div class='lede'>{inline(ln.strip('*'))} "
                    f"<a href='{REPO}'>Source</a> · "
                    f"<a href='{REPO}/blob/main/PORTFOLIO.md'>Full write-up</a></div>")
                lede_done = True
            else:
                body.append(f"<footer>{inline(ln.strip('*'))}</footer>")
        elif ln.strip():
            body.append(f"<p>{inline(ln)}</p>")
    if in_tbl:
        body.append("</tbody></table></div>")

    nav = "".join(f'<a href="#{i}">{html.escape(l)}</a>' for i, l in toc)
    head = (f'<meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="description" content="Automated 2026 World Cup forecasting '
            f'model — a live, self-grading report.">'
            f'<title>WC2026 Model Report · {date}</title><style>{CSS}</style>')
    return (f'<!doctype html><html lang="en"><head>{head}</head><body>'
            f'<header class="topbar"><span class="brand">⚽ WC2026 Model</span>'
            f'<nav>{nav}</nav></header><main>'
            f'<span class="datebadge">🔄 Auto-updated twice daily · {date}</span>'
            + "\n".join(body) + "</main></body></html>")


def _try(fn):
    """Run an optional section; never let it break the cron report."""
    try:
        return fn()
    except Exception as e:
        print(f"  warn: {fn.__name__} failed: {e}")
        return None


def main():
    date = datetime.date.today().isoformat()
    lb = leaderboard()
    day, fx = next_fixtures()
    skill, cal = match_skill()
    adv = advancement_skill()
    bet = betting_ledger()
    tracker = _try(title_tracker)
    kb = _try(knockout_board)
    mvm = _try(market_vs_model)
    eff = _try(market_efficiency)
    md = build_markdown(date, lb, tracker, kb, day, fx, skill, cal, adv, mvm, eff, bet)
    page = md_to_html(md, date)
    # HTML stays self-contained (base64 charts inlined); the .md view drops the
    # data URIs so the markdown file stays small and diff-friendly.
    import re
    md_file = re.sub(r"<img[^>]*>", "*(chart — view the HTML report)*", md)
    with open(os.path.join(OUT, "report.md"), "w") as f:
        f.write(md_file)
    with open(os.path.join(OUT, "report.html"), "w") as f:
        f.write(page)
    # also publish to docs/ so GitHub Pages serves the live report at the site root
    docs = os.path.join(BASE, "docs")
    os.makedirs(docs, exist_ok=True)
    with open(os.path.join(docs, "index.html"), "w") as f:
        f.write(page)
    print(f"wrote outputs/report.{{md,html}} and docs/index.html ({date})")
    if skill:
        print(f"  model skill: {skill['n']} games, avg p(actual) {skill['avg_p_actual']:.1%}, "
              f"RPS {skill['rps']:.4f}")
    if bet:
        print(f"  betting: {bet['won']}W-{bet['lost']}L settled, net {bet['profit']:+.2f}, "
              f"{bet['open_n']} open")


if __name__ == "__main__":
    main()
