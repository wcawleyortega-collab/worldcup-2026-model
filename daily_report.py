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

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # headless: safe under cron / GitHub Actions
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "outputs")
REPO = "https://github.com/wcawleyortega-collab/worldcup-2026-model"
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


def build_markdown(date, lb, tracker, kb, day, fx, skill, cal, adv, mvm, eff, bet):
    L = [f"# 🏆 World Cup 2026 — Model Report · {date}", "",
         "*A fully-automated quant forecasting system: it rates every national team, "
         "runs 50,000 Monte-Carlo simulations of the tournament every day, prices every "
         "match, and grades its own forecasts against reality — no human in the loop. "
         "The honest headline finding: it is well-calibrated but not sharper than the "
         "betting market. Full write-up in PORTFOLIO.md.*", ""]
    if lb is not None:
        L += ["## Championship leaderboard (blended forecast)", "",
              "| Team | Grp | Elo | R16 | QF | SF | Final | **Champ** |",
              "|---|---|--:|--:|--:|--:|--:|--:|"]
        for r in lb.itertuples(index=False):
            L.append(f"| {r.team} | {getattr(r,'group','')} | {int(r.elo)} | "
                     f"{_fmt_pct(r.reach_r16)} | {_fmt_pct(r.reach_qf)} | {_fmt_pct(r.reach_sf)} | "
                     f"{_fmt_pct(r.reach_final)} | **{_fmt_pct(r.reach_champion)}** |")
        L.append("")
    if tracker:
        L += ["## Title odds over time", "", tracker, ""]
    if kb:
        L += ["## Round of 32 — model match detail", "",
              "Advance % is the model's simulated probability of winning the tie (incl. "
              "extra time / penalties); W/D/L, scorelines, BTTS and over-2.5 are the "
              "90-minute Poisson–Dixon-Coles distribution. *(H) = host (home advantage).*",
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
        L += [f"## Next fixtures — {day} (model W/D/L)", "",
              "| Match | xG | Home | Draw | Away |", "|---|---|--:|--:|--:|"]
        for r in fx.itertuples(index=False):
            L.append(f"| {r.home} v {r.away} | {r.xg_home:.2f}–{r.xg_away:.2f} | "
                     f"{_fmt_pct(r.p_home)} | {_fmt_pct(r.p_draw)} | {_fmt_pct(r.p_away)} |")
        L.append("")
    if skill is not None:
        s = skill
        L += [f"## Model skill — {s['n']} resolved group games", "",
              "| Metric | Model | Uniform baseline |", "|---|--:|--:|",
              f"| RPS (lower better) | **{s['rps']:.4f}** | {s['rps_base']:.4f} |",
              f"| Log-loss | **{s['log_loss']:.4f}** | {s['log_loss_base']:.4f} |",
              f"| Brier | **{s['brier']:.4f}** | {s['brier_base']:.4f} |",
              f"| Avg P(actual outcome) | **{s['avg_p_actual']:.1%}** | 33.3% |", ""]
    if cal is not None:
        L += ["### Calibration (forecast prob vs realized frequency)", "",
              "| Bucket | n | Forecast | Realized |", "|---|--:|--:|--:|"]
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
        L += ["## Model vs market (live efficiency study)", "",
              "Championship odds: the model against Polymarket (overround stripped). "
              "Points on the dashed line mean agreement; the table lists where they diverge most.",
              "", img, "",
              "| Biggest disagreement | Model | Market | Gap |", "|---|--:|--:|--:|"]
        for t, mo, ma, d in rows[:8]:
            L.append(f"| {t} | {mo:.1%} | {ma:.1%} | {d*100:+.1f} |")
        L.append("")
        if eff is not None:
            L += [f"**Advancement (pre-tournament priors, scored on who reached the "
                  f"Round of 32, n={eff['n']}):** model Brier **{eff['model']:.3f}** vs "
                  f"Polymarket **{eff['market']:.3f}** — "
                  + ("the market edged the model" if eff['market'] < eff['model']
                     else "the model edged the market")
                  + ", consistent with the project's honest finding that the model is "
                  "well-calibrated but not sharper than the market.", ""]
    if bet is not None:
        b = bet
        sign = "+" if b["profit"] >= 0 else ""
        L += ["## Betting ledger (paper, honest)", "",
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


def md_to_html(md, date):
    """Tiny self-contained renderer for the subset of Markdown we emit."""
    css = """
    body{font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
      max-width:860px;margin:40px auto;padding:0 20px;color:#1a1a2e;background:#fafafe}
    h1{font-size:27px;border-bottom:3px solid #0a3d62;padding-bottom:10px;letter-spacing:-.3px}
    h2{font-size:20px;margin-top:34px;color:#0a3d62}
    h3{font-size:16px;color:#3c6382}
    table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px;
      box-shadow:0 1px 3px rgba(10,61,98,.07);border-radius:6px;overflow:hidden}
    th,td{padding:7px 10px;border-bottom:1px solid #e1e1ee;text-align:right}
    th:first-child,td:first-child{text-align:left}
    thead th{background:#0a3d62;color:#fff;border:none}
    tbody tr:hover{background:#eef3f8}
    strong{color:#0a3d62}
    em{color:#777;font-size:13px}
    a{color:#0a6cb3;text-decoration:none}
    a:hover{text-decoration:underline}
    hr{border:none;border-top:1px solid #ddd;margin:30px 0}
    .tag{display:inline-block;background:#0a3d62;color:#fff;padding:2px 10px;
      border-radius:12px;font-size:12px;letter-spacing:.5px}
    .lede{margin:18px 0 6px;padding:16px 18px;background:#fff;border:1px solid #e1e1ee;
      border-left:4px solid #0a3d62;border-radius:8px;font-size:14.5px;color:#33384a;
      box-shadow:0 1px 3px rgba(10,61,98,.06)}
    .lede a{font-weight:600}
    """
    body, in_tbl, lede_done = [], False, False

    def inline(s):
        s = html.escape(s)
        while "**" in s:
            s = s.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
        return s

    for ln in md.split("\n"):
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-:| "):
                continue
            if not in_tbl:
                body.append("<table><thead><tr>"
                            + "".join(f"<th>{inline(c)}</th>" for c in cells)
                            + "</tr></thead><tbody>")
                in_tbl = True
            else:
                body.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_tbl:
            body.append("</tbody></table>"); in_tbl = False
        if ln.lstrip().startswith("<"):     # raw HTML passthrough (embedded charts)
            body.append(ln); continue
        if ln.startswith("# "):
            body.append(f"<h1>{inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            body.append(f"<h2>{inline(ln[3:])}</h2>")
        elif ln.startswith("### "):
            body.append(f"<h3>{inline(ln[4:])}</h3>")
        elif ln.startswith("- "):
            body.append(f"<p style='margin:4px 0'>• {inline(ln[2:])}</p>")
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
                body.append(f"<em>{inline(ln.strip('*'))}</em>")
        elif ln.strip():
            body.append(f"<p>{inline(ln)}</p>")
    if in_tbl:
        body.append("</tbody></table>")
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>WC2026 Model Report · {date}</title><style>{css}</style></head>"
            f"<body><div class='tag'>AUTO-GENERATED · {date}</div>"
            + "\n".join(body) + "</body></html>")


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
