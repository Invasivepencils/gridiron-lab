"""Retrospective recorded-play attribution and separately reported availability evidence.

No counterfactual win probability or causal player rankings are inferred here.
Run: python -m gridiron_lab.history --raw data/raw --out docs
"""
import argparse
import csv
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import norm, beta

TEAMS = dict(zip(
    'ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(),
    ['Arizona Cardinals','Atlanta Falcons','Baltimore Ravens','Buffalo Bills','Carolina Panthers','Chicago Bears','Cincinnati Bengals','Cleveland Browns','Dallas Cowboys','Denver Broncos','Detroit Lions','Green Bay Packers','Houston Texans','Indianapolis Colts','Jacksonville Jaguars','Kansas City Chiefs','Los Angeles Rams','Los Angeles Chargers','Las Vegas Raiders','Miami Dolphins','Minnesota Vikings','New England Patriots','New Orleans Saints','New York Giants','New York Jets','Philadelphia Eagles','Pittsburgh Steelers','Seattle Seahawks','San Francisco 49ers','Tampa Bay Buccaneers','Tennessee Titans','Washington Commanders']))
OFFENSE = {'QB','RB','FB','WR','TE','T','G','C','OL','OT','OG'}

def number(value):
    try:
        v=float(value)
        return v if np.isfinite(v) else None
    except (TypeError,ValueError): return None

def rows(path):
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        yield from csv.DictReader(f)

def attribution(play):
    """One credit budget per team per play; returns (id,team,unit,weight).

    Ordinary passing plays share credit equally between passer and target. Turnovers
    stay with the passer/carrier. Named defensive finishers share the opposite swing.
    Unnamed coverage, blocking, coaching and penalties receive no invented credit.
    """
    post, defense=play.get('posteam'),play.get('defteam')
    if not post or not defense or play.get('no_play')=='1': return []
    if play.get('qb_kneel')=='1' or play.get('qb_spike')=='1': return []
    kind=play.get('play_type'); result=[]
    def give(ids,team,unit,sign=1):
        ids=sorted({i for i in ids if i and i not in {'NA','00-0000000'}})
        result.extend((i,team,unit,sign/len(ids)) for i in ids)
    if kind in {'field_goal','extra_point'}:
        give([play.get('kicker_player_id')],post,'Special teams')
        if play.get('blocked_player_id'): give([play['blocked_player_id']],defense,'Special teams',-1)
    elif kind=='punt':
        give([play.get('punter_player_id')],post,'Special teams')
        give([play.get('punt_returner_player_id')],defense,'Special teams',-1)
    elif kind=='kickoff':
        # nflverse posteam is the RECEIVING team on kickoffs.
        give([play.get('kicker_player_id')],defense,'Special teams',-1)
        give([play.get('kickoff_returner_player_id')],post,'Special teams')
    elif kind in {'pass','run'}:
        if play.get('fumble_lost')=='1':
            give([play.get('fumbled_1_player_id') or play.get('rusher_player_id') or play.get('passer_player_id')],post,'Offense')
        elif kind=='pass':
            ids=[play.get('passer_player_id')]
            if play.get('interception')!='1' and play.get('sack')!='1':ids.append(play.get('receiver_player_id'))
            give(ids,post,'Offense')
        else: give([play.get('rusher_player_id')],post,'Offense')
        if play.get('interception')=='1': defenders=[play.get('interception_player_id')]
        elif play.get('sack')=='1':defenders=[play.get(k) for k in ['sack_player_id','half_sack_1_player_id','half_sack_2_player_id']]
        elif play.get('fumble_lost')=='1':
            defenders=[play.get(k) for k in ['forced_fumble_player_1_player_id','forced_fumble_player_2_player_id']]
            defenders += [play.get(f'fumble_recovery_{i}_player_id') for i in [1,2] if play.get(f'fumble_recovery_{i}_team')==defense]
        elif play.get('incomplete_pass')=='1':defenders=[play.get('pass_defense_1_player_id'),play.get('pass_defense_2_player_id')]
        else:
            defenders=[play.get(f'{prefix}_{i}_player_id') for prefix,count in [('solo_tackle',2),('assist_tackle',4),('tackle_with_assist',2)] for i in range(1,count+1) if play.get(f'{prefix}_{i}_team')==defense]
        give(defenders,defense,'Defense',-1)
    return result

def availability_posterior(active, limited, prior_sd=7., noise_sd=12.):
    """Normal posterior for between-group adjusted-margin association.

    This conditions on a separately fitted full-season opponent baseline. It does
    not remove teammate confounding or propagate baseline estimation uncertainty.
    """
    if len(active)<3 or len(limited)<2:return None
    y=np.array(active+limited);x=np.column_stack([np.ones(len(y)),np.r_[np.ones(len(active)),np.zeros(len(limited))]])
    precision=np.diag([1/20**2,1/prior_sd**2])+x.T@x/noise_sd**2
    cov=np.linalg.solve(precision,np.eye(2));mean=cov@(x.T@y/noise_sd**2)
    sd=float(np.sqrt(cov[1,1]));effect=float(mean[1])
    return {'effect':round(effect,2),'low':round(effect-1.645*sd,2),'high':round(effect+1.645*sd,2),'prob_positive':round(float(norm.cdf(effect/sd)),3)}

def record_summary(games):
    if not games:return {'games':0,'wins':0,'win_rate':None,'margin':None}
    wins=sum(g['margin']>0 for g in games);ties=sum(g['margin']==0 for g in games)
    n=len(games);a=1+wins;b=1+n-wins-ties
    return {'games':n,'wins':wins,'ties':ties,'win_rate':round(wins/max(1,n-ties),3),'margin':round(float(np.mean([g['margin'] for g in games])),2),'win_interval':[round(float(beta.ppf(q,a,b)),3) for q in [.05,.95]]}

def build_season(raw,season,players):
    games={};events=defaultdict(lambda:{'wpa':0.,'epa':0.,'plays':0,'units':defaultdict(lambda:{'wpa':0.,'epa':0.,'plays':0}),'top':[]})
    count=0;valid=0;seen=set()
    for r in rows(raw/f'play_by_play_{season}.csv.gz'):
        if r['season_type']!='REG':continue
        key=(r['game_id'],r['play_id'])
        if key in seen:raise ValueError('Duplicate play '+str(key))
        seen.add(key);count+=1
        g=games.setdefault(r['game_id'],{'id':r['game_id'],'week':int(r['week']),'home':r['home_team'],'away':r['away_team'],'home_score':number(r['home_score']),'away_score':number(r['away_score'])})
        wpa,epa=number(r['wpa']),number(r['epa'])
        if wpa is None or epa is None:continue
        valid+=1
        for pid,team,unit,weight in attribution(r):
            e=events[(pid,team,g['week'])];e['wpa']+=wpa*weight;e['epa']+=epa*weight;e['plays']+=1;e['units'][unit]['wpa']+=wpa*weight;e['units'][unit]['epa']+=epa*weight;e['units'][unit]['plays']+=1
            e['top'].append({'swing':round(100*wpa*weight,2),'description':r.get('desc',''),'game':g['id'],'play':r['play_id']})
    if len(games)!=272 or any(g['home_score'] is None or g['away_score'] is None for g in games.values()):raise ValueError(f'{season}: incomplete regular-season games')
    teams=sorted(TEAMS);index={t:i for i,t in enumerate(teams)}
    x=np.zeros((len(games),33));y=[]
    for row,g in enumerate(games.values()):
        x[row,index[g['home']]]=1;x[row,index[g['away']]]=-1;x[row,-1]=1;y.append(g['home_score']-g['away_score'])
    # Proper normal prior: ridge team contrasts, home-field prior mean 1.5.
    precision=x.T@x+np.diag([8.]*32+[4.]);rhs=x.T@np.array(y);rhs[-1]+=6
    strength=np.linalg.solve(precision,rhs)
    team_games={}
    for g in games.values():
        for team,opp,home in [(g['home'],g['away'],1),(g['away'],g['home'],-1)]:
            margin=(g['home_score']-g['away_score'])*home
            expected=strength[index[team]]-strength[index[opp]]+home*strength[-1]
            team_games[(team,g['week'])]={'week':g['week'],'game':g['id'],'opponent':opp,'margin':margin,'adjusted_margin':float(margin-expected),'score':f"{int(g['home_score'] if home==1 else g['away_score'])}–{int(g['away_score'] if home==1 else g['home_score'])}",'result':'W' if margin>0 else 'L' if margin<0 else 'T'}
    roster=defaultdict(dict)
    for r in rows(raw/f'roster_weekly_{season}.csv.gz'):
        if r['game_type']!='REG' or not r['gsis_id'] or r['status'] in {'CUT','TRD','RET','DEV'}:continue
        week=int(r['week']);team=r['team'];pid=r['gsis_id']
        if (team,week) not in team_games:continue
        roster[(pid,team)][week]=r['status'];players.setdefault(pid,{'name':r['full_name'],'position':r['position'],'pfr_id':r['pfr_id']})
    by_pfr={p['pfr_id']:pid for pid,p in players.items() if p.get('pfr_id')}
    snaps={};unmatched=0
    for r in rows(raw/f'snap_counts_{season}.csv.gz'):
        if r['game_type']!='REG':continue
        pid=by_pfr.get(r['pfr_player_id']);week=int(r['week']);team=r['team']
        if not pid:unmatched+=1;continue
        snaps[(pid,team,week)]=r
        roster[(pid,team)].setdefault(week,'ACT')
    injuries={};injury_rows=0
    for r in rows(raw/f'injuries_{season}.csv.gz'):
        if r.get('game_type')!='REG':continue
        week=int(r['week']);pid=r['gsis_id'];team=r['team'];injury_rows+=1
        injuries[(pid,team,week)]={'status':r['report_status'] or 'Practice report only','injury':r['report_primary_injury'] or r['practice_primary_injury']}
    unmatched_events=0
    for pid,team,week in list(events):
        if week not in roster.get((pid,team),{}):
            unmatched_events+=1;del events[(pid,team,week)]
    profiles=[]
    for (pid,team),weeks in roster.items():
        p=players.get(pid)
        if not p:continue
        unit='Special teams' if p['position'] in {'K','P','LS'} else 'Offense' if p['position'] in OFFENSE else 'Defense'
        snap_col={'Offense':'offense_pct','Defense':'defense_pct','Special teams':'st_pct'}[unit]
        timeline=[]
        for week,status in sorted(weeks.items()):
            g=team_games.get((team,week))
            if not g:continue
            e=events.get((pid,team,week));s=snaps.get((pid,team,week))
            snap=number(s[snap_col]) if s else None
            inj=injuries.get((pid,team,week));confirmed=bool(status in {'RES','INA'} or (inj and inj['status']=='Out'))
            # No snap row alone is not proof of nonparticipation: keep unknown as null.
            if snap is None and confirmed:snap=0.
            unit_credits={u:{'wpa':round(v['wpa']*100,2),'epa':round(v['epa'],2),'plays':v['plays']} for u,v in e['units'].items()} if e else {}
            timeline.append({**g,'adjusted_margin':round(g['adjusted_margin'],3),'snap':snap,'roster_status':status,'injury':inj,'wpa':round(e['wpa']*100,2) if e else 0.,'epa':round(e['epa'],2) if e else 0.,'plays':e['plays'] if e else 0,'units':unit_credits,'top':sorted(e['top'],key=lambda a:abs(a['swing']),reverse=True)[:2] if e else []})
        if not any(g['plays'] or (g['snap'] or 0)>0 for g in timeline):continue
        threshold=.01 if unit=='Special teams' else .2
        known=[g for g in timeline if g['snap'] is not None];active=[g for g in known if g['snap']>=threshold];limited=[g for g in known if g['snap']<threshold]
        post=availability_posterior([g['adjusted_margin'] for g in active],[g['adjusted_margin'] for g in limited])
        performances=[g for g in timeline if g['plays']>=3];median=float(np.median([g['epa'] for g in performances])) if performances else None
        low=[g for g in performances if g['epa']<median];high=[g for g in performances if g['epa']>=median]
        unit_totals={u:{'wpa':round(sum(g['units'].get(u,{}).get('wpa',0) for g in timeline),2),'epa':round(sum(g['units'].get(u,{}).get('epa',0) for g in timeline),2),'plays':sum(g['units'].get(u,{}).get('plays',0) for g in timeline)} for u in ['Offense','Defense','Special teams']}
        profiles.append({'id':pid+'_'+team,'player_id':pid,'name':p['name'],'position':p['position'],'team':team,'unit':unit,'threshold':threshold,'units':unit_totals,'wpa':round(sum(g['wpa'] for g in timeline),2),'epa':round(sum(g['epa'] for g in timeline),2),'weeks':timeline,'played_games':sum((g['snap'] or 0)>0 or g['plays']>0 for g in timeline),'positive_weeks':sum(g['wpa']>0 for g in timeline),'dependence':post,'active':record_summary(active),'limited':record_summary(limited),'unknown_games':len(timeline)-len(known),'low_performance':record_summary(low),'high_performance':record_summary(high),'performance_median':round(median,2) if median is not None else None})
    profiles.sort(key=lambda p:p['wpa'],reverse=True)
    coverage={'season':season,'games':len(games),'weeks':sorted({g['week'] for g in games.values()}),'plays':count,'modeled_plays':valid,'players':len(profiles),'unmatched_snap_rows':unmatched,'unmatched_player_team_weeks':unmatched_events,'injury_rows':injury_rows}
    return {'season':season,'coverage':coverage,'players':profiles}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--raw',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seasons',type=int,nargs='+',default=[2023,2024,2025]);args=parser.parse_args()
    players={r['gsis_id']:{'name':r['display_name'],'position':r['position'],'pfr_id':r['pfr_id']} for r in rows(args.raw/'players.csv.gz') if r['gsis_id']}
    args.out.mkdir(parents=True,exist_ok=True);coverage=[]
    for season in args.seasons:
        report=build_season(args.raw,season,players);coverage.append(report['coverage'])
        (args.out/f'history-{season}.json').write_text(json.dumps(report,separators=(',',':'),allow_nan=False),encoding='utf-8');print(report['coverage'],flush=True)
    manifest=json.loads((args.raw/'manifest.json').read_text())
    files={str(y):hashlib.sha256((args.out/f'history-{y}.json').read_bytes()).hexdigest()[:12] for y in args.seasons}
    (args.out/'history-index.json').write_text(json.dumps({'seasons':args.seasons,'teams':TEAMS,'coverage':coverage,'sources':manifest,'files':files,'data_license':'CC BY 4.0; nflverse play-by-play, identities, rosters, injuries; PFR snap counts via nflverse. Derived attribution and analysis by Gridiron Lab.'},indent=2))

if __name__=='__main__':main()
