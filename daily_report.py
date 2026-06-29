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

# Charts are themed dark + transparent so they sit on the report's glass panels.
plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10.5,
    "figure.facecolor": "none", "axes.facecolor": "none", "savefig.facecolor": "none",
    "text.color": "#c9d4e3", "axes.labelcolor": "#9fb0c6",
    "xtick.color": "#7e8ca3", "ytick.color": "#7e8ca3",
    "axes.edgecolor": "#33415c", "axes.linewidth": .8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#ffffff16", "grid.linewidth": .8,
    "axes.titlesize": 12.5, "axes.titleweight": "bold", "axes.titlecolor": "#e8eefb",
    "axes.titlelocation": "left", "axes.titlepad": 10,
    "legend.frameon": False, "legend.labelcolor": "#c9d4e3",
    "axes.prop_cycle": cycler(color=["#5d8fd1", "#d6a25c", "#69b29a", "#c47f8c",
                                     "#8a86c0", "#7faad8", "#a8788f", "#5fa9ad"]),
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
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", transparent=True)
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
    ax.legend(fontsize=8, ncol=2, frameon=False, labelcolor="#c9d4e3")
    ax.grid(alpha=.25)
    fig.autofmt_xdate()
    return _png(fig)


def reliability_chart(cal):
    """Reliability diagram: forecast probability vs realized frequency, with the
    perfect-calibration diagonal and binomial 95% bands (the sampling uncertainty
    implied by each bucket's game count). Marker area scales with bucket size."""
    if cal is None or len(cal) == 0:
        return None
    f = cal["forecast"].to_numpy(float)
    r = cal["realized"].to_numpy(float)
    n = cal["n"].to_numpy(float)
    se = np.sqrt(np.clip(r * (1 - r), 0, None) / np.maximum(n, 1))
    fig, ax = plt.subplots(figsize=(5.6, 5.6))
    ax.plot([0, 1], [0, 1], "--", color="#5b6b86", lw=1, label="perfect calibration")
    ax.errorbar(f, r, yerr=1.96 * se, fmt="none", ecolor="#5d8fd1",
                elinewidth=1.2, capsize=3, alpha=.7, zorder=3)
    ax.scatter(f, r, s=24 + 16 * np.sqrt(n), color="#5d8fd1",
               edgecolors="#0a1020", linewidths=.6, zorder=4)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("Model forecast probability")
    ax.set_ylabel("Observed frequency")
    ax.legend(fontsize=8, frameon=False, labelcolor="#c9d4e3", loc="upper left")
    ax.grid(alpha=.25)
    ax.set_aspect("equal", "box")
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
    ax.scatter(xs, ys, s=34, alpha=.85, color="#5d8fd1", edgecolors="#0a1020", linewidths=.6)
    lim = max(xs + ys + [1]) * 1.1
    ax.plot([0, lim], [0, lim], "--", color="#5b6b86", lw=1)
    for t, mo, ma, _ in rows[:6]:
        ax.annotate(t, (mo * 100, ma * 100), fontsize=7.5,
                    xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("Model champion %")
    ax.set_ylabel("Polymarket implied % (overround stripped)")
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
    base = float(np.mean(list(y.values())))  # climatology: predict the base rate
    return {"model": float(mb), "market": float(kb), "n": len(teams),
            "base_brier": base * (1 - base)}


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


def _ticker(num, dec=0, suffix="", prefix=""):
    """Count-up animated number (driven by the page's JS)."""
    return (f'<span class="ticker" data-to="{num}" data-dec="{dec}" '
            f'data-suffix="{suffix}" data-prefix="{prefix}">{prefix}{num:.{dec}f}{suffix}</span>')


def _cards(lb, skill, bet):
    """An 'at a glance' bento band (raw HTML — passes through the renderer)."""
    def card(k, v_html, s):
        return (f'<div class="card"><div class="k">{html.escape(k)}</div>'
                f'<div class="v">{v_html}</div>'
                f'<div class="s">{html.escape(s)}</div></div>')
    c = []
    if lb is not None and len(lb):
        t = lb.iloc[0]
        c.append(card("Current favourite", html.escape(str(t["team"])),
                      f"{t['reach_champion']:.1%} chance to win the cup"))
    if skill:
        better = (skill["rps_base"] - skill["rps"]) / skill["rps_base"] * 100
        c.append(card("Forecast accuracy", _ticker(skill["rps"], 3),
                      f"RPS — {better:.0f}% better than guessing ({skill['n']} games)"))
        c.append(card("Hit rate", _ticker(skill["avg_p_actual"] * 100, 0, "%"),
                      "avg confidence in the result that actually happened"))
    if bet:
        sign = "+" if bet["profit"] >= 0 else "−"
        c.append(card("Paper betting", f"{bet['won']}W–{bet['lost']}L",
                      f"net {sign}€{abs(bet['profit']):.0f} · tracked honestly, no real money"))
    return [f'<div class="cards">{"".join(c)}</div>', ""] if c else []


def build_markdown(date, lb, tracker, kb, day, fx, skill, cal, rel, adv, mvm, eff, bet):
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
              "the trophy, from 50,000 tournament simulations. Darker cells = more likely. "
              "Each probability carries a Monte-Carlo 95% margin of ≤ ±0.4 pp from the "
              "50,000 draws.",
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
              "> When the model says X%, does it happen about X% of the time? Points on "
              "the diagonal are perfectly calibrated; the bars are 95% bands implied by "
              "each bucket's sample size, and bigger dots hold more games.", ""]
        if rel:
            L += [rel, ""]
        L += ["| Forecast bucket | n | Model said | Actually happened |", "|---|--:|--:|--:|"]
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
            if eff.get("base_brier"):
                bss_m = 1 - eff["model"] / eff["base_brier"]
                bss_k = 1 - eff["market"] / eff["base_brier"]
                L += [f"> Brier skill score versus a no-skill climatology forecast "
                      f"(always predict the base rate, Brier {eff['base_brier']:.3f}): "
                      f"model **{bss_m:+.1%}**, market **{bss_k:+.1%}** — both beat "
                      f"chance, the market by more.", ""]
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
:root{--bg:#0a0d13;--ink:#e7ecf3;--muted:#97a4b6;--faint:#67738a;
  --line:rgba(255,255,255,.07);--line2:rgba(255,255,255,.14);
  --panel:rgba(18,24,38,.55);--accent:#5d8fd1;
  --grad:linear-gradient(100deg,#9cbceb,#5d8fd1)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font:16px/1.6 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  color:var(--ink);background:var(--bg);-webkit-font-smoothing:antialiased;overflow-x:hidden}
.aurora{position:fixed;inset:0;z-index:-2;background:
  radial-gradient(45% 55% at 12% 6%,rgba(93,143,209,.13),transparent 62%),
  radial-gradient(48% 58% at 88% 2%,rgba(120,150,200,.08),transparent 62%),
  radial-gradient(55% 65% at 60% 104%,rgba(80,118,176,.07),transparent 62%),var(--bg)}
.grid{position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.55;
  background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),
    linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:48px 48px;
  -webkit-mask:radial-gradient(circle at 50% 0,#000 28%,transparent 78%);
  mask:radial-gradient(circle at 50% 0,#000 28%,transparent 78%)}
.topbar{position:sticky;top:0;z-index:30;display:flex;gap:14px;align-items:center;
  padding:11px 20px;background:rgba(10,13,19,.72);backdrop-filter:blur(16px) saturate(1.3);
  -webkit-backdrop-filter:blur(16px) saturate(1.4);border-bottom:1px solid var(--line);
  overflow-x:auto;scrollbar-width:none}
.topbar::-webkit-scrollbar{display:none}
.topbar .brand{font-weight:700;font-size:15px;white-space:nowrap;
  background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.topbar nav{display:flex;gap:3px}
.topbar a{color:var(--muted);text-decoration:none;font-size:13px;white-space:nowrap;
  padding:5px 11px;border-radius:99px;transition:.2s}
.topbar a:hover,.topbar a:focus{color:var(--ink);background:rgba(255,255,255,.07);outline:none}
.topbar a.active{color:var(--ink);background:rgba(93,143,209,.16);
  box-shadow:inset 0 0 0 1px rgba(93,143,209,.32)}
main{max-width:960px;margin:0 auto;padding:8px 20px 80px}
.datebadge{display:inline-flex;align-items:center;gap:6px;margin:28px 0 0;
  background:rgba(93,143,209,.1);color:var(--accent);font-weight:600;font-size:12px;
  padding:5px 12px;border-radius:99px;border:1px solid rgba(93,143,209,.24);letter-spacing:.3px}
h1{font-size:clamp(30px,6.5vw,50px);line-height:1.06;letter-spacing:-1.2px;margin:16px 0 4px;
  font-weight:800;background:linear-gradient(180deg,#fff,#aab9d4);
  -webkit-background-clip:text;background-clip:text;color:transparent}
h2{font-size:clamp(21px,3.8vw,28px);font-weight:700;letter-spacing:-.5px;color:var(--ink);
  margin:58px 0 0;padding-top:24px;border-top:1px solid var(--line);scroll-margin-top:66px}
h3{font-size:18px;color:#cdd9ec;margin:26px 0 0;scroll-margin-top:66px}
p{margin:11px 0}.li{margin:5px 0;color:#cdd9ec}
.sub{color:var(--muted);font-size:14.5px;margin:8px 0 6px;max-width:66ch}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
abbr{text-decoration:underline dotted rgba(93,143,209,.65);text-underline-offset:3px;cursor:help}
strong{color:#fff;font-weight:650}
.lede{position:relative;margin:20px 0;padding:18px 22px;border-radius:16px;background:var(--panel);
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid var(--line);
  font-size:15px;color:#d7e0f0;overflow:hidden}
.lede::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--grad)}
.lede a{font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:24px 0}
.card{position:relative;padding:18px 20px;border-radius:18px;background:var(--panel);
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid var(--line);
  overflow:hidden;transition:transform .25s,border-color .25s}
.card:hover{transform:translateY(-3px);border-color:var(--line2)}
.card::after{content:"";position:absolute;inset:0;border-radius:18px;padding:1px;
  background:radial-gradient(130px 130px at var(--mx,50%) var(--my,-20%),rgba(93,143,209,.6),transparent 62%);
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
  -webkit-mask-composite:xor;mask-composite:exclude;opacity:0;transition:opacity .3s}
.card:hover::after{opacity:1}
.card .k{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--faint)}
.card .v{font-size:clamp(26px,4vw,32px);font-weight:800;letter-spacing:-.6px;margin:7px 0 5px;
  line-height:1;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.card .s{font-size:12.5px;color:var(--muted);line-height:1.45}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:16px 0;border-radius:16px;
  border:1px solid var(--line);background:var(--panel);
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:10px 13px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{background:rgba(255,255,255,.045);color:#cdd9ec;font-weight:600;border-bottom:1px solid var(--line2)}
tbody tr{transition:background .15s}
tbody tr:hover{background:rgba(93,143,209,.07)}
tbody tr:last-child td{border-bottom:none}
img{max-width:100%;height:auto;display:block;margin:16px 0;border-radius:16px;
  border:1px solid var(--line);background:rgba(13,19,34,.45);padding:12px}
hr{border:none;border-top:1px solid var(--line);margin:42px 0 16px}
footer{color:var(--faint);font-size:12.5px;max-width:68ch;line-height:1.5}
.js .reveal{opacity:0;transform:translateY(16px);transition:opacity .6s ease,transform .6s ease}
.js .reveal.in{opacity:1;transform:none}
@media print{.reveal{opacity:1!important;transform:none!important}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}html{scroll-behavior:auto}
  .js .reveal{opacity:1;transform:none;transition:none}}
"""

JS = """
if(!('IntersectionObserver' in window)){
  document.querySelectorAll('.reveal').forEach(e=>e.classList.add('in'));}
const ease=t=>1-Math.pow(1-t,3);
function tick(el){const to=parseFloat(el.dataset.to),dec=+(el.dataset.dec||0),
  suf=el.dataset.suffix||'',pre=el.dataset.prefix||'',t0=performance.now();
  function f(t){const p=Math.min(1,(t-t0)/900);
    el.textContent=pre+(to*ease(p)).toFixed(dec)+suf;if(p<1)requestAnimationFrame(f)}
  requestAnimationFrame(f)}
const io=new IntersectionObserver((es)=>es.forEach(e=>{if(e.isIntersecting){
  e.target.classList.add('in');
  e.target.querySelectorAll('.ticker[data-to]').forEach(k=>{if(!k._d){k._d=1;tick(k)}});
  io.unobserve(e.target)}}),{threshold:.12});
document.querySelectorAll('main>h1,main>h2,main>h3,main>.cards,main>.tw,main>img,main>.lede,main>p')
  .forEach(el=>{el.classList.add('reveal');io.observe(el)});
const links=[...document.querySelectorAll('.topbar a')],map={};
links.forEach(a=>map[a.getAttribute('href').slice(1)]=a);
const so=new IntersectionObserver((es)=>es.forEach(e=>{if(e.isIntersecting){
  links.forEach(l=>l.classList.remove('active'));map[e.target.id]&&map[e.target.id].classList.add('active')}}),
  {rootMargin:'-18% 0px -72% 0px'});
document.querySelectorAll('main h2[id]').forEach(h=>so.observe(h));
document.querySelectorAll('.card').forEach(c=>c.addEventListener('mousemove',e=>{
  const r=c.getBoundingClientRect();
  c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px')}));
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
        if m:  # heat-shade single-percentage cells: brighter glow = more likely
            v = min(float(m.group(1)), 100) / 100
            style = f' style="background:rgba(93,143,209,{0.04 + 0.34 * v:.2f})"'
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
            f'<title>WC2026 Model Report · {date}</title><style>{CSS}</style>'
            f'<script>document.documentElement.classList.add("js")</script>')
    return (f'<!doctype html><html lang="en"><head>{head}</head><body>'
            f'<div class="aurora" aria-hidden="true"></div>'
            f'<div class="grid" aria-hidden="true"></div>'
            f'<header class="topbar"><span class="brand">⚽ WC2026 Model</span>'
            f'<nav>{nav}</nav></header><main>'
            f'<span class="datebadge">🔄 Auto-updated twice daily · {date}</span>'
            + "\n".join(body) + f"</main><script>{JS}</script></body></html>")


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
    rel = _try(lambda: reliability_chart(cal))
    md = build_markdown(date, lb, tracker, kb, day, fx, skill, cal, rel, adv, mvm, eff, bet)
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
