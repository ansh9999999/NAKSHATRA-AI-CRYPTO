let symbol='BTCUSD',busy=false,productTimer=null;
const $=id=>document.getElementById(id);
const esc=v=>String(v??'—').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null};
const fmt=(v,d=2)=>{const n=num(v);return n===null?'—':n.toLocaleString('en-IN',{maximumFractionDigits:d})};
function set(id,v){if($(id))$(id).textContent=v??'—'}
function biasClass(v){const s=String(v||'').toUpperCase();return s.includes('BULL')||s.includes('BUY')||s.includes('POSITIVE')?'bull':s.includes('BEAR')||s.includes('SELL')||s.includes('NEGATIVE')?'bear':''}
function selectSymbol(s){symbol=s.toUpperCase();document.querySelectorAll('.symbol').forEach(b=>b.classList.toggle('active',b.dataset.symbol===symbol));$('cryptoSearch').value='';$('searchResults').innerHTML='';load()}
function normalizeRows(o){
 const raw=Array.isArray(o?.rows)?o.rows:(Array.isArray(o?.atm_chain)?o.atm_chain:[]);
 return raw.map(r=>({strike:num(r.strike??r.strike_price),ceLtp:num(r.call_ltp??r.ce_ltp??r.ce?.ltp),ceOi:num(r.call_oi??r.ce_oi??r.ce?.oi),peLtp:num(r.put_ltp??r.pe_ltp??r.pe?.ltp),peOi:num(r.put_oi??r.pe_oi??r.pe?.oi),ceDoi:num(r.call_oi_change??r.ce_oi_change??r.ce?.oi_change??r.delta_oi_call),peDoi:num(r.put_oi_change??r.pe_oi_change??r.pe?.oi_change??r.delta_oi_put),atm:Boolean(r.atm)})).filter(r=>r.strike!==null).sort((a,b)=>a.strike-b.strike);
}
function calcOption(o,spot){
 const rows=normalizeRows(o);if(!rows.length)return {rows:[],status:'NO_DATA',view:'SIDEWAYS'};
 const atm=rows.find(r=>r.atm)?.strike??rows.reduce((a,r)=>Math.abs(r.strike-spot)<Math.abs(a.strike-spot)?r:a).strike;
 const callOi=rows.reduce((s,r)=>s+(r.ceOi||0),0),putOi=rows.reduce((s,r)=>s+(r.peOi||0),0),pcr=callOi?putOi/callOi:null;
 const putSide=rows.filter(r=>r.strike<=atm&&r.peOi!=null),callSide=rows.filter(r=>r.strike>=atm&&r.ceOi!=null);
 const support=(putSide.sort((a,b)=>(b.peOi||0)-(a.peOi||0))[0]||{}).strike??null;
 const resistance=(callSide.sort((a,b)=>(b.ceOi||0)-(a.ceOi||0))[0]||{}).strike??null;
 let view=String(o.signal||'').toUpperCase();view=view==='BUY'?'BULLISH':view==='SELL'?'BEARISH':'SIDEWAYS';
 // OI-only view is intentionally descriptive, not a guaranteed price prediction.
 if(!o.signal&&pcr!=null)view=pcr>=1.2?'BULLISH':pcr<=.75?'BEARISH':'SIDEWAYS';
 const byStrike=new Map(rows.map(r=>[r.strike,r]));
 const serverCalls=Array.isArray(o.top_call_oi)?o.top_call_oi:[];
 const serverPuts=Array.isArray(o.top_put_oi)?o.top_put_oi:[];
 const topCalls=(serverCalls.length?serverCalls.map(r=>{const x=byStrike.get(num(r.strike))||{};return {...x,strike:num(r.strike),ceOi:num(r.oi??x.ceOi)}}):rows.filter(r=>r.ceOi!=null).sort((a,b)=>(b.ceOi||0)-(a.ceOi||0)).slice(0,5));
 const topPuts=(serverPuts.length?serverPuts.map(r=>{const x=byStrike.get(num(r.strike))||{};return {...x,strike:num(r.strike),peOi:num(r.oi??x.peOi)}}):rows.filter(r=>r.peOi!=null).sort((a,b)=>(b.peOi||0)-(a.peOi||0)).slice(0,5));
 return {rows,atm,pcr,callOi,putOi,support,resistance,maxPain:num(o.max_pain),expiry:o.expiry||'—',status:o.status||'OK',view,topCalls,topPuts};
}
function renderTradePlan(x,price){
 const p=x.trade_plan||{};let side=String(p.side||x.recommendation||'WAIT').toUpperCase();
 if(p.status==='READY'&&p.entry_zone){set('entryZone',p.entry_zone);set('stopLoss',fmt(p.stop_loss));set('tp1',fmt(p.target1));set('tp2',fmt(p.target2));set('tp3',fmt(p.target3));set('rr',p.risk_reward||'—');set('riskState',`${side} • ${p.basis||'ATR based'}`);return}
 const atr=num(x.atr),px=num(price);if((side==='BUY'||side==='SELL')&&atr&&px){const risk=Math.max(1.2*atr,px*.0025),half=Math.max(.15*atr,px*.0005);set('entryZone',`${fmt(px-half)} – ${fmt(px+half)}`);if(side==='BUY'){set('stopLoss',fmt(px-risk));set('tp1',fmt(px+1.5*risk));set('tp2',fmt(px+2.5*risk));set('tp3',fmt(px+3.5*risk))}else{set('stopLoss',fmt(px+risk));set('tp1',fmt(px-1.5*risk));set('tp2',fmt(px-2.5*risk));set('tp3',fmt(px-3.5*risk))}set('rr','1 : 2.5');set('riskState',`${side} • 5m ATR based`);return}
 ['entryZone','stopLoss','tp1','tp2','tp3','rr'].forEach(id=>set(id,'—'));set('riskState','WAIT • No actionable trade plan');
}
function renderOption(o,price){
 const oc=calcOption(o,price||0);set('expiry',`Expiry ${oc.expiry}`);set('optionStatus',oc.status==='OK'?'● LIVE':'● NO DATA');set('pcrOi',fmt(oc.pcr,3));set('pcrVol',fmt(o.pcr_volume,3));set('atm',fmt(oc.atm,0));set('maxPain',fmt(oc.maxPain,0));set('support',fmt(oc.support,0));set('resistance',fmt(oc.resistance,0));
 set('optionView',oc.view);set('optionViewReason',o.reason||'OI positioning snapshot');$('optionView').className=biasClass(oc.view);
 const row=(r,i,type)=>`<tr><td>${i+1}</td><td>${fmt(r.strike,0)}</td><td>${fmt(type==='CE'?r.ceOi:r.peOi,0)}</td><td>${fmt(type==='CE'?r.ceLtp:r.peLtp,2)}</td><td>${fmt(type==='CE'?r.ceDoi:r.peDoi,0)}</td></tr>`;
 $('topCalls').innerHTML=oc.topCalls.map((r,i)=>row(r,i,'CE')).join('')||'<tr><td colspan="5">No call OI data</td></tr>';
 $('topPuts').innerHTML=oc.topPuts.map((r,i)=>row(r,i,'PE')).join('')||'<tr><td colspan="5">No put OI data</td></tr>';
 set('optionNote',oc.status==='OK'?'Live Delta expiry chain • Top 5 OI only':'Option data unavailable — no stale option signal');
}
function render(a){
 const x=a.analysis||{},t=a.ticker||{},o=x.option_chain||{},it=x.intraday_trend||{},ii=x.intraday_intelligence||{},ast=x.astrology||{},numx=x.numerology||{},sent=x.sentiment||{},ag=x.agreement_detail||{};
 const sess=ii.session||{},ev=ii.events||{},by={};(it.timeframes||[]).forEach(z=>by[z.timeframe]=z);
 const price=num(t.price??t.ltp??x.price);set('marketSymbol',symbol.replace('USD','/USD'));set('price',fmt(price));set('change',t.change_24h==null?'':`24h ${fmt(t.change_24h)}%`);set('dayHigh',fmt(t.high??t.day_high??x.day_high));set('dayLow',fmt(t.low??t.day_low??x.day_low));set('dayVolume',fmt(t.volume,0));set('openInterest',fmt(t.oi??x.open_interest,0));
 const decision=String(x.recommendation||x.signal||'WAIT').toUpperCase();set('decision',decision);set('whyDecision',decision);const conf=num(x.confidence??x.overall_confidence);set('confidence',`Strength ${fmt(conf,0)}/100`);if($('confidenceBar'))$('confidenceBar').style.width=`${Math.max(0,Math.min(100,conf||0))}%`;
 set('agreementMini',`Agreement ${ag.final||x.agreement||'—'}`);set('agreementMini2',ag.final||x.agreement||'—');
 set('tf5',by['5m']?.trend||'—');set('tf15',by['15m']?.trend||'—');set('tf1h',by['1h']?.trend||'—');set('tf4h',by['4h']?.trend||by['1d']?.trend||'—');set('tf1d',by['1d']?.trend||'—');
 set('intra5',by['5m']?.trend||'—');set('intra15',by['15m']?.trend||'—');set('intra1h',by['1h']?.trend||'—');set('intra4h',by['4h']?.trend||'—');set('intra1d',by['1d']?.trend||'—');
 set('activityRegime',sess.activity||'—');set('relativeVolume',ii.relative_volume==null?'—':`${ii.relative_volume}x`);set('volumeRegime',ii.volume_regime||'—');
 renderTradePlan(x,price);set('eventRisk',ev.risk||'NORMAL');set('eventDisclaimer',ev.disclaimer||'Scheduled times are displayed in IST.');
 $('reasons').innerHTML=(x.reasons||[]).slice(0,6).map(r=>`<div>• ${esc(r)}</div>`).join('')||'<div>No high-quality reasons returned.</div>';
 const eventList=(ev.watchlist||ev.upcoming||[]).slice(0,4);$('catalyst').innerHTML=eventList.map(e=>{const dt=e.date_ist||e.time_ist?[e.date_ist,e.time_ist].filter(Boolean).join(' • '):e.datetime_ist||'Time varies (IST)';return `<div class="catalyst-row"><div class="event-main"><strong>${esc(e.name)}</strong><span class="event-time">🕒 ${esc(dt)}</span><span class="effect-label">CRYPTO EFFECT</span><small>${esc(e.effect||'Possible volatility impact; direction depends on actual release vs expectations.')}</small></div><div class="event-right"><b>${esc(e.impact||'—')}</b><small>${esc(e.status||'')}</small></div></div>`}).join('')||'<div class="muted">No scheduled event data.</div>';
 const tech=x.technical||{};set('moduleTechnical',tech.signal||'—');set('moduleOption',o.signal||'—');set('moduleAstrology',ast.bias||'—');set('moduleAstrology2',ast.bias||'—');set('moduleNumerology',numx.bias||'—');set('moduleNumerology2',numx.bias||'—');set('trend',x.trend||it.overall||'—');
 $('metrics').innerHTML=[['EMA9',x.ema9],['EMA21',x.ema21],['EMA50',x.ema50],['EMA200',x.ema200],['RSI',x.rsi],['MACD',x.macd],['ATR',x.atr],['Technical Score',tech.score]].map(q=>`<div><small>${q[0]}</small><b>${fmt(q[1],4)}</b></div>`).join('');
 $('astroRows').innerHTML=[['Rashi Trend',ast.rashi_trend||ast.bias],['Nakshatra',ast.nakshatra_influence||ast.nakshatra],['Tithi',ast.tithi_impact||ast.tithi],['Yoga',ast.yoga],['Karana',ast.karana],['Planetary',ast.planetary_alignment],['Score',ast.score]].map(q=>`<div><span>${esc(q[0])}</span><b>${esc(q[1])}</b></div>`).join('');
 $('numRows').innerHTML=[['Life Path',numx.life_path],['Expression',numx.expression_number],['Day Vibration',numx.day_vibration],['Market Number',numx.market_number],['Score',numx.score]].map(q=>`<div><span>${esc(q[0])}</span><b>${esc(q[1])}</b></div>`).join('');
 const sb=sent.bias||sent.signal||sent.overall||'—';set('sentimentBias',sb);$('sentimentRows').innerHTML=[['Social Sentiment',sent.social_sentiment],['News Sentiment',sent.news_sentiment],['Fear/Greed',sent.fear_greed],['Overall Score',sent.score]].map(q=>`<div><span>${esc(q[0])}</span><b>${esc(q[1])}</b></div>`).join('');
 renderOption(o,price);
 set('agreeTechnical',ag.technical||'—');set('agreeOptions',ag.option_chain||'—');set('agreeAstrology',ag.astrology||'—');set('agreeNumerology',ag.numerology||'—');set('agreeFinal',ag.final||x.agreement||'—');
 $('status').textContent='● LIVE';$('dataState').textContent='● LIVE';$('updateStatus').textContent=`Updated ${new Date().toLocaleTimeString()}`;
}
async function loadDay(){try{const r=await fetch(`/api/history?symbol=${encodeURIComponent(symbol)}&resolution=1d&limit=3&_=${Date.now()}`,{cache:'no-store'});const d=await r.json();const rows=d.rows||d.history||[];if(rows.length>=2){const a=rows[rows.length-2],b=rows[rows.length-1];const prev=num(a.close),last=num(b.close);if(prev&&last){const ch=last-prev,p=ch/prev*100;set('dayChange',`${ch>=0?'▲':'▼'} ${fmt(ch)}`);set('dayChangePct',`${p>=0?'+':''}${fmt(p)}%`)}}}catch(e){set('dayChange','—');set('dayChangePct','1D data unavailable')}}
async function load(){if(busy)return;busy=true;try{const r=await fetch(`/api/live?symbol=${encodeURIComponent(symbol)}&_=${Date.now()}`,{cache:'no-store'});const d=await r.json();if(d.status==='OK'){render(d);loadDay()}else{set('status','● DATA RISK');set('dataState','● DATA RISK');set('updateStatus',d.message||'Data unavailable')}}catch(e){set('status','● OFFLINE');set('dataState','● OFFLINE');set('updateStatus','Connection error')}finally{busy=false}}
async function scanner(){try{const r=await fetch('/api/scanner?_='+Date.now(),{cache:'no-store'});const d=await r.json();const arr=Array.isArray(d)?d:(d.markets||[]);$('scanner').innerHTML=arr.map(x=>`<div class="scanner-row"><b>${esc(x.symbol)}</b><span>${esc(x.signal||x.recommendation||'WAIT')}</span><small>${esc(x.strength??x.confidence??'—')}</small></div>`).join('')||'No scanner data'}catch(e){$('scanner').textContent='Scanner unavailable'}}
async function trades(){try{const r=await fetch('/api/history?_='+Date.now(),{cache:'no-store'});const d=await r.json();const arr=Array.isArray(d)?d:(d.history||[]);$('trades').innerHTML=(arr||[]).slice(-8).reverse().map(x=>`<tr><td>${esc(x.symbol)}</td><td>${esc(x.side)}</td><td>${esc(fmt(x.entry))}</td><td>${esc(fmt(x.pnl))}</td><td>${esc(x.status)}</td></tr>`).join('')||'<tr><td colspan="5">No trades yet</td></tr>';$('equitySummary').textContent=arr?.length?`${arr.length} recorded trades`:'No recorded trades'}catch(e){$('equitySummary').textContent='Trade history unavailable'}}
async function searchProducts(q){clearTimeout(productTimer);if(!q||q.length<1){$('searchResults').innerHTML='';return}productTimer=setTimeout(async()=>{try{const r=await fetch(`/api/products?q=${encodeURIComponent(q)}`);const d=await r.json();$('searchResults').innerHTML=(d.products||[]).slice(0,8).map(p=>`<button class="result-item" data-symbol="${esc(p.symbol)}"><b>${esc(p.symbol)}</b><small>${esc(p.description||p.contract_type||'Delta product')}</small></button>`).join('')||'<div class="empty-search">No live Delta crypto found</div>';document.querySelectorAll('.result-item').forEach(b=>b.onclick=()=>selectSymbol(b.dataset.symbol))}catch(e){$('searchResults').innerHTML='<div class="empty-search">Search unavailable</div>'}},120)}
document.querySelectorAll('.symbol').forEach(b=>b.onclick=()=>selectSymbol(b.dataset.symbol));$('cryptoSearch').addEventListener('input',e=>searchProducts(e.target.value));$('refreshBtn')?.addEventListener('click',()=>{load();scanner();trades()});load();scanner();trades();setInterval(()=>{load();scanner()},10000);
