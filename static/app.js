let symbol='BTCUSD',productTimer=null,liveRequestSeq=0,searchRequestSeq=0; window.NAKSHATRA_SYMBOL=symbol;
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
window.NAKSHATRA_CALENDAR_LIVE=true;
window.NAKSHATRA_CURRENT_REASONS=[];window.NAKSHATRA_CURRENT_RSI=null;window.NAKSHATRA_STOCH_RSI=window.NAKSHATRA_STOCH_RSI??null;
function indicatorRead(value,kind){
 const v=num(value);if(v===null)return {bias:'SIDEWAYS',label:'UNAVAILABLE',detail:'No reliable value returned for this selected coin.'};
 if(kind==='RSI'){
  if(v>=55)return {bias:'BULLISH',label:v>=70?'BULLISH • OVERBOUGHT RISK':'BULLISH',detail:v>=70?'Momentum is strong, but RSI is overbought; a pullback is possible.':'RSI above 55 supports positive momentum.'};
  if(v<=45)return {bias:'BEARISH',label:v<=30?'BEARISH • OVERSOLD RISK':'BEARISH',detail:v<=30?'Momentum is weak, but oversold conditions can bounce.':'RSI below 45 supports negative momentum.'};
  return {bias:'SIDEWAYS',label:'SIDEWAYS',detail:'RSI is in the middle zone; momentum is not decisive.'};
 }
 if(v>=55)return {bias:'BULLISH',label:v>=80?'BULLISH MOMENTUM • OVERBOUGHT':'BULLISH MOMENTUM',detail:v>=80?'Stochastic RSI is overbought; bullish momentum can persist, but pullback risk is elevated.':'Stochastic RSI above 55 shows stronger short-term momentum.'};
 if(v<=45)return {bias:'BEARISH',label:v<=20?'BEARISH MOMENTUM • OVERSOLD':'BEARISH MOMENTUM',detail:v<=20?'Stochastic RSI is oversold; bearish momentum can persist, but a bounce is possible.':'Stochastic RSI below 45 shows weaker short-term momentum.'};
 return {bias:'SIDEWAYS',label:'SIDEWAYS',detail:'Stochastic RSI is in the middle zone; wait for a clearer momentum shift.'};
}
function renderWhyReasons(){
 const root=$('reasons');if(!root)return;
 const rows=(window.NAKSHATRA_CURRENT_REASONS||[]).slice(0,6).map(r=>({text:String(r),bias:biasClass(r)||''}));
 const rsi=indicatorRead(window.NAKSHATRA_CURRENT_RSI,'RSI');
 const stoch=indicatorRead(window.NAKSHATRA_STOCH_RSI,'STOCH');
 rows.push({text:`RSI (14): ${num(window.NAKSHATRA_CURRENT_RSI)===null?'UNAVAILABLE':fmt(window.NAKSHATRA_CURRENT_RSI,2)} — ${rsi.label}. ${rsi.detail}`,bias:rsi.bias});
 rows.push({text:`Stochastic RSI (14): ${num(window.NAKSHATRA_STOCH_RSI)===null?'UNAVAILABLE':fmt(window.NAKSHATRA_STOCH_RSI,1)+' / 100'} — ${stoch.label}. ${stoch.detail}`,bias:stoch.bias});
 root.innerHTML=rows.map(r=>`<div class="why-reason ${r.bias?biasClass(r.bias):''}">• ${esc(r.text)}</div>`).join('')||'<div>No high-quality reasons returned.</div>';
}
async function loadCalendar(){
 window.NAKSHATRA_CALENDAR_LIVE=true;
 try{
  const r=await fetch(`/api/calendar?days=7&_=${Date.now()}`,{cache:'no-store'});const d=await r.json();
  const root=$('catalyst');if(!root)return;
  set('eventRisk',d.risk||'UNCONFIRMED');paintBias('eventRisk',d.risk||'SIDEWAYS');
  set('eventDisclaimer',`${d.source||'TradingView'} • ${d.updated_ist||'Update unavailable'}. ${d.disclaimer||''}`);
  if(d.status==='OK'&&Array.isArray(d.events)&&d.events.length){
   root.innerHTML=d.events.slice(0,10).map(e=>{
    const nums=[['Actual',e.actual],['Forecast',e.forecast],['Previous',e.previous]].filter(x=>x[1]!==null&&x[1]!==undefined&&x[1]!=='').map(x=>`${x[0]}: ${x[1]}`).join(' • ');
    return `<div class="catalyst-row calendar-event"><div class="event-main"><strong>${esc(e.name)}</strong><span class="event-time">🕒 ${esc(e.datetime_ist||'Time not supplied')} • ${esc(e.country||'Global')}</span><span class="calendar-impact ${biasClass(e.impact)||'sideways'}">${esc(e.importance||e.impact||'UNRATED')} IMPACT</span><small>${esc(e.effect||'Volatility possible; compare actual vs forecast before assigning direction.')}</small>${nums?`<small class="calendar-values">${esc(nums)}</small>`:''}</div><div class="event-right"><b>${esc(e.importance||'UNRATED')}</b><small>TradingView</small></div></div>`;
   }).join('');
   set('gmCalendarStatus','CONNECTED • TradingView');set('gmCalendarNote',`${d.events.length} scheduled event(s) loaded. Times are IST; event effects are conditional, not guaranteed.`);
  }else{
   root.innerHTML=`<div class="calendar-status"><b class="${d.status==='UNAVAILABLE'?'sideways':'bull'}">${d.status==='UNAVAILABLE'?'CALENDAR FEED UNAVAILABLE':'NO UPCOMING EVENTS RETURNED'}</b><p>${esc(d.message||'No events found for the selected period.')}</p><a href="${esc(d.source_url||'https://in.tradingview.com/economic-calendar/')}" target="_blank" rel="noopener">Open TradingView Economic Calendar ↗</a></div>`;
   set('gmCalendarStatus',d.status==='UNAVAILABLE'?'FEED UNAVAILABLE':'NO EVENTS');set('gmCalendarNote',d.disclaimer||'Open TradingView to verify scheduled events.');
  }
 }catch(e){const root=$('catalyst');if(root)root.innerHTML='<div class="calendar-status"><b class="sideways">CALENDAR FEED UNAVAILABLE</b><p>Could not load scheduled events. No events are invented.</p><a href="https://in.tradingview.com/economic-calendar/" target="_blank" rel="noopener">Open TradingView Economic Calendar ↗</a></div>';set('gmCalendarStatus','FEED UNAVAILABLE');set('gmCalendarNote','Could not reach the live calendar endpoint.');}
}
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
function selectSymbol(s){const next=String(s||'').toUpperCase().trim();if(!next)return;symbol=next;window.NAKSHATRA_SYMBOL=symbol;window.NAKSHATRA_STOCH_RSI=null;renderWhyReasons();document.querySelectorAll('.symbol').forEach(b=>b.classList.toggle('active',b.dataset.symbol===symbol));$('cryptoSearch').value='';$('searchResults').innerHTML='';set('marketSymbol',symbol.replace(/(USDT|USD)$/,'/$1'));set('status','● LOADING');set('dataState','● LOADING');set('updateStatus',`Loading ${symbol}…`);['price','dayChange','dayChangePct','dayHigh','dayLow','dayVolume','openInterest'].forEach(id=>set(id,'—'));set('dayChangeEffect','Fetching selected coin ticker…');set('volumeEffect','Fetching selected coin volume…');set('oiEffect','Fetching selected coin open interest…');window.dispatchEvent(new CustomEvent('nakshatra:symbol-changed',{detail:{symbol}}));load()}
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
 const price=num(t.price??t.ltp??x.price);set('marketSymbol',symbol.replace(/(USDT|USD)$/,'/$1'));set('price',fmtExact(t.price_exact??t.price??t.ltp??x.price));const chPct=num(t.change_24h_pct);set('change',chPct===null?'24h change unavailable':`24h ${chPct>=0?'+':''}${fmt(chPct,4)}%`);set('dayHigh',fmtExact(t.high_exact??t.high??t.day_high??x.day_high));set('dayLow',fmtExact(t.low_exact??t.low??t.day_low??x.day_low));set('dayVolume',fmt(t.volume,0));set('openInterest',fmt(t.oi??x.open_interest,0));const priceBias=chPct===null?'SIDEWAYS':chPct>0?'BULLISH':chPct<0?'BEARISH':'SIDEWAYS';set('volumeEffect',`${priceBias} PRICE CONTEXT: 24h traded volume is ${fmt(t.volume,0)}. Volume itself has no direction; ${priceBias==='BULLISH'?'rising price with above-normal volume supports buyers.':priceBias==='BEARISH'?'falling price with above-normal volume supports sellers.':'price is flat; wait for volume expansion and a breakout.'}`);paintBias('volumeEffect',priceBias);const oiChange=num(t.oi_change_pct??t.oi_change_24h_pct??t.open_interest_change_pct);if(oiChange!==null){const oiBias=oiChange>0&&chPct>0?'BULLISH':oiChange>0&&chPct<0?'BEARISH':oiChange<0?'SIDEWAYS':priceBias;set('oiEffect',`${oiBias}: OI change ${oiChange>0?'+':''}${fmt(oiChange,2)}%. ${oiChange>0?(chPct>0?'OI and price both rise: possible long build-up.':chPct<0?'OI rises while price falls: possible short build-up.':'OI rises without price direction; wait for breakout.'):'OI is falling: positions may be closing; squeeze direction is not confirmed.'}`);paintBias('oiEffect',oiBias)}else{set('oiEffect',`SIDEWAYS / UNCONFIRMED: current OI ${fmt(t.oi??x.open_interest,0)} is only a snapshot; no comparable OI-change feed is available, so bullish/bearish positioning cannot be confirmed.`);paintBias('oiEffect','SIDEWAYS')} 
 const decision=String(x.recommendation||x.signal||'WAIT').toUpperCase();set('decision',decision);set('whyDecision',decision);paintBias('decision',decision);paintBias('whyDecision',decision);const conf=num(x.confidence??x.overall_confidence);set('confidence',`Strength ${fmt(conf,0)}/100`);if($('confidenceBar'))$('confidenceBar').style.width=`${Math.max(0,Math.min(100,conf||0))}%`;
 set('agreementMini',`Agreement ${ag.final||x.agreement||'—'}`);set('agreementMini2',ag.final||x.agreement||'—');paintBias('agreementMini',ag.final||x.agreement);paintBias('agreementMini2',ag.final||x.agreement);
 set('tf5',by['5m']?.trend||'—');set('tf15',by['15m']?.trend||'—');set('tf1h',by['1h']?.trend||'—');set('tf4h',by['4h']?.trend||by['1d']?.trend||'—');set('tf1d',by['1d']?.trend||'—');['tf5','tf15','tf1h','tf4h','tf1d'].forEach(id=>paintBias(id,$(id)?.textContent));
 set('intra5',by['5m']?.trend||'—');set('intra15',by['15m']?.trend||'—');set('intra1h',by['1h']?.trend||'—');set('intra4h',by['4h']?.trend||'—');set('intra1d',by['1d']?.trend||'—');['intra5','intra15','intra1h','intra4h','intra1d'].forEach(id=>paintBias(id,$(id)?.textContent));
 set('activityRegime',sess.activity||'—');set('relativeVolume',ii.relative_volume==null?'—':`${ii.relative_volume}x`);set('volumeRegime',ii.volume_regime||'—');
 renderTradePlan(x,price);set('eventRisk',ev.risk||'NORMAL');set('eventDisclaimer',ev.disclaimer||'Scheduled times are displayed in IST.');
 window.NAKSHATRA_CURRENT_REASONS=Array.isArray(x.reasons)?x.reasons:[];window.NAKSHATRA_CURRENT_RSI=x.rsi;renderWhyReasons();
 const conflict=$('decisionConflict');if(conflict){const bias=String(ag.final||x.agreement||'').toUpperCase();const mismatch=(decision==='SELL'&&bias.includes('BULLISH'))||(decision==='BUY'&&bias.includes('BEARISH'));conflict.hidden=!mismatch;conflict.textContent=mismatch?`SIGNAL CONFLICT: AI says ${decision}, but agreement is ${bias}. Treat as WAIT until technical, options and trend signals align.`:'';}
 if(!window.NAKSHATRA_GLOBAL_CONTEXT&&!window.NAKSHATRA_CALENDAR_LIVE){const eventList=(ev.watchlist||ev.upcoming||[]).slice(0,4);$('catalyst').innerHTML=eventList.map(e=>{const dt=e.date_ist||e.time_ist?[e.date_ist,e.time_ist].filter(Boolean).join(' • '):e.datetime_ist||'Time varies (IST)';return `<div class="catalyst-row"><div class="event-main"><strong>${esc(e.name)}</strong><span class="event-time">🕒 ${esc(dt)}</span><span class="effect-label">CRYPTO EFFECT</span><small>${esc(e.effect||'Possible volatility impact; direction depends on actual release vs expectations.')}</small></div><div class="event-right"><b>${esc(e.impact||'—')}</b><small>${esc(e.status||'')}</small></div></div>`}).join('')||'<div class="muted">No scheduled event data.</div>'; }
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
 const targetSymbol=symbol;
 try{
  const res=await fetch(`/api/market-history?symbol=${encodeURIComponent(targetSymbol)}&resolution=5m&limit=100&_=${Date.now()}`,{cache:'no-store'});
  if(targetSymbol!==symbol)return;
  if(!res.ok)throw Error('history unavailable');
  const d=await res.json();if(targetSymbol!==symbol)return;const rows=Array.isArray(d.rows)?d.rows:[];
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
  if(metric){const b=metric.querySelector('b');if(b)b.textContent=`${val.toFixed(1)} / 100`;const label=val>=80?'OVERBOUGHT':val<=20?'OVERSOLD':val>=55?'BULLISH MOMENTUM':val<=45?'BEARISH MOMENTUM':'SIDEWAYS';if(b){b.classList.remove('bull','bear','sideways');b.classList.add(val>=55?'bull':val<=45?'bear':'sideways')}metric.title=`Stochastic RSI (14): ${label}; extremes can persist in trends.`;}renderWhyReasons();
 }catch(e){if(targetSymbol!==symbol)return;window.NAKSHATRA_STOCH_RSI='Unavailable';const metric=[...document.querySelectorAll('#metrics > div')].find(el=>el.textContent.includes('Stochastic RSI'));if(metric){const b=metric.querySelector('b');if(b)b.textContent='Unavailable';}renderWhyReasons();}
}

function renderFastTicker(d,requestedSymbol,requestId){if(requestId!==liveRequestSeq||requestedSymbol!==symbol||d.status!=='OK'||!d.ticker)return;const t=d.ticker;set('marketSymbol',requestedSymbol.replace(/(USDT|USD)$/,'/$1'));set('price',fmtExact(t.price_exact??t.price??t.ltp));set('dayHigh',fmtExact(t.high_exact??t.high??t.day_high));set('dayLow',fmtExact(t.low_exact??t.low??t.day_low));set('dayVolume',fmt(t.volume,0));set('openInterest',fmt(t.oi??t.open_interest,0));set('status','● LIVE');set('dataState','● LIVE TICKER');set('updateStatus',`Ticker updated for ${requestedSymbol}`);const pct=num(t.change_24h_pct),bias=pct===null?'SIDEWAYS':pct>0?'BULLISH':pct<0?'BEARISH':'SIDEWAYS';set('volumeEffect',`${bias} PRICE CONTEXT: volume is ${fmt(t.volume,0)}. Volume confirms direction only against a volume baseline; volume alone is not directional.`);paintBias('volumeEffect',bias);set('oiEffect',`SIDEWAYS / UNCONFIRMED: current OI ${fmt(t.oi??t.open_interest,0)} is a snapshot; OI change is not provided by this ticker.`);paintBias('oiEffect','SIDEWAYS');loadDay(t,requestedSymbol,requestId)}
async function fetchFastTicker(requestedSymbol,requestId){try{const r=await fetch(`/api/ticker?symbol=${encodeURIComponent(requestedSymbol)}&_=${Date.now()}`,{cache:'no-store'});const d=await r.json();renderFastTicker(d,requestedSymbol,requestId)}catch(e){/* the full /api/live request below provides the visible error state */}}
async function loadDay(ticker,requestedSymbol=symbol,requestId=liveRequestSeq){
  const px=num(ticker?.price);
  let delta=num(ticker?.change_24h_abs);
  if(delta===null) delta=num(ticker?.change_24h);
  let pct=num(ticker?.change_24h_pct);
  if(pct===null && delta!==null && px!==null && (px-delta)!==0) pct=delta/(px-delta)*100;
  if(delta===null || pct===null){
    try{
      const r=await fetch(`/api/market-history?symbol=${encodeURIComponent(requestedSymbol)}&resolution=1d&limit=3&_=${Date.now()}`,{cache:'no-store'});
      const d=await r.json(); const rows=d.rows||[];
      if(rows.length>=2){const prev=num(rows[rows.length-2].close),last=num(rows[rows.length-1].close);if(prev!==null&&last!==null&&prev!==0){delta=last-prev;pct=delta/prev*100;}}
    }catch(e){}
  }
  if(requestId!==liveRequestSeq||requestedSymbol!==symbol)return;
  if(delta===null || pct===null){set('dayChange','—');set('dayChangePct','Change unavailable');set('dayChangeEffect','No reliable 24h comparison available for this symbol.');paintBias('dayChangeEffect','SIDEWAYS');return;}
  const dir=pct>0?'bull':pct<0?'bear':'sideways';
  set('dayChange',`${delta>0?'▲':delta<0?'▼':'•'} ${fmt(Math.abs(delta),8)}`);
  set('dayChangePct',`${pct>0?'+':''}${fmt(pct,4)}%`);
  const effect=pct>0?'BULLISH EFFECT: price is up over 24h; buyers have the advantage, but confirm with volume and trend.':pct<0?'BEARISH EFFECT: price is down over 24h; sellers have the advantage, but rebounds remain possible.':'SIDEWAYS EFFECT: net 24h change is near zero; direction is not established.';
  set('dayChangeEffect',effect);
  ['dayChange','dayChangePct','dayChangeEffect'].forEach(id=>{const el=$(id);if(el){el.classList.remove('bull','bear','sideways');el.classList.add(dir)}});
}

async function load(){const requestId=++liveRequestSeq;const requestedSymbol=symbol;fetchFastTicker(requestedSymbol,requestId);try{const r=await fetch(`/api/live?symbol=${encodeURIComponent(requestedSymbol)}&_=${Date.now()}`,{cache:'no-store'});const d=await r.json();if(requestId!==liveRequestSeq||requestedSymbol!==symbol)return;if(d.status==='OK'&&d.ticker){render(d);loadDayForSymbol(d.ticker||{},requestedSymbol,requestId);loadStochRsi()}else{const msg=d.message||'Live ticker unavailable for this listed contract';set('status','● NO TICKER');set('dataState','● NO TICKER');set('marketSymbol',requestedSymbol.replace(/(USDT|USD)$/,'/$1'));['price','change','dayChange','dayChangePct','dayHigh','dayLow','dayVolume','openInterest'].forEach(id=>set(id,'—'));set('dayChangeEffect',msg);set('volumeEffect','Volume feed unavailable for this symbol.');set('oiEffect','Open-interest feed unavailable for this symbol.');set('updateStatus',msg);paintBias('dayChangeEffect','SIDEWAYS');paintBias('volumeEffect','SIDEWAYS');paintBias('oiEffect','SIDEWAYS')}}catch(e){if(requestId!==liveRequestSeq)return;set('status','● CONNECTION ERROR');set('dataState','● CONNECTION ERROR');['price','change','dayChange','dayChangePct','dayHigh','dayLow','dayVolume','openInterest'].forEach(id=>set(id,'—'));set('dayChangeEffect','Could not reach the live ticker API.');set('volumeEffect','Volume unavailable while API is unreachable.');set('oiEffect','Open interest unavailable while API is unreachable.');set('updateStatus','Connection error');paintBias('dayChangeEffect','SIDEWAYS');paintBias('volumeEffect','SIDEWAYS');paintBias('oiEffect','SIDEWAYS')}}
async function loadDayForSymbol(ticker,requestedSymbol,requestId){const previous=symbol;if(previous!==requestedSymbol)return;await loadDay(ticker,requestedSymbol,requestId)}
async function scanner(){try{const r=await fetch('/api/scanner?_='+Date.now(),{cache:'no-store'});const d=await r.json();const arr=Array.isArray(d)?d:(d.markets||[]);$('scanner').innerHTML=arr.map(x=>`<div class="scanner-row"><b>${esc(x.symbol)}</b><span class="${biasClass(x.signal||x.recommendation||'WAIT')}">${esc(x.signal||x.recommendation||'WAIT')}</span><small>${esc(x.strength??x.confidence??'—')}</small></div>`).join('')||'No scanner data'}catch(e){$('scanner').textContent='Scanner unavailable'}}
async function trades(){try{const r=await fetch('/api/history?_='+Date.now(),{cache:'no-store'});const d=await r.json();const arr=Array.isArray(d)?d:(d.history||[]);$('trades').innerHTML=(arr||[]).slice(-8).reverse().map(x=>`<tr><td>${esc(x.symbol)}</td><td>${esc(x.side)}</td><td>${esc(fmt(x.entry))}</td><td>${esc(fmt(x.pnl))}</td><td>${esc(x.status)}</td></tr>`).join('')||'<tr><td colspan="5">No trades yet</td></tr>';$('equitySummary').textContent=arr?.length?`${arr.length} recorded trades`:'No recorded trades'}catch(e){$('equitySummary').textContent='Trade history unavailable'}}
async function searchProducts(q){clearTimeout(productTimer);const query=String(q||'').trim();const requestId=++searchRequestSeq;if(!query){$('searchResults').innerHTML='';return}$('searchResults').innerHTML='<div class="search-loading">Searching live Delta contracts…</div>';productTimer=setTimeout(async()=>{try{const r=await fetch(`/api/products?q=${encodeURIComponent(query)}&_=${Date.now()}`,{cache:'no-store'});const d=await r.json();if(requestId!==searchRequestSeq||$('cryptoSearch').value.trim()!==query)return;const products=(d.products||[]).slice(0,8);$('searchResults').innerHTML=products.map(p=>`<button type="button" class="result-item" data-symbol="${esc(p.symbol)}"><span class="result-main"><b>${esc(p.symbol)}</b><small>${esc(p.description||p.contract_type||'Delta product')} · ${p.price!==null&&p.price!==undefined&&p.price!==''?'LIVE TICKER':'TICKER UNAVAILABLE'}</small></span><strong class="result-price">${p.price!==null&&p.price!==undefined&&p.price!==''?esc(p.price):'—'}</strong></button>`).join('')||'<div class="empty-search">No matching live Delta crypto contract found. Try the exact Delta symbol, e.g. DOGEUSD.</div>';document.querySelectorAll('.result-item').forEach(b=>b.onclick=()=>selectSymbol(b.dataset.symbol))}catch(e){if(requestId===searchRequestSeq)$('searchResults').innerHTML='<div class="empty-search">Delta search API unavailable. Check Render logs.</div>'}},180)}
document.querySelectorAll('.symbol').forEach(b=>b.onclick=()=>selectSymbol(b.dataset.symbol));$('cryptoSearch').addEventListener('input',e=>searchProducts(e.target.value));$('refreshBtn')?.addEventListener('click',()=>{load();scanner();trades()});load();scanner();trades();setInterval(()=>{load();scanner()},10000);
// Accessible collapsible cards: every analytics/global section can be expanded or collapsed.
function enableSectionDropdowns(){
 const cards=[...document.querySelectorAll('.card,.global-card')];
 cards.forEach((card,index)=>{if(card.dataset.collapseReady==='1')return;card.dataset.collapseReady='1';
   let head=card.querySelector(':scope > .section-head, :scope > .global-card-head');
   if(!head){const h=card.querySelector(':scope > h2, :scope > h3');if(h)head=h;else if(card.classList.contains('tf-strip')){head=document.createElement('div');head.className='section-head generated-collapse-head';head.innerHTML='<h2>⏱ Timeframe Signals</h2>';card.insertBefore(head,card.firstChild)}else{head=document.createElement('div');head.className='generated-collapse-head';card.insertBefore(head,card.firstChild)}}
   const btn=document.createElement('button');btn.type='button';btn.className='collapse-toggle';btn.setAttribute('aria-expanded','true');btn.setAttribute('aria-label','Collapse section');btn.textContent='−';head.appendChild(btn);
   btn.addEventListener('click',ev=>{ev.preventDefault();ev.stopPropagation();const collapsed=card.classList.toggle('is-collapsed');btn.textContent=collapsed?'+':'−';btn.setAttribute('aria-expanded',String(!collapsed));btn.setAttribute('aria-label',collapsed?'Expand section':'Collapse section');});
 });
}
enableSectionDropdowns();loadCalendar();setInterval(loadCalendar,300000);
(function enableGlobalMonitorDropdown(){const wrap=document.querySelector('#globalMarketSection');const head=wrap?.querySelector(':scope > .global-title-row');if(!wrap||!head||head.querySelector('.collapse-toggle'))return;const btn=document.createElement('button');btn.type='button';btn.className='collapse-toggle';btn.textContent='−';btn.setAttribute('aria-expanded','true');btn.setAttribute('aria-label','Collapse global intelligence');head.appendChild(btn);btn.addEventListener('click',()=>{const collapsed=wrap.classList.toggle('is-collapsed');btn.textContent=collapsed?'+':'−';btn.setAttribute('aria-expanded',String(!collapsed));btn.setAttribute('aria-label',collapsed?'Expand global intelligence':'Collapse global intelligence')})})();
// Re-apply semantic colours to every dynamically refreshed section (tables, rows, scanner, option chain).
paintValueBias();const signalObserver=new MutationObserver(records=>{for(const rec of records){if(rec.type==='childList'){rec.addedNodes.forEach(n=>{if(n.nodeType===1)paintValueBias(n)});}else if(rec.type==='characterData'){const p=rec.target.parentElement;if(p)paintValueBias(p);}}});signalObserver.observe(document.body,{subtree:true,childList:true,characterData:true});
