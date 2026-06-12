"""Snapshot Polymarket 2026 World Cup prices into data/polymarket_history.csv.

Logged markets (Gamma API, no auth):
- "World Cup: Team to advance to Knockout Stages" — 48 Yes/No markets
- "World Cup Group {A..L} Winner" — 12 multi-outcome events
- "World Cup Winner" — outright tournament winner

Each run appends one row per market with a UTC timestamp; rows are never
overwritten, so intraday snapshots accumulate (the panel for the market-
efficiency study). Run standalone or via update_predictions.py.
"""

import csv
import datetime
import json
import os
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "polymarket_history.csv")
API = "https://gamma-api.polymarket.com/events?slug="

SLUGS = (
    [("advance", "world-cup-team-to-advance-to-knockout-stages"),
     ("outright", "world-cup-winner")]
    + [("group_winner", f"world-cup-group-{g}-winner") for g in "abcdefghijkl"]
)

TEAMS = [
    "Mexico", "South Africa", "South Korea", "Czech Republic", "Canada",
    "Switzerland", "Qatar", "Bosnia and Herzegovina", "Brazil", "Morocco",
    "Haiti", "Scotland", "United States", "Paraguay", "Australia", "Turkey",
    "Germany", "Curaçao", "Ivory Coast", "Ecuador", "Netherlands", "Japan",
    "Sweden", "Tunisia", "Belgium", "Egypt", "Iran", "New Zealand", "Spain",
    "Cape Verde", "Saudi Arabia", "Uruguay", "France", "Senegal", "Iraq",
    "Norway", "Argentina", "Algeria", "Austria", "Jordan", "Portugal",
    "DR Congo", "Uzbekistan", "Colombia", "England", "Croatia", "Ghana", "Panama",
]
ALIASES = {
    "Türkiye": "Turkey", "Turkiye": "Turkey", "Czechia": "Czech Republic",
    "USA": "United States", "Curacao": "Curaçao", "Korea Republic": "South Korea",
    "Bosnia": "Bosnia and Herzegovina", "Côte d'Ivoire": "Ivory Coast",
    "Democratic Republic of Congo": "DR Congo", "Congo DR": "DR Congo",
}
# longest names first so e.g. "South Africa" wins over any shorter substring
_LOOKUP = sorted({**{t: t for t in TEAMS}, **ALIASES}.items(),
                 key=lambda kv: -len(kv[0]))


def team_from(text: str) -> str | None:
    for name, canonical in _LOOKUP:
        if name in text:
            return canonical
    return None


def fetch(slug: str) -> dict | None:
    req = urllib.request.Request(API + slug, headers={"User-Agent": "wc-research/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        events = json.load(r)
    return events[0] if events else None


def snapshot() -> list[dict]:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    rows = []
    for kind, slug in SLUGS:
        try:
            ev = fetch(slug)
        except Exception as e:
            print(f"  warn: {slug}: {e}")
            continue
        if ev is None:
            continue
        for m in ev.get("markets", []):
            team = team_from(m.get("question", "") + " " + m.get("groupItemTitle", ""))
            if team is None:
                continue  # e.g. "Other" outcome
            try:
                yes_price = float(json.loads(m["outcomePrices"])[0])
            except (KeyError, ValueError, IndexError):
                yes_price = None
            rows.append({
                "ts_utc": ts, "market": kind, "team": team,
                "price": yes_price,
                "bid": m.get("bestBid"), "ask": m.get("bestAsk"),
                "last_trade": m.get("lastTradePrice"),
                "volume": m.get("volumeNum"), "liquidity": m.get("liquidityNum"),
                "closed": m.get("closed"),
            })
    return rows


def main():
    rows = snapshot()
    if not rows:
        print("  polymarket: no rows fetched")
        return
    exists = os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        if not exists:
            w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[r["market"]] = counts.get(r["market"], 0) + 1
    print(f"  polymarket: logged {len(rows)} prices {counts}")


if __name__ == "__main__":
    main()
