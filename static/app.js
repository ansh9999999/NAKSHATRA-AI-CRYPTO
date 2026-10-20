let symbol='BTCUSD',busy=false,productTimer=null; window.NAKSHATRA_SYMBOL=symbol;
const $=id=>document.getElementById(id);
const esc=v=>String(v??'—').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null};
const fmt=(v,d=2)=>{const n=num(v);return n===null?'—':n.toLocaleString('en-IN',{maximumFractionDigits:d})};
const fmtExact=(v)=>{if(v===null||v===undefined||v==='')return '—';let s=String(v).trim();if(!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(s))return esc(s);if(/[eE]/.test(s)){const n=Number(s);if(!Number.isFinite(n))return '—';s=n.toFixed(12).replace(/0+$/,'').replace(/\.$/,'');}let sign='';if(s[0]==='-'||s[0]==='+'){sign=s[0];s=s.slice(1);}let parts=s.split('.');let whole=(parts[0]||'0').replace(/^0+(?=\d)/,'').replace(/\B(?=(\d{3})+(?!\d))/g,',');return sign+whole+(parts.length>1&&parts[1]!==''?'.'+parts[1]:'')};
function set(id,v){if($(id))$(id).textContent=v??'—'}
function biasClass(v){
 const s=String(v??'').toUpperCase().replace(/[–—]/g,'-');
 if(/\b(BULLISH|STRONG BULL|BULL|BUY|POSITIVE)\b/.test(s))return 'bull';
 if(/\b(BEARISH|STRONG BEAR|BEAR|SELL|NEGATIVE)\b/.test(s))return 'bear';
 if(/\b(SIDEWAYS|NEUTRAL|WAIT|RANGE[- ]BOUND)\b/.test(s))return 'sideways';
 return '';
}
function paintBias(id,v){const el=$(id);if(!el)return;el.classList.remove('bull','bear','sideways');const c=biasClass(v);if(c)el.classList.add(c)}
function paintValueBias(root=document){
 const selector='b,strong,span,td,th,small,div,p,li,h2,h3,label';
 root.querySelectorAll(selector).forEach(el=>{
   // Only colour text-bearing leaf nodes; never colour an entire card because of its children.
   if([...el.children].some(ch=>ch.textContent.trim()))return;
   const raw=(el.textContent||'').trim();
   el.classList.remove('bull','bear','sideways');
   if(!raw||raw.length>100)return;
   const c=biasClass(raw);if(c)el.classList.add(c);
 });
}
function selectSymbol(s){symbol=s.toUpperCase();window.NAKSHATRA_SYMBOL=symbol;document.querySelectorAll('.symbol').forEach(b=>b.classList.toggle('active',b.dataset.symbol===symbol));$('cryptoSearch').value='';$('searchResults').innerHTML='';window.dispatchEvent(new CustomEvent('nakshatra:symbol-changed',{detail:{symbol}}));load()}
function normalizeRows(o){
 const raw=Array.isArray(o?.rows)?o.rows:(Array.isArray(o?.atm_chain)?o.atm_chain:[]);
 const grouped=new Map();
 for(const r of raw){
   const strike=num(r.strike??r.strike_price); if(strike===null) continue;
   const x=grouped.get(strike)||{strike,ceLtp:null,ceOi:null,peLtp:null,peOi:null,ceDoi:null,peDoi:null,ceVol:null,peVol:null,atm:Boolean(r.atm)};
   const typ=String(r.type??r.contract_type??'').toUpperCase();
   const oi=num(r.oi??r.open_interest);
   const ltp=num(r.ltp??r.close??r.mark_price);
   const doi=num(r.oi_change??r.call_oi_change??r.put_oi_change??r.delta_oi);
   if(typ.includes('CALL')||typ==='CE'||typ==='CALL_OPTIONS'){x.ceOi=oi;x.ceLtp=ltp;x.ceDoi=doi;x.ceVol=num(r.volume??r.vol??r.turnover);}
   else if(typ.includes('PUT')||typ==='PE'||typ==='PUT_OPTIONS'){x.peOi=oi;x.peLtp=ltp;x.peDoi=doi;x.peVol=num(r.volume??r.vol??r.turnover);}
   else {
     x.ceLtp=num(r.call_ltp??r.ce_ltp??r.ce?.ltp); x.ceOi=num(r.call_oi??r.ce_oi??r.ce?.oi);
     x.peLtp=num(r.put_ltp??r.pe_ltp??r.pe?.ltp); x.peOi=num(r.put_oi??r.pe_oi??r.pe?.oi);
     x.ceDoi=num(r.call_oi_change??r.ce_oi_change??r.ce?.oi_change??r.delta_oi_call); x.ceVol=num(r.call_volume??r.ce_volume??r.ce?.volume);
     x.peDoi=num(r.put_oi_change??r.pe_oi_change??r.pe?.oi_change??r.delta_oi_put); x.peVol=num(r.put_volume??r.pe_volume??r.pe?.volume);
   }
   grouped.set(strike,x);
 }
 return [...grouped.values()].sort((a,b)=>a.strike-b.strike);
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
 const callVol=rows.reduce((s,r)=>s+(r.ceVol||0),0),putVol=rows.reduce((s,r)=>s+(r.peVol||0),0); return {rows,atm,pcr,callOi,putOi,callVol,putVol,support,resistance,maxPain:num(o.max_pain),expiry:o.expiry||'—',status:o.status||'OK',view,topCalls,topPuts};
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
 if(oc.callVol>0||oc.putVol>0){const vr=oc.callVol?oc.putVol/oc.callVol:null;const vb=vr!==null?(vr>=1.2?'BEARISH PUT-VOLUME DOMINANCE':vr<=0.75?'BULLISH CALL-VOLUME DOMINANCE':'SIDEWAYS / BALANCED VOLUME'):'UNCONFIRMED';set('callPutVolumeBias',vb);paintBias('callPutVolumeBias',vb);set('callPutVolumeEffect',`Call volume ${fmt(oc.callVol,0)} • Put volume ${fmt(oc.putVol,0)}. ${vr!==null&&vr>=1.2?'Put-side activity dominates; may reflect hedging or bearish speculation, confirm price/OI.':vr!==null&&vr<=0.75?'Call-side activity dominates; may reflect bullish speculation, confirm price/OI.':'No strong call/put volume imbalance.'}`)}else{set('callPutVolumeBias','UNAVAILABLE');set('callPutVolumeEffect','This option-chain feed does not provide comparable call/put traded volume. OI/PCR are not substitutes for traded volume.')}
 const row=(r,i,type)=>`<tr><td>${i+1}</td><td>${fmt(r.strike,0)}</td><td>${fmt(type==='CE'?r.ceOi:r.peOi,0)}</td><td>${fmt(type==='CE'?r.ceLtp:r.peLtp,2)}</td><td>${fmt(type==='CE'?r.ceDoi:r.peDoi,0)}</td></tr>`;
 $('topCalls').innerHTML=oc.topCalls.map((r,i)=>row(r,i,'CE')).join('')||'<tr><td colspan="5">No call OI data</td></tr>';
 $('topPuts').innerHTML=oc.topPuts.map((r,i)=>row(r,i,'PE')).join('')||'<tr><td colspan="5">No put OI data</td></tr>';
 set('optionNote',oc.status==='OK'?'Live Delta expiry chain • Top 5 OI only':'Option data unavailable — no stale option signal');
}
function render(a){
 const x=a.analysis||{},t=a.ticker||{},o=x.option_chain||{},it=x.intraday_trend||{},ii=x.intraday_intelligence||{},ast=x.astrology||{},numx=x.numerology||{},sent=x.sentiment||{},ag=x.agreement_detail||{};
 const sess=ii.session||{},ev=ii.events||{},by={};(it.timeframes||[]).forEach(z=>by[z.timeframe]=z);
 const price=num(t.price??t.ltp??x.price);set('marketSymbol',symbol.replace('USD','/USD'));set('price',fmtExact(t.price_exact??t.price??t.ltp??x.price));const chPct=num(t.change_24h_pct);set('change',chPct===null?'24h change unavailable':`24h ${chPct>=0?'+':''}${fmt(chPct,4)}%`);set('dayHigh',fmtExact(t.high_exact??t.high??t.day_high??x.day_high));set('dayLow',fmtExact(t.low_exact??t.low??t.day_low??x.day_low));set('dayVolume',fmt(t.volume,0));set('openInterest',fmt(t.oi??x.open_interest,0));set('volumeEffect','24h traded amount. High volume confirms a move only when price direction agrees; volume alone is not bullish or bearish.');set('oiEffect', 'Current OI is a snapshot, not OI change. Rising OI + rising price can indicate bullish position build-up; rising OI + falling price can indicate bearish build-up. Falling OI often means positions are closing.');
 const decision=String(x.recommendation||x.signal||'WAIT').toUpperCase();set('decision',decision);set('whyDecision',decision);paintBias('decision',decision);paintBias('whyDecision',decision);const conf=num(x.confidence??x.overall_confidence);set('confidence',`Strength ${fmt(conf,0)}/100`);if($('confidenceBar'))$('confidenceBar').style.width=`${Math.max(0,Math.min(100,conf||0))}%`;
 set('agreementMini',`Agreement ${ag.final||x.agreement||'—'}`);set('agreementMini2',ag.final||x.agreement||'—');paintBias('agreementMini',ag.final||x.agreement);paintBias('agreementMini2',ag.final||x.agreement);
 set('tf5',by['5m']?.trend||'—');set('tf15',by['15m']?.trend||'—');set('tf1h',by['1h']?.trend||'—');set('tf4h',by['4h']?.trend||by['1d']?.trend||'—');set('tf1d',by['1d']?.trend||'—');['tf5','tf15','tf1h','tf4h','tf1d'].forEach(id=>paintBias(id,$(id)?.textContent));
 set('intra5',by['5m']?.trend||'—');set('intra15',by['15m']?.trend||'—');set('intra1h',by['1h']?.trend||'—');set('intra4h',by['4h']?.trend||'—');set('intra1d',by['1d']?.trend||'—');['intra5','intra15','intra1h','intra4h','intra1d'].forEach(id=>paintBias(id,$(id)?.textContent));
 set('activityRegime',sess.activity||'—');set('relativeVolume',ii.relative_volume==null?'—':`${ii.relative_volume}x`);set('volumeRegime',ii.volume_regime||'—');
 renderTradePlan(x,price);set('eventRisk',ev.risk||'NORMAL');set('eventDisclaimer',ev.disclaimer||'Scheduled times are displayed in IST.');
 $('reasons').innerHTML=(x.reasons||[]).slice(0,6).map(r=>`<div>• ${esc(r)}</div>`).join('')||'<div>No high-quality reasons returned.</div>';
 const conflict=$('decisionConflict');if(conflict){const bias=String(ag.final||x.agreement||'').toUpperCase();const mismatch=(decision==='SELL'&&bias.includes('BULLISH'))||(decision==='BUY'&&bias.includes('BEARISH'));conflict.hidden=!mismatch;conflict.textContent=mismatch?`SIGNAL CONFLICT: AI says ${decision}, but agreement is ${bias}. Treat as WAIT until technical, options and trend signals align.`:'';}
 if(!window.NAKSHATRA_GLOBAL_CONTEXT){const eventList=(ev.watchlist||ev.upcoming||[]).slice(0,4);$('catalyst').innerHTML=eventList.map(e=>{const dt=e.date_ist||e.time_ist?[e.date_ist,e.time_ist].filter(Boolean).join(' • '):e.datetime_ist||'Time varies (IST)';return `<div class="catalyst-row"><div class="event-main"><strong>${esc(e.name)}</strong><span class="event-time">🕒 ${esc(dt)}</span><span class="effect-label">CRYPTO EFFECT</span><small>${esc(e.effect||'Possible volatility impact; direction depends on actual release vs expectations.')}</small></div><div class="event-right"><b>${esc(e.impact||'—')}</b><small>${esc(e.status||'')}</small></div></div>`}).join('')||'<div class="muted">No scheduled event data.</div>'; }
 const tech=x.technical||{};set('moduleTechnical',tech.signal||'—');set('moduleOption',o.signal||'—');set('moduleAstrology',ast.bias||'—');set('moduleAstrology2',ast.bias||'—');set('moduleNumerology',numx.bias||'—');set('moduleNumerology2',numx.bias||'—');set('trend',x.trend||it.overall||'—');paintBias('trend',x.trend||it.overall);paintBias('activityRegime',sess.activity);paintBias('sentimentBias',sent.bias||sent.signal||sent.overall);paintBias('riskState',$('riskState')?.textContent);paintBias('optionView',o.signal||'');
 $('metrics').innerHTML=[['EMA9',x.ema9],['EMA21',x.ema21],['EMA50',x.ema50],['EMA200',x.ema200],['RSI (14)',x.rsi],['Stochastic RSI',window.NAKSHATRA_STOCH_RSI??'Loading…'],['MACD',x.macd],['ATR',x.atr],['Technical Score',tech.score]].map(q=>{const v=num(q[1]);const c=(q[0]==='RSI (14)'||q[0]==='Stochastic RSI')?(v===null?'':v>=60?'bull':v<=40?'bear':'sideways'):(q[0]==='Technical Score'?(v===null?'':v>0?'bull':v<0?'bear':'sideways'):'');return `<div><small>${q[0]}</small><b class="${c}">${fmt(q[1],4)}</b></div>`}).join('');
 $('astroRows').innerHTML=[['Rashi Trend',ast.rashi_trend||ast.bias],['Nakshatra',ast.nakshatra_influence||ast.nakshatra],['Tithi',ast.tithi_impact||ast.tithi],['Yoga',ast.yoga],['Karana',ast.karana],['Planetary',ast.planetary_alignment],['Score',ast.score]].map(q=>`<div><span>${esc(q[0])}</span><b>${esc(q[1])}</b></div>`).join('');
 $('numRows').innerHTML=[['Life Path',numx.life_path],['Expression',numx.expression_number],['Day Vibration',numx.day_vibration],['Market Number',numx.market_number],['Score',numx.score]].map(q=>`<div><span>${esc(q[0])}</span><b>${esc(q[1])}</b></div>`).join('');
 const gc=window.NAKSHATRA_GLOBAL_CONTEXT||null;const gf=gc?.fear_greed;const sb=gf?.bias||sent.bias||sent.signal||sent.overall||'—';set('sentimentBias',sb);$('sentimentRows').innerHTML=[['Social Sentiment',sent.social_sentiment||'UNAVAILABLE — no social feed'],['News Sentiment',gc?.headlines?.length?`${gc.headlines.length} live headlines`:(sent.news_sentiment||'Not connected')],['Fear/Greed',gf?`${gf.label} (${gf.value})`:(sent.fear_greed||'Unavailable')],['Overall Score',gf?`${gf.bias} • F&G index`:(sent.score??'Unavailable')]].map(q=>`<div><span>${esc(q[0])}</span><b>${esc(q[1])}</b></div>`).join('');
 renderOption(o,price);
 set('agreeTechnical',ag.technical||'—');set('agreeOptions',ag.option_chain||'—');set('agreeAstrology',ag.astrology||'—');set('agreeNumerology',ag.numerology||'—');set('agreeFinal',ag.final||x.agreement||'—');
 $('status').textContent='● LIVE';$('dataState').textContent='● LIVE';$('updateStatus').textContent=`Updated ${new Date().toLocaleTimeString()}`;const ch=num(t.change_24h_pct);if($('change'))$('change').classList.toggle('bull',ch!==null&&ch>=0);if($('change'))$('change').classList.toggle('bear',ch!==null&&ch<0);paintValueBias();
}

async function loadStochRsi(){
 try{
  const res=await fetch(`/api/market-history?symbol=${encodeURIComponent(symbol)}&resolution=5m&limit=100&_=${Date.now()}`,{cache:'no-store'});
  if(!res.ok)throw Error('history unavailable');
  const d=await res.json();const rows=Array.isArray(d.rows)?d.rows:[];
  const closes=rows.map(r=>num(r.close)).filter(v=>v!==null);
  if(closes.length<30)throw Error('not enough candles');
  const rsis=[];
  for(let i=14;i<closes.length;i++){
   let gain=0,loss=0;for(let j=i-13;j<=i;j++){const delta=closes[j]-closes[j-1];if(delta>0)gain+=delta;else loss-=delta;}
   const avgGain=gain/14,avgLoss=loss/14;rsis.push(avgLoss===0?100:100-(100/(1+avgGain/avgLoss)));
  }
  const recent=rsis.slice(-14),lo=Math.min(...recent),hi=Math.max(...recent);
  const val=hi===lo?50:((recent[recent.length-1]-lo)/(hi-lo))*100;
  window.NAKSHATRA_STOCH_RSI=Number(val.toFixed(1));
  const metric=[...document.querySelectorAll('#metrics > div')].find(el=>el.textContent.includes('Stochastic RSI'));
  if(metric){const b=metric.querySelector('b');if(b)b.textContent=`${val.toFixed(1)} / 100`;const label=val>=80?'OVERBOUGHT':val<=20?'OVERSOLD':val>=55?'BULLISH MOMENTUM':val<=45?'BEARISH MOMENTUM':'SIDEWAYS';if(b){b.classList.remove('bull','bear','sideways');b.classList.add(val>=55?'bull':val<=45?'bear':'sideways')}metric.title=`Stochastic RSI (14): ${label}; extremes can persist in trends.`;}
 }catch(e){window.NAKSHATRA_STOCH_RSI='Unavailable';const metric=[...document.querySelectorAll('#metrics > div')].find(el=>el.textContent.includes('Stochastic RSI'));if(metric){const b=metric.querySelector('b');if(b)b.textContent='Unavailable';}}
}

async function loadDay(ticker){
  const px=num(ticker?.price);
  let delta=num(ticker?.change_24h_abs);
  if(delta===null) delta=num(ticker?.change_24h);
  let pct=num(ticker?.change_24h_pct);
  if(pct===null && delta!==null && px!==null && (px-delta)!==0) pct=delta/(px-delta)*100;
  if(delta===null || pct===null){
    try{
      const r=await fetch(`/api/market-history?symbol=${encodeURIComponent(symbol)}&resolution=1d&limit=3&_=${Date.now()}`,{cache:'no-store'});
      const d=await r.json(); const rows=d.rows||[];
      if(rows.length>=2){const prev=num(rows[rows.length-2].close),last=num(rows[rows.length-1].close);if(prev!==null&&last!==null&&prev!==0){delta=last-prev;pct=delta/prev*100;}}
    }catch(e){}
  }
  if(delta===null || pct===null){set('dayChange','—');set('dayChangePct','Change unavailable');set('dayChangeEffect','No reliable 24h comparison available for this symbol.');paintBias('dayChangeEffect','SIDEWAYS');return;}
  const dir=pct>0?'bull':pct<0?'bear':'sideways';
  set('dayChange',`${delta>0?'▲':delta<0?'▼':'•'} ${fmt(Math.abs(delta),8)}`);
  set('dayChangePct',`${pct>0?'+':''}${fmt(pct,4)}%`);
  const effect=pct>0?'BULLISH EFFECT: price is up over 24h; buyers have the advantage, but confirm with volume and trend.':pct<0?'BEARISH EFFECT: price is down over 24h; sellers have the advantage, but rebounds remain possible.':'SIDEWAYS EFFECT: net 24h change is near zero; direction is not established.';
  set('dayChangeEffect',effect);
  ['dayChange','dayChangePct','dayChangeEffect'].forEach(id=>{const el=$(id);if(el){el.classList.remove('bull','bear','sideways');el.classList.add(dir)}});
}

async function load(){if(busy)return;busy=true;try{const r=await fetch(`/api/live?symbol=${encodeURIComponent(symbol)}&_=${Date.now()}`,{cache:'no-store'});const d=await r.json();if(d.status==='OK'){render(d);loadDay(d.ticker||{});loadStochRsi()}else{set('status',d.status==='NO TICKER DATA'?'● NO TICKER DATA':'● DATA RISK');set('dataState',d.status==='NO TICKER DATA'?'● TICKER UNAVAILABLE':'● DATA RISK');set('marketSymbol',symbol.replace('USD','/USD'));['price','change','dayChange','dayChangePct','dayHigh','dayLow','dayVolume','openInterest'].forEach(id=>set(id,'—'));set('dayChangeEffect','Selected coin has no live ticker data.');set('volumeEffect','Volume unavailable for this coin.');set('oiEffect','Open interest unavailable for this coin.');set('updateStatus',d.message||'Data unavailable')}}catch(e){set('status','● OFFLINE');set('dataState','● OFFLINE');['price','change','dayChange','dayChangePct','dayHigh','dayLow','dayVolume','openInterest'].forEach(id=>set(id,'—'));set('dayChangeEffect','Selected coin has no live ticker data.');set('volumeEffect','Volume unavailable for this coin.');set('oiEffect','Open interest unavailable for this coin.');set('updateStatus','Connection error')}finally{busy=false}}
async function scanner(){try{const r=await fetch('/api/scanner?_='+Date.now(),{cache:'no-store'});const d=await r.json();const arr=Array.isArray(d)?d:(d.markets||[]);$('scanner').innerHTML=arr.map(x=>`<div class="scanner-row"><b>${esc(x.symbol)}</b><span class="${biasClass(x.signal||x.recommendation||'WAIT')}">${esc(x.signal||x.recommendation||'WAIT')}</span><small>${esc(x.strength??x.confidence??'—')}</small></div>`).join('')||'No scanner data'}catch(e){$('scanner').textContent='Scanner unavailable'}}
async function trades(){try{const r=await fetch('/api/history?_='+Date.now(),{cache:'no-store'});const d=await r.json();const arr=Array.isArray(d)?d:(d.history||[]);$('trades').innerHTML=(arr||[]).slice(-8).reverse().map(x=>`<tr><td>${esc(x.symbol)}</td><td>${esc(x.side)}</td><td>${esc(fmt(x.entry))}</td><td>${esc(fmt(x.pnl))}</td><td>${esc(x.status)}</td></tr>`).join('')||'<tr><td colspan="5">No trades yet</td></tr>';$('equitySummary').textContent=arr?.length?`${arr.length} recorded trades`:'No recorded trades'}catch(e){$('equitySummary').textContent='Trade history unavailable'}}
async function searchProducts(q){clearTimeout(productTimer);if(!q||q.length<1){$('searchResults').innerHTML='';return}productTimer=setTimeout(async()=>{try{const r=await fetch(`/api/products?q=${encodeURIComponent(q)}`);const d=await r.json();$('searchResults').innerHTML=(d.products||[]).slice(0,8).map(p=>`<button class="result-item" data-symbol="${esc(p.symbol)}"><span class="result-main"><b>${esc(p.symbol)}</b><small>${esc(p.description||p.contract_type||'Delta product')}</small></span><strong class="result-price">${p.price!==null&&p.price!==undefined&&p.price!==''?esc(p.price):'Price unavailable'}</strong></button>`).join('')||'<div class="empty-search">No live Delta crypto found</div>';document.querySelectorAll('.result-item').forEach(b=>b.onclick=()=>selectSymbol(b.dataset.symbol))}catch(e){$('searchResults').innerHTML='<div class="empty-search">Search unavailable</div>'}},120)}
document.querySelectorAll('.symbol').forEach(b=>b.onclick=()=>selectSymbol(b.dataset.symbol));$('cryptoSearch').addEventListener('input',e=>searchProducts(e.target.value));$('refreshBtn')?.addEventListener('click',()=>{load();scanner();trades()});load();scanner();trades();setInterval(()=>{load();scanner()},10000);
// Re-apply semantic colours to every dynamically refreshed section (tables, rows, scanner, option chain).
paintValueBias();const signalObserver=new MutationObserver(records=>{for(const rec of records){if(rec.type==='childList'){rec.addedNodes.forEach(n=>{if(n.nodeType===1)paintValueBias(n)});}else if(rec.type==='characterData'){const p=rec.target.parentElement;if(p)paintValueBias(p);}}});signalObserver.observe(document.body,{subtree:true,childList:true,characterData:true});
