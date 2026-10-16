(() => {
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '—').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const n = v => { const x = Number(v); return v === null || v === undefined || v === '' || !Number.isFinite(x) ? null : x; };
  const fmt = (v, digits=2) => { const x=n(v); return x===null?'—':x.toLocaleString('en-US',{maximumFractionDigits:digits}); };
  const pct = (v) => { const x=n(v); return x===null?'—':`${x>0?'+':''}${x.toFixed(2)}%`; };
  const bias = v => { const s=String(v||'').toUpperCase(); if(s.includes('BULL')||s.includes('ABOVE'))return 'bull'; if(s.includes('BEAR')||s.includes('BELOW'))return 'bear'; if(s.includes('SIDE')||s.includes('NEUTRAL')||s.includes('NORMAL')||s.includes('LIMITED')||s.includes('UNCONFIRMED')||s.includes('NOT CALIBRATED'))return 'sideways'; return ''; };
  function text(id, value, cls) { const el=$(id); if(!el)return; el.textContent=value ?? '—'; if(cls!==undefined){el.classList.remove('bull','bear','sideways');const c=bias(cls);if(c)el.classList.add(c);} }
  function render(d){
    const w=d.early_warning||{}, sm=d.smart_money||{}, liq=d.liquidation_risk||{}, prob=d.probability||{};
    text('gmAlertLevel',w.level||'—',w.level); text('gmAlertTitle',w.title||'No alert data',w.direction); text('gmAlertMethod',w.method||'');
    $('gmAlertReasons').innerHTML=`<ul>${(w.reasons||[]).map(x=>`<li>${esc(x)}</li>`).join('')||'<li>No reasons returned.</li>'}</ul>`;
    text('gmConsensus',d.consensus||'UNCONFIRMED',d.consensus); text('gmMeanPrice',d.global_mean_price===null?'Unavailable':`$${fmt(d.global_mean_price,2)}`);
    text('gmMedianChange',pct(d.median_change_24h_pct),n(d.median_change_24h_pct)===null?'SIDEWAYS':(n(d.median_change_24h_pct)>=0.25?'BULLISH':(n(d.median_change_24h_pct)<=-0.25?'BEARISH':'SIDEWAYS')));
    text('gmAgreement',d.consensus_ratio===null?'—':`${fmt(d.consensus_ratio,0)}%`); text('gmProviders',`${d.available_count??0}/${d.provider_count??0}`);
    text('gmUpdated',d.updated_at?`Updated ${new Date(d.updated_at).toLocaleTimeString()}`:'Update time unavailable');
    const rows=d.exchanges||[];
    $('gmExchangeRows').innerHTML=rows.map(r=>{
      const status=r.status==='OK'?'<span class="bull gm-status-text">● ONLINE</span>':`<span class="gm-unavailable" title="${esc(r.note||'Provider unavailable')}">● UNAVAILABLE</span>`;
      const c=n(r.change_24h_pct);const ccls=c===null?'':(c>=0.25?'bull':c<=-0.25?'bear':'sideways');
      return `<tr><td><strong>${esc(r.exchange)}</strong></td><td>${esc(r.market)}</td><td>${r.price===null?'—':`$${fmt(r.price,2)}`}</td><td class="${ccls}">${pct(c)}</td><td>${fmt(r.volume_24h,0)}</td><td>${status}</td></tr>`;
    }).join('')||'<tr><td colspan="6">No exchange rows returned.</td></tr>';
    text('gmOpenInterest',sm.open_interest===null?'Not available':fmt(sm.open_interest,0)); text('gmFunding',sm.funding_rate_pct===null?'Not available':`${fmt(sm.funding_rate_pct,5)}%`);
    text('gmBookImbalance',sm.order_book_imbalance===null?'Not connected':`${fmt(sm.order_book_imbalance,2)}%`); text('gmDerivSource',[sm.open_interest_source,sm.funding_source].filter(Boolean).join(' / ')||'No derivatives feed'); text('gmSmartNote',sm.note||'');
    const divs=d.divergences||[]; $('gmDivergences').innerHTML=divs.length?divs.map(x=>`<div class="gm-divergence-row"><span>${esc(x.exchange)} <small>${esc(x.market)}</small></span><b class="${x.deviation_pct>0?'bull':'bear'}">${x.deviation_pct>0?'+':''}${fmt(x.deviation_pct,3)}%</b></div>`).join(''):'<div class="gm-divergence-row">No material price deviation detected across currently available providers.</div>';
    text('gmLiqStatus',liq.status||'UNCONFIRMED',liq.status); text('gmSqueeze',liq.long_short_squeeze||'UNCONFIRMED'); text('gmLiqNote',liq.note||'');
    text('gmProbabilityStatus',prob.status||'NOT CALIBRATED',prob.status); text('gmUpProbability',prob.up_pct===null?'Not published':`${fmt(prob.up_pct,1)}%`); text('gmDownProbability',prob.down_pct===null?'Not published':`${fmt(prob.down_pct,1)}%`); text('gmProbabilityNote',prob.note||'');
  }
  let busy=false;
  async function load(force=false){if(busy)return;busy=true;const b=$('globalRefreshBtn');if(b){b.disabled=true;b.textContent='Refreshing…';}try{const r=await fetch(`/api/global-market/snapshot${force?'?force=true':''}`,{cache:'no-store'});if(!r.ok)throw new Error(`HTTP ${r.status}`);render(await r.json());}catch(e){text('gmAlertTitle','Global exchange data temporarily unavailable');text('gmAlertReasons',String(e.message||e));text('gmAlertLevel','OFFLINE','SIDEWAYS');}finally{busy=false;if(b){b.disabled=false;b.textContent='↻ Refresh global data';}}}
  document.addEventListener('DOMContentLoaded',()=>{if(!$('globalMarketSection'))return;const b=$('globalRefreshBtn');if(b)b.addEventListener('click',()=>load(true));load();window.setInterval(()=>load(false),15000);});
})();
