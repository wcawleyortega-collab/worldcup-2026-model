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

import datetime
import html
import os

import numpy as np
import pandas as pd

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


# ---------------------------------------------------------------- rendering
def _fmt_pct(x):
    return f"{x:.1%}" if pd.notna(x) else "—"


def build_markdown(date, lb, day, fx, skill, cal, adv, bet):
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


def main():
    date = datetime.date.today().isoformat()
    lb = leaderboard()
    day, fx = next_fixtures()
    skill, cal = match_skill()
    adv = advancement_skill()
    bet = betting_ledger()
    md = build_markdown(date, lb, day, fx, skill, cal, adv, bet)
    page = md_to_html(md, date)
    with open(os.path.join(OUT, "report.md"), "w") as f:
        f.write(md)
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
