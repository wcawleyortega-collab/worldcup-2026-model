"""2026 FIFA World Cup structure and Monte Carlo simulation.

Format: 12 groups of 4; top two plus the 8 best third-placed teams advance to a
round of 32, then R16/QF/SF/Final (104 matches). Groups verified against the
Dec 2025 draw + March 2026 playoff results; bracket per the official FIFA
schedule (matches 73-104).

Third-place allocation: FIFA publishes a 495-row lookup table keyed on which 8
groups supply thirds. We reproduce it as a constraint-satisfaction problem:
each of the 8 third-place bracket slots admits thirds only from a fixed set of
groups; we backtrack to a feasible perfect matching (best-ranked third gets
first pick), which matches FIFA's table up to permutations within constraints.
"""

import numpy as np

from .elo import HOME_ADV, win_expectancy

GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    "B": ["Canada", "Switzerland", "Qatar", "Bosnia and Herzegovina"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

HOSTS = {"United States", "Mexico", "Canada"}

# Round of 32, official matches 73-88. Slots: ("W","A")=winner of group A,
# ("R","A")=runner-up, ("3", "ABCDF")=third from one of those groups.
R32 = {
    73: (("R", "A"), ("R", "B")),
    74: (("W", "E"), ("3", "ABCDF")),
    75: (("W", "F"), ("R", "C")),
    76: (("W", "C"), ("R", "F")),
    77: (("W", "I"), ("3", "CDFGH")),
    78: (("R", "E"), ("R", "I")),
    79: (("W", "A"), ("3", "CEFHI")),
    80: (("W", "L"), ("3", "EHIJK")),
    81: (("W", "D"), ("3", "BEFIJ")),
    82: (("W", "G"), ("3", "AEHIJ")),
    83: (("R", "K"), ("R", "L")),
    84: (("W", "H"), ("R", "J")),
    85: (("W", "B"), ("3", "EFGIJ")),
    86: (("W", "J"), ("R", "H")),
    87: (("W", "K"), ("3", "DEIJL")),
    88: (("R", "D"), ("R", "G")),
}
R16 = {89: (74, 77), 90: (73, 75), 91: (76, 78), 92: (79, 80),
       93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87)}
QF = {97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96)}
SF = {101: (97, 98), 102: (99, 100)}
FINAL = {104: (101, 102)}

THIRD_SLOTS = [m for m, pair in sorted(R32.items()) if pair[1][0] == "3"]

ROUNDS = ["group", "r32", "r16", "qf", "sf", "final", "champion"]


def allocate_thirds(qualified_groups: list[str]) -> dict[int, str] | None:
    """Backtracking perfect matching of 8 third-placed groups to bracket slots.

    qualified_groups is ordered best-ranked first; better thirds are tried in
    slots in match order, so the assignment is deterministic given the ranking.
    """
    slots = sorted(THIRD_SLOTS, key=lambda m: len(R32[m][1][1]))  # most constrained first
    assignment: dict[int, str] = {}

    def backtrack(i: int) -> bool:
        if i == len(slots):
            return True
        m = slots[i]
        allowed = R32[m][1][1]
        for g in qualified_groups:
            if g in allowed and g not in assignment.values():
                assignment[m] = g
                if backtrack(i + 1):
                    return True
                del assignment[m]
        return False

    return assignment if backtrack(0) else None


class Simulator:
    """Monte Carlo simulation of the full 2026 tournament."""

    def __init__(self, ratings: dict, goals_model, group_fixtures, regional_bonus: float = 33.0,
                 seed: int = 2026):
        """group_fixtures: list of (home_team, away_team, neutral) for all 72 group games.
        regional_bonus: Elo points for non-host CONCACAF sides on neutral US/MEX/CAN
        soil (~1/3 of home advantage, following FiveThirtyEight's 2018 treatment).
        """
        self.ratings = ratings
        self.gm = goals_model
        self.rng = np.random.default_rng(seed)
        self.group_fixtures = group_fixtures
        self.regional = {"Panama", "Haiti", "Curaçao"}
        self.regional_bonus = regional_bonus
        self.team_group = {t: g for g, ts in GROUPS.items() for t in ts}
        self._matrix_cache: dict = {}
        self._ko_results: dict = {}

    # ---- match-level -------------------------------------------------------
    def _dr(self, a: str, b: str, a_home: bool) -> float:
        dr = self.ratings[a] - self.ratings[b]
        if a_home:
            dr += HOME_ADV
        else:
            dr += self.regional_bonus * ((a in self.regional) - (b in self.regional))
        return dr

    def match_dist(self, a: str, b: str, a_home: bool):
        """Cached (score_matrix flattened cumsum, n) for sampling; plus lambdas."""
        key = (a, b, a_home)
        if key not in self._matrix_cache:
            we = win_expectancy(self._dr(a, b, a_home))
            lam_a, lam_b = self.gm.expected_goals(we, a_home)
            m = self.gm.score_matrix(lam_a, lam_b)
            self._matrix_cache[key] = (m.ravel().cumsum(), m.shape[1], lam_a, lam_b)
        return self._matrix_cache[key]

    def sample_score(self, a: str, b: str, a_home: bool, n: int = 1):
        cum, ncol, _, _ = self.match_dist(a, b, a_home)
        idx = np.searchsorted(cum, self.rng.random(n))
        return idx // ncol, idx % ncol

    def sample_knockout(self, a: str, b: str, a_home: bool) -> str:
        ga, gb = self.sample_score(a, b, a_home, 1)
        if ga[0] != gb[0]:
            return a if ga[0] > gb[0] else b
        # extra time at ~1/3 of 90' scoring rates, then shootout with tiny Elo tilt
        _, _, lam_a, lam_b = self.match_dist(a, b, a_home)
        ea, eb = self.rng.poisson(lam_a / 3), self.rng.poisson(lam_b / 3)
        if ea != eb:
            return a if ea > eb else b
        p_a = win_expectancy((self.ratings[a] - self.ratings[b]) / 5.0)
        return a if self.rng.random() < p_a else b

    # ---- tournament --------------------------------------------------------
    def simulate(self, n_sims: int = 20000, played: dict | None = None,
                 ko_results: dict | None = None, alloc_override: dict | None = None) -> dict:
        """Returns reach[team][round] counts and group-position counts.

        played: {(home, away): (hs, as)} actual scores for completed group games
            (held fixed in every simulation).
        ko_results: {frozenset({a, b}): winner} completed knockout matches.
        alloc_override: {r32_match: group} real third-place slotting once FIFA
            publishes the actual round-of-32 pairings.
        """
        played = played or {}
        self._ko_results = ko_results or {}
        # Pre-sample all 72 group fixtures vectorized; played ones are constant.
        fixtures = self.group_fixtures
        scores = []
        for h, a, neu in fixtures:
            if (h, a) in played:
                hs, as_ = played[(h, a)]
                scores.append((np.full(n_sims, hs), np.full(n_sims, as_)))
            else:
                scores.append(self.sample_score(h, a, not neu, n_sims))

        reach = {t: dict.fromkeys(ROUNDS, 0) for ts in GROUPS.values() for t in ts}
        positions = {t: [0, 0, 0, 0] for t in reach}

        for s in range(n_sims):
            # group standings: points, GD, GF (+ random jitter for fair play/lots)
            stats = {t: [0, 0, 0] for t in reach}
            for (h, a, _), (gh, ga) in zip(fixtures, scores):
                x, y = int(gh[s]), int(ga[s])
                stats[h][1] += x - y; stats[h][2] += x
                stats[a][1] += y - x; stats[a][2] += y
                if x > y:
                    stats[h][0] += 3
                elif x < y:
                    stats[a][0] += 3
                else:
                    stats[h][0] += 1; stats[a][0] += 1

            winners, runners, thirds = {}, {}, []
            for g, teams in GROUPS.items():
                order = sorted(teams, key=lambda t: (stats[t][0], stats[t][1], stats[t][2],
                                                     self.rng.random()), reverse=True)
                winners[g], runners[g] = order[0], order[1]
                thirds.append((g, order[2]))
                for pos, t in enumerate(order):
                    positions[t][pos] += 1
                for t in teams:
                    reach[t]["group"] += 1

            # best 8 thirds: points, GD, GF, jitter
            thirds.sort(key=lambda gt: (stats[gt[1]][0], stats[gt[1]][1], stats[gt[1]][2],
                                        self.rng.random()), reverse=True)
            qualified = thirds[:8]
            third_of = dict(qualified)
            if alloc_override is not None:
                alloc = alloc_override
                third_of = dict(thirds)  # real slotting may include any group's third
            else:
                alloc = allocate_thirds([g for g, _ in qualified])
                if alloc is None:  # should not happen; FIFA table covers all 495 combos
                    alloc = {m: g for m, (g, _) in zip(THIRD_SLOTS, qualified)}

            mw = {}  # match -> winner
            for m, (s1, s2) in R32.items():
                t1 = winners[s1[1]] if s1[0] == "W" else runners[s1[1]]
                if s2[0] == "3":
                    t2 = third_of[alloc[m]]
                else:
                    t2 = runners[s2[1]]
                reach[t1]["r32"] += 1; reach[t2]["r32"] += 1
                mw[m] = self._ko(t1, t2)

            for stage, table in (("r16", R16), ("qf", QF), ("sf", SF), ("final", FINAL)):
                for m, (m1, m2) in table.items():
                    t1, t2 = mw[m1], mw[m2]
                    reach[t1][stage] += 1; reach[t2][stage] += 1
                    mw[m] = self._ko(t1, t2)
            reach[mw[104]]["champion"] += 1

        return {"reach": reach, "positions": positions, "n": n_sims}

    def _ko(self, t1: str, t2: str) -> str:
        decided = self._ko_results.get(frozenset((t1, t2)))
        if decided is not None:
            return decided
        home = t1 in HOSTS and t2 not in HOSTS
        away = t2 in HOSTS and t1 not in HOSTS
        if away:
            return self.sample_knockout(t2, t1, True)
        return self.sample_knockout(t1, t2, home)
