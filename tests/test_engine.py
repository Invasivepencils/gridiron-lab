import unittest
from dataclasses import replace
from gridiron_lab.data import read_games, read_injuries
from gridiron_lab.engine import StrengthModel, backtest, fit_before, forecast, snapshot, timestamp


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.games = read_games('examples/games.csv')
        self.injuries = read_injuries('examples/injuries.csv')
        self.game = self.games[2]
        self.cutoff = timestamp('2024-09-21T17:00:00Z')

    def test_future_results_cannot_change_forecast(self):
        before = fit_before(self.games, self.cutoff, 2024).margin(self.game)
        modified = [replace(g, home_score=99) if g.game_id == self.game.game_id else g for g in self.games]
        self.assertEqual(before, fit_before(modified, self.cutoff, 2024).margin(self.game))

    def test_delayed_result_is_unavailable(self):
        modified = [replace(g, result_available_at=timestamp('2024-10-01T12:00:00Z')) for g in self.games if g.home_score is not None]
        self.assertEqual(fit_before(modified, self.cutoff, 2024).ratings, {})

    def test_late_report_excluded(self):
        reports = snapshot(self.game, self.injuries, self.cutoff)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].absence_probability, 0.9)

    def test_future_effect_rejected(self):
        injury = replace(self.injuries[0], impact_available_at=timestamp('2025-01-01T00:00:00Z'))
        with self.assertRaises(ValueError):
            snapshot(self.game, [injury], self.cutoff)

    def test_absence_direction_and_determinism(self):
        injury = replace(self.injuries[0], absence_probability=1, impact_sd=0)
        home = forecast(StrengthModel(), self.game, [injury], self.cutoff, 100)
        away = forecast(StrengthModel(), self.game, [replace(injury, team=self.game.away)], self.cutoff, 100)
        self.assertLess(home['injury_change_percentage_points'], 0)
        self.assertGreater(away['injury_change_percentage_points'], 0)
        self.assertEqual(home, forecast(StrengthModel(), self.game, [injury], self.cutoff, 100))

    def test_no_injury_matches_baseline(self):
        row = forecast(StrengthModel(), self.game, [], self.cutoff, 100)
        self.assertAlmostEqual(row['baseline_home_probability'], row['injury_adjusted_home_probability'])

    def test_ties_and_missing_coverage(self):
        games = [replace(self.games[0], away_score=self.games[0].home_score)]
        report = backtest(games, [], simulations=100)
        self.assertEqual(report['baseline_all']['games'], 0)
        self.assertEqual(report['tie_games_excluded_from_binary_scoring'], 1)
        self.assertEqual(report['injury_coverage_games'], 0)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            replace(self.injuries[0], absence_probability=1.2)
        with self.assertRaises(ValueError):
            timestamp('2024-09-21T17:00:00')
        with self.assertRaises(ValueError):
            forecast(StrengthModel(), self.game, [], self.game.kickoff, 100)


if __name__ == '__main__':
    unittest.main()
