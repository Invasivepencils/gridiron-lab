from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from math import erf, isfinite, log, sqrt
from random import Random


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamps must include a timezone")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class Game:
    game_id: str
    season: int
    week: int
    kickoff: datetime
    home: str
    away: str
    home_score: float | None
    away_score: float | None
    result_available_at: datetime | None
    neutral: bool = False

    def __post_init__(self):
        if not self.game_id or not self.home or not self.away or self.home == self.away:
            raise ValueError("Game needs an ID and two distinct teams")
        if (self.home_score is None) != (self.away_score is None):
            raise ValueError("Scores must both be present or absent")
        for score in (self.home_score, self.away_score):
            if score is not None and (not isfinite(score) or score < 0):
                raise ValueError("Scores must be finite and nonnegative")
        if self.home_score is not None:
            if self.result_available_at is None or self.result_available_at <= self.kickoff:
                raise ValueError("Results require availability after kickoff")


@dataclass(frozen=True)
class Injury:
    game_id: str
    team: str
    player_id: str
    observed_at: datetime
    absence_probability: float
    impact_points: float
    impact_sd: float
    impact_available_at: datetime
    source: str

    def __post_init__(self):
        if not all(isfinite(x) for x in (self.absence_probability, self.impact_points, self.impact_sd)):
            raise ValueError("Injury inputs must be finite")
        if not 0 <= self.absence_probability <= 1 or self.impact_points < 0 or self.impact_sd < 0:
            raise ValueError("Invalid probability or impact")
        if not self.player_id or not self.source:
            raise ValueError("Player ID and source are required")


class StrengthModel:
    """Online point-margin ratings with uncalibrated default hyperparameters."""
    def __init__(self, learning_rate=0.08, home_advantage=1.5, margin_sd=13.5):
        self.ratings = {}
        self.learning_rate = learning_rate
        self.home_advantage = home_advantage
        self.margin_sd = margin_sd
        self.season = None

    def start_season(self, season):
        if self.season is not None and season < self.season:
            raise ValueError("Seasons must be chronological")
        if self.season is not None and season != self.season:
            self.ratings = {t: r * 0.7 ** (season - self.season) for t, r in self.ratings.items()}
        self.season = season

    def margin(self, game):
        return (self.ratings.get(game.home, 0) - self.ratings.get(game.away, 0)
                + (0 if game.neutral else self.home_advantage))

    def update(self, game):
        error = game.home_score - game.away_score - self.margin(game)
        change = self.learning_rate * max(-28, min(28, error))
        self.ratings[game.home] = self.ratings.get(game.home, 0) + change
        self.ratings[game.away] = self.ratings.get(game.away, 0) - change


def probability(margin, sd):
    return 0.5 * (1 + erf(margin / (sd * sqrt(2))))


def snapshot(game, injuries, cutoff):
    latest = {}
    for injury in injuries:
        if injury.game_id != game.game_id or injury.observed_at > cutoff:
            continue
        if injury.team not in (game.home, game.away):
            raise ValueError("Injury team is not in this matchup")
        if injury.impact_available_at > cutoff:
            raise ValueError("Player impact was not available at forecast cutoff")
        key = (injury.team, injury.player_id)
        if key in latest and latest[key].observed_at == injury.observed_at:
            raise ValueError("Duplicate player report at same timestamp")
        if key not in latest or injury.observed_at > latest[key].observed_at:
            latest[key] = injury
    return list(latest.values())


def forecast(model, game, injuries, cutoff, simulations=10000, seed=7):
    if cutoff >= game.kickoff:
        raise ValueError("Forecast cutoff must be before kickoff")
    if simulations < 100:
        raise ValueError("Use at least 100 simulations")
    selected = snapshot(game, injuries, cutoff)
    margin = model.margin(game)
    baseline = probability(margin, model.margin_sd)
    rng = Random(seed)
    samples = []
    for _ in range(simulations):
        adjusted = margin
        for injury in selected:
            if rng.random() < injury.absence_probability:
                effect = max(0, rng.gauss(injury.impact_points, injury.impact_sd))
                adjusted += -effect if injury.team == game.home else effect
        # Integrate game-level Gaussian noise; sample uncertain injury scenarios.
        samples.append(probability(adjusted, model.margin_sd))
    adjusted = sum(samples) / simulations
    variance = sum((p - adjusted) ** 2 for p in samples) / (simulations - 1)
    ordered = sorted(samples)
    players = []
    for injury in selected:
        signed = -injury.impact_points if injury.team == game.home else injury.impact_points
        players.append({"player_id": injury.player_id, "team": injury.team,
                        "absence_probability": injury.absence_probability,
                        "assumed_impact_points": injury.impact_points,
                        "isolated_absence_home_probability_change":
                        probability(margin + signed, model.margin_sd) - baseline})
    return {"game_id": game.game_id, "cutoff": cutoff.isoformat(),
            "home": game.home, "away": game.away,
            "baseline_home_probability": baseline,
            "injury_adjusted_home_probability": adjusted,
            "injury_change_percentage_points": 100 * (adjusted - baseline),
            "monte_carlo_standard_error": sqrt(variance / simulations),
            "injury_scenario_probability_p05": ordered[int(0.05 * (simulations - 1))],
            "injury_scenario_probability_p95": ordered[int(0.95 * (simulations - 1))],
            "injury_reports_used": len(selected), "players": players,
            "model_status": "uncalibrated baseline; supplied player-impact assumptions"}


def fit_before(games, cutoff, target_season):
    model = StrengthModel()
    eligible = sorted((g for g in games if g.home_score is not None and g.result_available_at < cutoff),
                      key=lambda g: (g.season, g.kickoff, g.game_id))
    for game in eligible:
        model.start_season(game.season)
        model.update(game)
    model.start_season(target_season)
    return model


def metrics(rows, field):
    eligible = [r for r in rows if r["outcome"] is not None]
    if not eligible:
        return {"games": 0}
    brier = sum((r[field] - r["outcome"]) ** 2 for r in eligible) / len(eligible)
    loss = 0
    bins = []
    for row in eligible:
        p = max(1e-12, min(1 - 1e-12, row[field]))
        loss -= row["outcome"] * log(p) + (1 - row["outcome"]) * log(1 - p)
    for index in range(10):
        bucket = [r for r in eligible if min(9, int(r[field] * 10)) == index]
        if bucket:
            bins.append({"lower": index / 10, "count": len(bucket),
                         "mean_probability": sum(r[field] for r in bucket) / len(bucket),
                         "observed_home_win_rate": sum(r["outcome"] for r in bucket) / len(bucket)})
    return {"games": len(eligible), "brier": brier, "log_loss": loss / len(eligible), "calibration_bins": bins}


def backtest(games, injuries, hours_before=24, simulations=2000, seed=7):
    if hours_before <= 0:
        raise ValueError("Forecast horizon must be positive")
    rows = []
    for game in sorted(games, key=lambda g: (g.kickoff, g.game_id)):
        if game.home_score is None:
            continue
        cutoff = game.kickoff - timedelta(hours=hours_before)
        model = fit_before(games, cutoff, game.season)
        row = forecast(model, game, injuries, cutoff, simulations, seed)
        row.update(season=game.season, week=game.week,
                   outcome=None if game.home_score == game.away_score else int(game.home_score > game.away_score))
        rows.append(row)
    covered = [r for r in rows if r["injury_reports_used"] > 0]
    return {"forecasts": rows,
            "baseline_all": metrics(rows, "baseline_home_probability"),
            "baseline_with_injury_coverage": metrics(covered, "baseline_home_probability"),
            "adjusted_with_injury_coverage": metrics(covered, "injury_adjusted_home_probability"),
            "tie_games_excluded_from_binary_scoring": sum(r["outcome"] is None for r in rows),
            "injury_coverage_games": len(covered),
            "limitations": ["No fitted player effects or calibrated absence probabilities",
                            "Scenario quantiles are not posterior confidence intervals",
                            "Ratings reflect historical availability; effects may double count",
                            "Independent absences; no injury interactions or rating uncertainty",
                            "Binary scoring excludes ties; settlement needs separate handling",
                            "Revised data does not prove historical point-in-time availability"]}
