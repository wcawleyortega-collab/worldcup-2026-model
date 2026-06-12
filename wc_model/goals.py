"""Match engine: Elo win expectancy -> expected goals -> Dixon-Coles score matrix.

Following the standard academic bridge (Csató 2025; football-rankings.info):
expected goals for a team are a smooth function of its pre-match Elo win
expectancy. We fit a Poisson GLM with a cubic polynomial in W_e plus a
home-venue dummy by maximum likelihood, then correct the joint score
distribution for low-score dependence with the Dixon-Coles tau term
(rho estimated by ML on the same sample).
"""

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import poisson

MAX_GOALS = 12  # score matrix support 0..MAX_GOALS


def _design(we, home_flag):
    we = np.asarray(we, dtype=float)
    home_flag = np.asarray(home_flag, dtype=float)
    return np.column_stack([np.ones_like(we), we, we**2, we**3, home_flag])


class GoalsModel:
    def __init__(self):
        self.beta = None  # GLM coefficients (log link)
        self.rho = 0.0    # Dixon-Coles low-score correction

    # ---- fitting -----------------------------------------------------------
    def fit(self, elo_log, since="1990-01-01"):
        df = elo_log[elo_log["date"] >= since]
        # two rows per match: (team perspective, opponent perspective)
        we = np.concatenate([df["we_home"].values, 1 - df["we_home"].values])
        goals = np.concatenate([df["home_score"].values, df["away_score"].values])
        is_home = ~df["neutral"].values
        home_flag = np.concatenate([is_home.astype(float), -is_home.astype(float)])

        X = _design(we, home_flag)
        y = goals.astype(float)

        def nll(beta):
            eta = X @ beta
            lam = np.exp(np.clip(eta, -10, 3))
            return -(y * eta - lam).sum()

        beta0 = np.zeros(X.shape[1])
        beta0[0] = np.log(max(y.mean(), 0.1))
        res = minimize(nll, beta0, method="L-BFGS-B")
        if not res.success:
            raise RuntimeError(f"Poisson GLM failed: {res.message}")
        self.beta = res.x

        self._fit_rho(df)
        return self

    def _fit_rho(self, df):
        lam_h = self._lambda(df["we_home"].values, np.where(df["neutral"].values, 0.0, 1.0))
        lam_a = self._lambda(1 - df["we_home"].values, np.where(df["neutral"].values, 0.0, -1.0))
        x = df["home_score"].values
        y = df["away_score"].values

        def nll(rho):
            tau = np.ones_like(lam_h)
            m00 = (x == 0) & (y == 0)
            m01 = (x == 0) & (y == 1)
            m10 = (x == 1) & (y == 0)
            m11 = (x == 1) & (y == 1)
            tau[m00] = 1 - lam_h[m00] * lam_a[m00] * rho
            tau[m01] = 1 + lam_h[m01] * rho
            tau[m10] = 1 + lam_a[m10] * rho
            tau[m11] = 1 - rho
            if (tau <= 0).any():
                return 1e12
            return -np.log(tau).sum()

        res = minimize_scalar(nll, bounds=(-0.3, 0.3), method="bounded")
        self.rho = float(res.x)

    # ---- prediction --------------------------------------------------------
    def _lambda(self, we, home_flag):
        return np.exp(_design(we, home_flag) @ self.beta)

    def expected_goals(self, we_a: float, a_at_home: bool = False) -> tuple[float, float]:
        """(lambda_A, lambda_B) given A's win expectancy; a_at_home for non-neutral."""
        h = 1.0 if a_at_home else 0.0
        lam_a = float(self._lambda([we_a], [h])[0])
        lam_b = float(self._lambda([1 - we_a], [-h])[0])
        return lam_a, lam_b

    def score_matrix(self, lam_a: float, lam_b: float) -> np.ndarray:
        """Joint P(A scores i, B scores j) with Dixon-Coles correction."""
        k = np.arange(MAX_GOALS + 1)
        pa = poisson.pmf(k, lam_a)
        pb = poisson.pmf(k, lam_b)
        m = np.outer(pa, pb)
        rho = self.rho
        m[0, 0] *= 1 - lam_a * lam_b * rho
        m[0, 1] *= 1 + lam_a * rho
        m[1, 0] *= 1 + lam_b * rho
        m[1, 1] *= 1 - rho
        np.maximum(m, 0, out=m)
        return m / m.sum()

    def outcome_probs(self, we_a: float, a_at_home: bool = False) -> tuple[float, float, float]:
        """(P win A, P draw, P win B)."""
        m = self.score_matrix(*self.expected_goals(we_a, a_at_home))
        return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())
