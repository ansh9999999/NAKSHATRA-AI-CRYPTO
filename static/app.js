let symbol='BTCUSD'; let busy=false;
const $=id=>document.getElementById(id);
function fmt(v,d=2){return v==null||Number.isNaN(Number(v))?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});}
function setDecision(v){$('decision').textContent=v||'WAIT'; $('decision').className=(v||'WAIT').toLowerCase();}
function render(a){
 const t=a.ticker||{}; const x=a.analysis||{}; $('price').textContent=fmt(t.ltp); $('change').textContent=t.change_24h==null?'':`24h ${fmt(t.change_24h)}%`;
 setDecision(x.recommendation); $('confidence').textContent=`Confidence ${fmt(x.confidence,1)}%`; $('trend').textContent=x.trend||'—'; $('techScore').textContent=fmt(x.technical_score,0); $('optScore').textContent=fmt(x.option_score,0); $('overallScore').textContent=fmt(x.overall_score,0);
 const it=x.intraday_trend||{}; $('overall').textContent=it.overall||'—'; const by={}; (it.timeframes||[]).forEach(z=>by[z.timeframe]=z); ['5m','15m','1h','1d'].forEach(k=>$(k==='1h'?'tf1h':'tf'+k.replace('m','')).textContent=by[k]?.trend||'—');
 $('mtf').innerHTML=(it.timeframes||[]).map(z=>`<div class="row"><b>${z.timeframe}</b><span>${z.trend}</span><em>score ${z.score}</em></div>`).join('');
 $('metrics').innerHTML=[['EMA9',x.ema9],['EMA21',x.ema21],['EMA50',x.ema50],['EMA200',x.ema200],['RSI',x.rsi],['MACD',x.macd],['ATR',x.atr]].map(q=>`<div><small>${q[0]}</small><b>${fmt(q[1],4)}</b></div>`).join('');
 $('reasons').innerHTML=(x.reasons||[]).map(r=>`<span>• ${r}</span>`).join('');
 const o=x.option_chain||{}; $('expiry').textContent=`Expiry ${o.expiry||'—'}`; $('optionMetrics').innerHTML=[['PCR OI',o.pcr_oi],['PCR VOL',o.pcr_volume],['ATM',o.atm],['Support',o.support],['Resistance',o.resistance],['Max Pain',o.max_pain],['CE OI',o.call_oi],['PE OI',o.put_oi]].map(q=>`<div><small>${q[0]}</small><b>${fmt(q[1],3)}</b></div>`).join('');
 $('chain').innerHTML=(o.atm_chain||[]).map(r=>`<tr class="${r.atm?'atm':''}"><td>${fmt(r.strike)}</td><td>${fmt(r.call_ltp)}</td><td>${fmt(r.call_oi,0)}</td><td>${fmt(r.put_oi,0)}</td><td>${fmt(r.put_ltp)}</td></tr>`).join('') || '<tr><td colspan="5">Option chain unavailable</td></tr>';
 $('status').textContent='● LIVE';
}
async function load(){if(busy)return;busy=true;try{const r=await fetch(`/api/live?symbol=${symbol}&_=${Date.now()}`);const d=await r.json();if(d.status==='OK')render(d);else $('status').textContent='● ERROR';}catch(e){$('status').textContent='● OFFLINE';}finally{busy=false;}}
document.querySelectorAll('.symbol').forEach(b=>b.onclick=()=>{document.querySelectorAll('.symbol').forEach(x=>x.classList.remove('active'));b.classList.add('active');symbol=b.dataset.symbol;load();});load();setInterval(load,15000);
