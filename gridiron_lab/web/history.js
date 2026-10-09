let index,report,selected,rows=[],page=1,loadToken=0;
const $=s=>document.querySelector(s),els={season:$('#season'),view:$('#view'),week:$('#week'),team:$('#team'),unit:$('#unit'),search:$('#search'),sort:$('#sort')};
const state=new URLSearchParams(location.search),fmt=(n,d=1)=>Number(n).toFixed(d),signed=n=>(n>0?'+':'')+fmt(n),name=t=>index?.teams[t]||t;
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const option=(value,text)=>{const e=node('option',text);e.value=value;return e;};
function message(text,error=false){$('#status').textContent=text;$('#status').className=error?'error':'small';$('#status').setAttribute('role',error?'alert':'status');}
function save(){const p=new URLSearchParams();for(const[k,e]of Object.entries(els))if(e.value)p.set(k,e.value);if(selected)p.set('player',selected.id);if($('#compare-a')?.value)p.set('first',$('#compare-a').value);if($('#compare-b')?.value)p.set('second',$('#compare-b').value);history.replaceState(null,'','?'+p);}
function recordText(r){return r.games?`${r.wins} wins in ${r.games} games · average margin ${signed(r.margin)} points`:'No comparable games';}
function metricRow(p){let row=p;if(els.view.value==='week'){const w=p.weeks.find(w=>w.week===Number(els.week.value));if(!w)return null;row={...p,wpa:w.wpa,epa:w.epa,units:w.units,current:w};}const unit=els.unit.value;if(unit){const credit=row.units?.[unit];if(!credit?.plays)return null;return {...row,wpa:credit.wpa,epa:credit.epa,unit};}return row;}
function render(){
 if(!report)return;els.week.disabled=els.view.value!=='week';$('#detail').hidden=true;selected=null;
 const q=els.search.value.trim().toLowerCase();rows=report.players.map(metricRow).filter(p=>p&&(!els.team.value||p.team===els.team.value)&&(!q||`${p.name} ${name(p.team)} ${p.position}`.toLowerCase().includes(q)));
 const sort=els.sort.value;rows.sort((a,b)=>sort==='dependence'?((b.dependence?.low??-999)-(a.dependence?.low??-999)):(b[sort]-a[sort]));
 page=Math.min(page,Math.max(1,Math.ceil(rows.length/25)));$('#list-title').textContent=els.view.value==='week'?`Who made the biggest recorded plays in Week ${els.week.value}?`:`Who added the most over the ${els.season.value} season?`;
 $('#list-caption').textContent=`${rows.length.toLocaleString()} players · regular season only · ${els.view.value==='week'?'one week':'all 18 weeks'} · select a name to see their games and team dependence.`;
 $('#cards').replaceChildren();
 for(const unit of (els.unit.value?[els.unit.value]:['Offense','Defense','Special teams'])){
  const p=rows.filter(p=>p.units?.[unit]?.plays).sort((a,b)=>b.units[unit].wpa-a.units[unit].wpa)[0],card=node('div',undefined,'answer-card');card.append(node('span',unit,'mini'));
  if(p){const b=node('button',p.name);b.addEventListener('click',()=>detail(p));const strong=node('strong');strong.append(b);card.append(strong,node('p',`${name(p.team)} · ${signed(p.units[unit].wpa)} play-impact points${els.view.value==='week'?' this week':' this season'}`));}else card.append(node('p','No matching players in this group.'));
  $('#cards').append(card);
 }
 const tbody=$('#leaders tbody');tbody.replaceChildren();
 for(const[pIndex,p]of rows.slice((page-1)*25,page*25).entries()){
  const tr=node('tr'),cells=Array.from({length:6},()=>node('td'));cells[0].textContent=(page-1)*25+pIndex+1;
  const b=node('button',p.name,'player-link');b.addEventListener('click',()=>detail(p));cells[1].append(b,node('span',`${p.position} · ${name(p.team)}`,'sub'));
  cells[2].textContent=els.unit.value||Object.entries(p.units||{}).filter(([u,v])=>v.plays).map(([u])=>u).join(' / ')||p.unit;cells[3].append(node('strong',signed(p.wpa),'metric'+(p.wpa<0?' negative':'')));cells[4].textContent=signed(p.epa);
  cells[5].textContent=p.current?`${p.current.result} ${p.current.score} vs ${name(p.current.opponent)}`:p.dependence?`${signed(p.dependence.effect)} points · ${p.active.games}/${p.limited.games} games`:'Too few comparable games';tr.append(...cells);tbody.append(tr);
 }
 if(!rows.length){const td=node('td','No players match. Try a full name, another team, or clear the search.');td.colSpan=6;const tr=node('tr');tr.append(td);tbody.append(tr);}
 $('#page-label').textContent=`Page ${page} of ${Math.max(1,Math.ceil(rows.length/25))}`;$('#previous').disabled=page===1;$('#next').disabled=page*25>=rows.length;
 $('#coverage').textContent=`${report.coverage.games} games · ${report.coverage.plays.toLocaleString()} play records · ${report.coverage.players.toLocaleString()} player-team entries · ${report.coverage.unmatched_snap_rows} unmatched snap records and ${report.coverage.unmatched_player_team_weeks} unmatched credited player/team/week groups excluded.`;
 renderComparison();save();
}
function detail(p){
 selected=report.players.find(x=>x.id===p.id);p=selected;const root=$('#detail');root.replaceChildren();root.hidden=false;
 root.append(node('p',`${name(p.team)} / ${p.position} / ${els.season.value}`,'eyebrow'),node('h2',p.name),node('p','A great week and a great season are different. Start with the plays, then check whether the team struggled without this player.'));
 const stats=node('div',undefined,'stat-grid');
 for(const[label,value,help]of [['Season play impact',signed(p.wpa),'Accumulated credited win-probability points, not a probability or replacement estimate.'],['Expected points added',signed(p.epa),'Recorded play value, shared between named contributors.'],['Positive-impact weeks',`${p.positive_weeks} / ${p.played_games}`,'Weeks with positive recorded credit / games with participation evidence.']]){const c=node('div');c.append(node('span',label,'mini'),node('strong',value),node('span',help,'small'));stats.append(c);}root.append(stats);
 root.append(node('h3','How did their season unfold?'));const timeline=node('div',undefined,'timeline');
 const max=Math.max(1,...p.weeks.map(w=>Math.abs(w.wpa)));
 for(const w of p.weeks){const b=node('button',undefined,'week-bar');b.type='button';b.title=`Week ${w.week}: ${signed(w.wpa)} win-probability points`;b.setAttribute('aria-label',b.title);const fill=node('span',undefined,'bar-fill');fill.style.height=`${Math.max(2,Math.abs(w.wpa)/max*60)}px`;if(w.wpa<0)fill.style.background='#ffb4a5';b.append(fill,node('small',w.week));b.addEventListener('click',()=>weekDetail(w));timeline.append(b);}root.append(timeline,node('p','Select a week. Green = positive recorded play credit; coral = negative. Empty weeks can mean no credited events, not no contribution.','timeline-caption'));
 const wdetail=node('div');wdetail.id='week-detail';root.append(wdetail);
 function weekDetail(w){wdetail.replaceChildren(node('h3',`Week ${w.week} · ${w.result} ${w.score} vs ${name(w.opponent)}`),node('p',`${signed(w.wpa)} credited win-probability points · ${signed(w.epa)} expected points · ${w.snap==null?'Snap share unavailable':fmt(w.snap*100,0)+'% of '+p.unit.toLowerCase()+' snaps'}`));if(w.injury)wdetail.append(node('p',`Injury report: ${w.injury.status}${w.injury.injury?' · '+w.injury.injury:''}`,'small'));const list=node('ol',undefined,'play-list');for(const play of w.top)list.append(node('li',`${signed(play.swing)} points · ${play.description}`));wdetail.append(list);if(!w.top.length)wdetail.append(node('p','No named play credit in this game. Blocking, coverage away from the ball, and other unrecorded work are not measured.','small'));}
 const current=p.weeks.find(w=>w.week===Number(els.week.value)),best=[...p.weeks].sort((a,b)=>b.wpa-a.wpa)[0];weekDetail(els.view.value==='week'&&current?current:best);
 root.append(node('h3','Did the team depend on them?'),node('p',`Compare games with at least ${fmt(p.threshold*100,0)}% of this player’s primary ${p.unit.toLowerCase()} unit’s snaps against games below that threshold. Kickers, punters and long snappers use 1% because their role has few snaps. Opponent and home-field adjustments help, but other missing teammates and coaching still matter.`));
 const dep=node('div',undefined,'stat-grid');
 for(const[label,r]of [['Regular involvement',p.active],['Limited / not playing',p.limited]]){const c=node('div');c.append(node('span',label,'mini'),node('strong',r.games?fmt(r.win_rate*100,0)+'% wins':'No sample'),node('p',recordText(r),'small'));if(r.win_interval)c.append(node('p',`90% interval for win rate: ${fmt(r.win_interval[0]*100,0)}–${fmt(r.win_interval[1]*100,0)}%`,'small'));dep.append(c);}
 const d=node('div');d.append(node('span','Adjusted margin association','mini'));
 if(p.dependence){const a=p.dependence;d.append(node('strong',signed(a.effect)+' points'),node('p',`90% model interval ${signed(a.low)} to ${signed(a.high)} points`,'small'),node('p',a.low>0?'Evidence is consistent with the team doing better with regular involvement.':a.high<0?'The team did better in the limited-involvement sample. This does not prove the player harmed the team.':'The comparison is inconclusive; the model interval includes no difference.','small'));}else d.append(node('p','Too few comparable games. At least 3 regularly involved and 2 limited games are required.','small'));dep.append(d);root.append(dep,node('p',`${p.unknown_games} roster weeks have unknown snap participation and are excluded from this comparison. Limited games include injury, rotation, rest, and other reasons.`, 'small'));
 root.append(node('h3','What about their quieter games?'),node('p','Below versus at/above this player’s own median expected-points credit, among games with at least 3 credited events. This describes the season; team results and player production are linked, so it is not a causal test.','small'),node('p',`Below their median: ${recordText(p.low_performance)}. At/above their median: ${recordText(p.high_performance)}.`));
 root.append(node('p','There is no “sole reason they won” score. Play credit and team dependence are different evidence. A narrow or missing sample does not lower a player’s star rating.','evidence-note'));save();root.setAttribute('tabindex','-1');root.focus({preventScroll:true});root.scrollIntoView({behavior:'smooth',block:'start'});
}
async function load(){
 const token=++loadToken;report=null;selected=null;$('#team-comparison').replaceChildren();$('#all-teams').replaceChildren();$('#compare-note').textContent='Loading selected season…';$('#detail').hidden=true;$('#leaders tbody').replaceChildren();$('#cards').replaceChildren();message('Loading real NFL games…');
 try{const response=await fetch(`history-${els.season.value}.json.gz?v=${index.files?.[els.season.value]||'1'}`);if(!response.ok)throw Error('Season data could not load.');if(!globalThis.DecompressionStream)throw Error('Please use an updated browser to open the compressed season data.');const data=await new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).json();if(token!==loadToken)return;report=data;page=1;render();message('Choose a week or season, then select a player for their story.');const pid=state.get('player');if(pid){const p=report.players.find(p=>p.id===pid);if(p)detail(p);state.delete('player');}}catch(e){if(token===loadToken)message(e.message+' Try reloading or choosing another season.',true);}
}
for(const[k,e]of Object.entries(els))e.addEventListener(k==='search'?'input':'change',()=>{page=1;if(k==='season')load();else render();});
$('#previous').addEventListener('click',()=>{page--;render();});$('#next').addEventListener('click',()=>{page++;render();});
$('#clear').addEventListener('click',()=>{els.search.value='';els.team.value='';els.unit.value='';els.sort.value='wpa';page=1;render();});
const compareA=$('#compare-a'),compareB=$('#compare-b');
function periodPlayers(team){return report.players.filter(p=>p.team===team).map(p=>{if(els.view.value!=='week')return p;const w=p.weeks.find(w=>w.week===Number(els.week.value));return w?{...p,wpa:w.wpa,epa:w.epa,units:w.units}:null;}).filter(Boolean);}
function teamGames(team){const games=new Map();for(const p of report.players.filter(p=>p.team===team))for(const w of p.weeks)if(els.view.value!=='week'||w.week===Number(els.week.value))games.set(w.game,w);return [...games.values()].sort((a,b)=>a.week-b.week);}
function renderComparison(){
 if(!report)return;
 const root=$('#team-comparison');root.replaceChildren();
 const period=els.view.value==='week'?'Week '+els.week.value:els.season.value+' regular season';
 $('#compare-note').textContent=compareA.value===compareB.value?'Choose two different teams for a side-by-side comparison.':period+' · Both teams use the same period. Player search and unit filters below do not change this comparison.';
 for(const team of [compareA.value,compareB.value]){
  const card=node('article',undefined,'team-card'),games=teamGames(team),players=periodPlayers(team).sort((a,b)=>b.wpa-a.wpa);
  card.append(node('p',period,'eyebrow'),node('h3',name(team)));
  if(!games.length){card.append(node('p','No game recorded this week. The team may have a bye.'));root.append(card);continue;}
  const wins=games.filter(g=>g.result==='W').length,losses=games.filter(g=>g.result==='L').length,ties=games.length-wins-losses;
  card.append(node('p',els.view.value==='week'?(games[0].result==='W'?'Won ':games[0].result==='L'?'Lost ':'Tied ')+games[0].score+' against '+name(games[0].opponent):wins+' wins · '+losses+' losses'+(ties?' · '+ties+' ties':''),'team-record'));
  if(els.view.value==='season')card.append(node('p','Average score margin: '+signed(games.reduce((s,g)=>s+g.margin,0)/games.length)+' points per game. Positive means they outscored opponents on average.','small'));
  card.append(node('h4','Leading recorded play contributor'));
  const leader=players.find(p=>Object.values(p.units).some(u=>u.plays));
  if(leader){const b=node('button',leader.name,'player-link');b.addEventListener('click',()=>detail(leader));card.append(b,node('p',leader.position+' · '+signed(leader.wpa)+' play-impact points'),node('p',leader.wpa>0?'Highest accumulated credit among this team’s recorded contributors.':'Highest recorded credit on this team; the total was zero or negative.','small'));}
  else card.append(node('p','No named play credit is available.'));
  for(const unit of ['Offense','Defense','Special teams']){const p=players.filter(p=>p.units[unit]?.plays).sort((a,b)=>b.units[unit].wpa-a.units[unit].wpa)[0];const line=node('p');line.append(node('span',unit+': '));if(p){const b=node('button',p.name,'player-link');b.addEventListener('click',()=>detail(p));line.append(b,node('span',' · '+signed(p.units[unit].wpa)+' points'));}else line.append(node('span','No recorded contributor'));card.append(line);}
  const history=node('div',undefined,'game-strip');for(const g of games){const b=node('button','W'+g.week+' '+g.result);b.type='button';b.setAttribute('aria-label','Week '+g.week+': '+g.result+' '+g.score+' against '+name(g.opponent));b.addEventListener('click',()=>{els.view.value='week';els.week.value=g.week;render();});history.append(b);}card.append(history);root.append(card);
 }
 const all=$('#all-teams');all.replaceChildren();for(const team of Object.keys(index.teams).sort((a,b)=>name(a).localeCompare(name(b)))){const p=periodPlayers(team).filter(p=>Object.values(p.units).some(u=>u.plays)).sort((a,b)=>b.wpa-a.wpa)[0];const row=node('div');row.append(node('strong',name(team)));if(p){const b=node('button',p.name+' · '+signed(p.wpa)+' points','player-link');b.addEventListener('click',()=>detail(p));row.append(b);}else row.append(node('span','No game or named credit this week'));all.append(row);}
 const params=new URLSearchParams(location.search);params.set('first',compareA.value);params.set('second',compareB.value);history.replaceState(null,'','?'+params);
}
for(const e of [compareA,compareB])e.addEventListener('change',()=>{save();renderComparison();});
$('#swap').addEventListener('click',()=>{[compareA.value,compareB.value]=[compareB.value,compareA.value];save();renderComparison();});
fetch('history-index.json').then(r=>{if(!r.ok)throw Error('Data index unavailable');return r.json();}).then(d=>{
 index=d;for(const[t,n]of Object.entries(d.teams).sort((a,b)=>a[1].localeCompare(b[1]))){compareA.append(option(t,n));compareB.append(option(t,n));}compareA.value=d.teams[state.get('first')]?state.get('first'):'BUF';compareB.value=d.teams[state.get('second')]?state.get('second'):'SF';for(const y of [...d.seasons].reverse())els.season.append(option(y,y));for(const[t,n]of Object.entries(d.teams).sort((a,b)=>a[1].localeCompare(b[1])))els.team.append(option(t,n));for(let w=1;w<=18;w++)els.week.append(option(w,'Week '+w));
 for(const[k,e]of Object.entries(els)){const v=state.get(k);if(v&&(e.tagName!=='SELECT'||[...e.options].some(o=>o.value===v)))e.value=v;}load();
}).catch(e=>message(e.message+' Reload or visit the source repository.',true));
