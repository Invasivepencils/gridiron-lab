import unittest
from gridiron_lab.history import attribution, availability_posterior, record_summary

class HistoryTests(unittest.TestCase):
    def play(self,**kwargs):
        return {'posteam':'BUF','defteam':'NYJ','play_type':'pass','passer_player_id':'qb','receiver_player_id':'wr',**kwargs}

    def test_pass_credit_conserves_team_budget(self):
        credits=attribution(self.play(solo_tackle_1_team='NYJ',solo_tackle_1_player_id='db'))
        self.assertEqual(credits,[('qb','BUF','Offense',.5),('wr','BUF','Offense',.5),('db','NYJ','Defense',-1)])

    def test_turnover_credit_not_double_counted(self):
        c=attribution(self.play(interception='1',interception_player_id='db'))
        self.assertEqual(c,[('qb','BUF','Offense',1),('db','NYJ','Defense',-1)])

    def test_split_sacks_unique(self):
        c=attribution(self.play(sack='1',half_sack_1_player_id='a',half_sack_2_player_id='b'))
        self.assertEqual(sum(w for _,t,_,w in c if t=='NYJ'),-1)
        self.assertEqual(len(c),3)

    def test_penalty_kneel_spike_excluded(self):
        for flag in ['no_play','qb_kneel','qb_spike']:
            self.assertEqual(attribution(self.play(**{flag:'1'})),[])

    def test_special_teams_signs(self):
        c=attribution(self.play(play_type='punt',punter_player_id='p',punt_returner_player_id='r'))
        self.assertEqual(c,[('p','BUF','Special teams',1),('r','NYJ','Special teams',-1)])

    def test_kickoff_possession_is_receiving_team(self):
        c=attribution(self.play(play_type='kickoff',kicker_player_id='k',kickoff_returner_player_id='r'))
        self.assertEqual(c,[('k','NYJ','Special teams',-1),('r','BUF','Special teams',1)])

    def test_small_samples_are_not_zero_effects(self):
        self.assertIsNone(availability_posterior([20]*17,[]))
        self.assertIsNone(availability_posterior([20]*3,[-20]))

    def test_opposite_associations_and_shrinkage(self):
        a=availability_posterior([10]*8,[-10]*8)
        b=availability_posterior([-10]*8,[10]*8)
        self.assertGreater(a['effect'],0)
        self.assertLess(a['effect'],20)
        self.assertAlmostEqual(a['effect'],-b['effect'],delta=.3)
        self.assertGreater(a['high'],a['low'])

    def test_win_rate_intervals_and_ties(self):
        r=record_summary([{'margin':3},{'margin':0},{'margin':-3}])
        self.assertEqual((r['wins'],r['ties'],r['games']),(1,1,3))
        self.assertLess(r['win_interval'][0],.5)
        self.assertGreater(r['win_interval'][1],.5)

if __name__=='__main__':unittest.main()
