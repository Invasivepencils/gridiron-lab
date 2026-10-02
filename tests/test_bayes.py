import unittest
from dataclasses import replace
from gridiron_lab.data import read_games, read_injuries
from gridiron_lab.engine import timestamp
from gridiron_lab.bayes import fit, predict
import numpy as np


class BayesianTests(unittest.TestCase):
    def setUp(self):
        self.games = read_games('examples/games.csv')
        self.game = self.games[-1]
        self.cutoff = timestamp('2024-09-28T17:00:00Z')

    def test_posterior_matches_normal_equations(self):
        p = fit(self.games,self.game,self.cutoff)
        X = np.array([[1,-1,1],[-1,1,1],[1,-1,1]])
        y = np.array([7,-3,-13])
        prior = np.diag([4,4,1])
        expected = np.linalg.solve(prior+X.T@X, X.T@y+prior@np.array([0,0,1.5]))
        np.testing.assert_allclose(p.mean,expected)
        np.testing.assert_allclose(p.cholesky@p.cholesky.T,prior+X.T@X)

    def test_covariance_projection(self):
        p = fit(self.games,self.game,self.cutoff)
        x = p.vector(self.game)
        _,scale,_ = p.predictive(x)
        expected = p.beta/p.alpha*(1+x@np.linalg.solve(p.cholesky@p.cholesky.T,x))
        self.assertAlmostEqual(scale**2,expected)

    def test_future_results_do_not_change_posterior(self):
        p = fit(self.games,self.game,self.cutoff)
        future = replace(self.game,home_score=99,away_score=0,
                         result_available_at=timestamp('2024-09-30T12:00:00Z'))
        np.testing.assert_allclose(p.mean,fit(self.games+[future],self.game,self.cutoff).mean)

    def test_predictive_uncertainty_and_reproducibility(self):
        p = fit(self.games,self.game,self.cutoff)
        a = predict(p,self.game,[],self.cutoff,1000)
        b = predict(p,self.game,[],self.cutoff,1000)
        self.assertEqual(a,b)
        self.assertAlmostEqual(a['baseline_home_probability'],a['injury_adjusted_home_probability'])
        self.assertLess(a['predictive_margin_p05'],a['predicted_home_margin'])
        self.assertGreater(a['predictive_margin_p95'],a['predicted_home_margin'])

    def test_injury_direction(self):
        p = fit(self.games,self.game,self.cutoff)
        injuries = read_injuries('examples/injuries.csv')
        self.assertGreater(predict(p,self.game,injuries,self.cutoff,1000)['injury_change_percentage_points'],0)

    def test_proper_prior_handles_no_training_games(self):
        p = fit([],self.game,self.cutoff)
        self.assertEqual(p.training_games,0)
        self.assertEqual(p.alpha,3)
        self.assertAlmostEqual(sum(p.mean[:-1]),0)


if __name__ == '__main__': unittest.main()
