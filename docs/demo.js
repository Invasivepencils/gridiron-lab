let research,report;const $=id=>document.getElementById(id);const percent=p=>`${(100*p).toFixed(1)}%`;const fmt=x=>Number(x).toFixed(2);
async function request(action='forecast'){if(!research)throw Error('The demonstration is still loading. Try again shortly.');return action==='backtest'?research.backtest:research.scenarios[`${$('absence').value}:${$('impact').value}`];}
function fail(e){$('error').hidden=false;$('error').textContent=e.message;}
function display(value) {
  report = value; $('output').hidden = false;
  $('matchup').textContent = `${value.away} at ${value.home}`;
  $('baseline').textContent = percent(value.baseline_home_probability);
  $('adjusted').textContent = percent(value.injury_adjusted_home_probability);
  $('shift').textContent = `${value.injury_change_percentage_points>=0?'+':''}${value.injury_change_percentage_points.toFixed(1)} pp`;
  $('training').textContent=value.training_games; $('reports').textContent=value.injury_reports_used;
  $('df').textContent=value.student_t_degrees_of_freedom; $('mc').textContent=`${(100*value.monte_carlo_standard_error).toFixed(3)} pp`;
  const left=Math.min(-1,value.predictive_margin_p05), right=Math.max(1,value.predictive_margin_p95), total=right-left;
  $('zero').style.left=`${100*(-left)/total}%`;
  $('interval').style.left=`${100*(value.predictive_margin_p05-left)/total}%`;
  $('interval').style.width=`${100*(value.predictive_margin_p95-value.predictive_margin_p05)/total}%`;
  $('low').textContent=`${left.toFixed(1)} points`; $('high').textContent=`+${right.toFixed(1)} points`;
  $('margin-summary').textContent=`Baseline mean margin: ${fmt(value.predicted_home_margin)} points. Injury-adjusted predictive interval: ${fmt(value.predictive_margin_p05)} to ${fmt(value.predictive_margin_p95)} points.`;
  $('players').replaceChildren(...value.players.map(p=>{
    const row=document.createElement('tr');
    [p.player_id+' / '+p.team,percent(p.absence_probability),fmt(p.assumed_impact_points)+' points',(100*p.isolated_absence_home_probability_change).toFixed(1)+' pp'].forEach(text=>{const cell=document.createElement('td');cell.textContent=text;row.append(cell);});
    return row;
  }));
  $('injury-note').textContent=value.players.length ? 'Effects are supplied assumptions relative to replacement, not fitted causal estimates. Isolated effects do not add up to a joint attribution.' : 'No injury reports were supplied before the cutoff. This does not establish that either roster is healthy.';
}

$('experiment').addEventListener('submit',async e=>{e.preventDefault();try{display(await request());}catch(e){fail(e);}});
$('download').addEventListener('click',()=>{if(!report)return;const u=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='synthetic-forecast.json';a.click();URL.revokeObjectURL(u);});
$('backtest').addEventListener('click',async()=>{const button=$('backtest');button.disabled=true;button.textContent='Backtesting…';try{const r=await request('backtest');$('backtest-result').hidden=false;$('bt-games').textContent=r.baseline_all.games;$('bt-base').textContent=r.baseline_all.brier?.toFixed(4)??'Unavailable';$('bt-cover').textContent=r.injury_coverage_games;const a=r.baseline_with_injury_coverage,b=r.adjusted_with_injury_coverage;$('bt-comparison').textContent=a.games ? `Matched coverage (${a.games} games): baseline Brier ${a.brier.toFixed(4)}; injury-adjusted Brier ${b.brier.toFixed(4)}. Log loss: ${a.log_loss.toFixed(4)} vs. ${b.log_loss.toFixed(4)}. Ties excluded: ${r.tie_games_excluded_from_binary_scoring}.` : 'No games have injury coverage; an injury-model comparison cannot be scored.';$('bt-label').textContent=$('mode').textContent==='SYNTHETIC DEMONSTRATION' ? 'These scores come from three fictional games and do not measure real-world performance.' : 'Backtest results depend on source timestamp quality, coverage, and supplied assumptions. This is not evidence of a trading edge.';}catch(e){fail(e);}finally{button.disabled=false;button.textContent='Run chronological backtest →';}});

fetch('data.json').then(r=>{if(!r.ok)throw Error('Demo data could not load. Reload or open the repository setup guide.');return r.json();}).then(async d=>{research=d;const option=document.createElement('option');option.value='DEMO_4';option.textContent='TEAM_A at TEAM_B · fixed synthetic matchup';$('game').replaceChildren(option);$('cutoff').value='2024-09-28T17:00:00Z';display(await request());}).catch(fail);
