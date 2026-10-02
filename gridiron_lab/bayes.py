"""Conjugate Bayesian score-margin regression with joint team covariance."""
from dataclasses import dataclass
import numpy as np
from scipy.stats import t
from .engine import snapshot


@dataclass
class Posterior:
    teams: list[str]
    mean: np.ndarray
    cholesky: np.ndarray
    alpha: float
    beta: float
    training_games: int

    def vector(self, game):
        x = np.zeros(len(self.teams) + 1)
        x[self.teams.index(game.home)] = 1
        x[self.teams.index(game.away)] = -1
        x[-1] = 0 if game.neutral else 1
        return x

    def predictive(self, x):
        projected = np.linalg.solve(self.cholesky, x)
        scale = np.sqrt(self.beta / self.alpha * (1 + projected @ projected))
        return float(x @ self.mean), float(scale), 2 * self.alpha


def fit(games, target, cutoff, prior_precision=4.0):
    """Fit only the target season's usable results; zero-centered strength priors.

    Using a proper prior resolves the nonidentifiability of team contrasts.
    The home-field coefficient has a 1.5-point prior mean. Noise precision has
    Gamma(3, 2*13.5**2) prior. No tuning on held-out outcomes.
    """
    if not np.isfinite(prior_precision) or prior_precision <= 0:
        raise ValueError('Prior precision must be finite and positive')
    usable = [g for g in games if g.season == target.season and g.home_score is not None
              and g.result_available_at < cutoff]
    teams = sorted({target.home, target.away} | {team for g in usable for team in (g.home, g.away)})
    dim = len(teams) + 1
    prior = np.eye(dim) * prior_precision
    prior[-1,-1] = 1.0
    m0 = np.zeros(dim)
    m0[-1] = 1.5
    X = np.zeros((len(usable), dim))
    y = np.empty(len(usable))
    for index, game in enumerate(usable):
        X[index, teams.index(game.home)] = 1
        X[index, teams.index(game.away)] = -1
        X[index,-1] = 0 if game.neutral else 1
        y[index] = game.home_score - game.away_score
    precision = prior + X.T @ X
    L = np.linalg.cholesky(precision)
    mean = np.linalg.solve(L.T, np.linalg.solve(L, prior @ m0 + X.T @ y))
    alpha = 3.0 + len(y)/2
    # Residual form avoids catastrophic cancellation in y'y - m'Lambda*m.
    residual = y - X @ mean
    delta = mean - m0
    beta = 2 * 13.5**2 + 0.5 * (residual @ residual + delta @ prior @ delta)
    return Posterior(teams, mean, L, alpha, float(beta), len(usable))


def predict(posterior, game, injuries, cutoff, simulations=10000, seed=7):
    if cutoff >= game.kickoff or simulations < 100:
        raise ValueError('Use a pregame cutoff and at least 100 simulations')
    x = posterior.vector(game)
    center, scale, df = posterior.predictive(x)
    baseline = float(t.cdf(center / scale, df))
    selected = snapshot(game, injuries, cutoff)
    rng = np.random.default_rng(seed)
    adjustments = np.zeros(simulations)
    players = []
    for injury in selected:
        sign = -1 if injury.team == game.home else 1
        absent = rng.random(simulations) < injury.absence_probability
        effect = np.maximum(0, rng.normal(injury.impact_points, injury.impact_sd, simulations))
        adjustments += sign * absent * effect
        players.append({'player_id': injury.player_id, 'team': injury.team,
                        'absence_probability': injury.absence_probability,
                        'assumed_impact_points': injury.impact_points,
                        'isolated_absence_home_probability_change':
                        float(t.cdf((center + sign*injury.impact_points)/scale, df)) - baseline})
    scenario_p = t.cdf((center + adjustments)/scale, df)
    # Each draw uses one common noise variance and jointly sampled coefficients.
    sigma2 = 1 / rng.gamma(posterior.alpha, 1/posterior.beta, simulations)
    normals = rng.normal(size=(len(posterior.mean), simulations))
    coefficients = posterior.mean[:,None] + np.linalg.solve(posterior.cholesky.T, normals) * np.sqrt(sigma2)
    margins = x @ coefficients + rng.normal(size=simulations)*np.sqrt(sigma2) + adjustments
    return {'game_id': game.game_id, 'cutoff': cutoff.isoformat(), 'home':game.home, 'away':game.away,
            'baseline_home_probability': baseline,
            'injury_adjusted_home_probability': float(np.mean(scenario_p)),
            'injury_change_percentage_points': float(100*(np.mean(scenario_p)-baseline)),
            'monte_carlo_standard_error': float(np.std(scenario_p,ddof=1)/np.sqrt(simulations)),
            'injury_scenario_probability_p05':float(np.quantile(scenario_p,.05)),
            'injury_scenario_probability_p95':float(np.quantile(scenario_p,.95)),
            'predicted_home_margin': center,
            'predictive_margin_p05':float(np.quantile(margins,.05)),
            'predictive_margin_p95':float(np.quantile(margins,.95)),
            'student_t_degrees_of_freedom':df, 'training_games':posterior.training_games,
            'injury_reports_used':len(selected), 'players':players,
            'model_status':'Bayesian team contrasts; injury effects are supplied scenario assumptions'}
