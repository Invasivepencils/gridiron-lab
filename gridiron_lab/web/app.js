let data, report;
const $ = id => document.getElementById(id);
const percent = p => `${(100*p).toFixed(1)}%`;
const fmt = x => Number(x).toFixed(2);
async function options() {
  const response=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,action:'inspect'})});
  const parsed=await response.json();
  if(!response.ok) throw new Error(parsed.error);
  if(!parsed.games.length) throw new Error('The game CSV is empty');
  $('game').replaceChildren(...parsed.games.map(g=>{const option=document.createElement('option');option.value=g.game_id;option.textContent=`${g.away} at ${g.home} · ${g.game_id}`;option.dataset.kickoff=g.kickoff;return option;}));
  $('game').value=data.game_id || parsed.games.filter(g=>!g.completed).at(-1)?.game_id || parsed.games.at(-1).game_id;
}
async function request(action='forecast') {
  $('error').hidden = true;
  const response = await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,game_id:$('game').value,cutoff:$('cutoff').value,action})});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Unable to analyze the data');
  return value;
}
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
function fail(error) { $('error').hidden=false; $('error').textContent=error.message; }
async function run(){try{display(await request());}catch(e){fail(e);}}
async function demo(){try{data=await (await fetch('/api/demo')).json(); await options(); $('cutoff').value=data.cutoff; $('mode').textContent='SYNTHETIC DEMONSTRATION'; $('dataset-note').textContent='Fictional teams and assumed player effects. This is a method demonstration, not a current NFL forecast.'; $('games-file').value=''; $('injuries-file').value=''; $('backtest-result').hidden=true;await run();}catch(e){fail(e);}}
$('experiment').addEventListener('submit',async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;button.textContent='Estimating…';await run();button.disabled=false;button.textContent='Run Bayesian forecast →';});
$('games-file').addEventListener('change',async e=>{try{if(!e.target.files[0])return;data.games_csv=await e.target.files[0].text();data.game_id=null;data.injuries_csv='';await options();$('cutoff').value=new Date(new Date($('game').selectedOptions[0].dataset.kickoff).getTime()-86400000).toISOString();$('output').hidden=true;$('backtest-result').hidden=true;$('injuries-file').value='';$('mode').textContent='USER-SUPPLIED DATA';$('dataset-note').textContent='Uploaded CSVs have not been independently verified. Set a pregame UTC cutoff and supply timestamped injury assumptions.';}catch(e){fail(e);}});
$('injuries-file').addEventListener('change',async e=>{if(e.target.files[0])data.injuries_csv=await e.target.files[0].text();});
$('game').addEventListener('change',()=>{$('cutoff').value=new Date(new Date($('game').selectedOptions[0].dataset.kickoff).getTime()-86400000).toISOString();$('output').hidden=true;});
$('demo').addEventListener('click',demo);
$('download').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='gridiron-forecast.json';a.click();URL.revokeObjectURL(url);});
$('backtest').addEventListener('click',async()=>{const button=$('backtest');button.disabled=true;button.textContent='Backtesting…';try{const r=await request('backtest');$('backtest-result').hidden=false;$('bt-games').textContent=r.baseline_all.games;$('bt-base').textContent=r.baseline_all.brier?.toFixed(4)??'Unavailable';$('bt-cover').textContent=r.injury_coverage_games;const a=r.baseline_with_injury_coverage,b=r.adjusted_with_injury_coverage;$('bt-comparison').textContent=a.games ? `Matched coverage (${a.games} games): baseline Brier ${a.brier.toFixed(4)}; injury-adjusted Brier ${b.brier.toFixed(4)}. Log loss: ${a.log_loss.toFixed(4)} vs. ${b.log_loss.toFixed(4)}. Ties excluded: ${r.tie_games_excluded_from_binary_scoring}.` : 'No games have injury coverage; an injury-model comparison cannot be scored.';$('bt-label').textContent=$('mode').textContent==='SYNTHETIC DEMONSTRATION' ? 'These scores come from three fictional games and do not measure real-world performance.' : 'Backtest results depend on source timestamp quality, coverage, and supplied assumptions. This is not evidence of a trading edge.';}catch(e){fail(e);}finally{button.disabled=false;button.textContent='Run chronological backtest →';}});
demo();
