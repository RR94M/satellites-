/* The app shell shared by every page: the tab bar, the alerts badge, offline support and the install prompt.
   The badge counts things that matter where you are (a storm heading your way, a nearby earthquake or eruption,
   aurora possible tonight) that you haven't seen on the Alerts page yet. */
(function(){
  const TABS=[
    ['./','Globe','<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.8 3 2.8 15 0 18M12 3c-2.8 3-2.8 15 0 18"/>'],
    ['tonight.html','Tonight','<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/><path d="M17 3v3M15.5 4.5h3"/>'],
    ['launches.html','Launches','<path d="M12 2c3 2.5 4.5 6 4 11l-2 3h-4l-2-3c-.5-5 1-8.5 4-11z"/><circle cx="12" cy="9" r="1.6"/><path d="M8.5 13 6 16l2 1M15.5 13 18 16l-2 1M11 19l1 3 1-3"/>'],
    ['spaceweather.html','Space','<circle cx="12" cy="12" r="4"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>'],
    ['alerts.html','Alerts','<path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>']];
  const here=(location.pathname.split('/').pop()||'').replace(/^index\.html$/,'')||'./';
  const nav=document.createElement('nav'); nav.className='tabbar'; nav.setAttribute('aria-label','Pages');
  nav.innerHTML=TABS.map(([href,label,icon])=>{ const on=href===here||(href==='./'&&here==='./');
    return '<a href="'+href+'"'+(on?' class="on" aria-current="page"':'')+'><svg viewBox="0 0 24 24" aria-hidden="true">'+icon+'</svg>'+label+(label==='Alerts'?'<span class="badge" id="alertBadge" hidden></span>':'')+'</a>'; }).join('');
  const put=()=>{ document.body.prepend(nav); };
  if(document.body) put(); else document.addEventListener('DOMContentLoaded',put);

  // ---------- jump chips: smooth scroll and highlight the section on screen (pages re-render, so watch for new rows) ----------
  let io=null;
  function wireJump(){ const row=document.querySelector('.jump'); if(!row||row.dataset.wired) return; row.dataset.wired='1';
    const links=[...row.querySelectorAll('a[href^="#"]')], map=new Map(links.map(a=>[a.getAttribute('href').slice(1),a]));
    links.forEach(a=>a.addEventListener('click',e=>{ const t=document.getElementById(a.getAttribute('href').slice(1)); if(!t) return; e.preventDefault(); t.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'}); }));
    if(io) io.disconnect(); io=new IntersectionObserver(es=>{ for(const e of es) if(e.isIntersecting){ const a=map.get(e.target.id); if(a){ links.forEach(x=>x.classList.toggle('on',x===a)); const l=a.offsetLeft-row.offsetLeft, r=l+a.offsetWidth; if(l<row.scrollLeft||r>row.scrollLeft+row.clientWidth) row.scrollLeft=l-12; /* not scrollIntoView: it would cancel the page's smooth scroll */ } } },{rootMargin:'-30% 0px -60% 0px'});
    map.forEach((a,id)=>{ const t=document.getElementById(id); if(t) io.observe(t); }); }
  new MutationObserver(wireJump).observe(document.documentElement,{childList:true,subtree:true});

  // ---------- offline and "add to home screen" ----------
  if('serviceWorker' in navigator&&location.protocol==='https:') navigator.serviceWorker.register('sw.js').catch(()=>{});
  let deferred=null; const get=k=>{ try{ return localStorage.getItem(k); }catch(e){ return null; } }, set=(k,v)=>{ try{ localStorage.setItem(k,v); }catch(e){} };
  const standalone=matchMedia('(display-mode: standalone)').matches||navigator.standalone;
  const visits=(+get('ovh:visits')||0)+1; set('ovh:visits',visits);
  function hint(html,go){ if(standalone||get('ovh:installHint')) return; const d=document.createElement('div'); d.className='installhint'; d.innerHTML='<span style="font-size:22px">🛰️</span><span style="flex:1">'+html+'</span>'+(go?'<button class="go">Install</button>':'')+'<button class="no" aria-label="Not now">Not now</button>';
    d.querySelector('.no').onclick=()=>{ set('ovh:installHint','1'); d.remove(); }; if(go) d.querySelector('.go').onclick=()=>{ set('ovh:installHint','1'); d.remove(); go(); }; document.body.appendChild(d); }
  window.addEventListener('beforeinstallprompt',e=>{ e.preventDefault(); deferred=e; if(visits>=2) hint('<b>Install Overhead</b> on your home screen: opens full screen, works offline.',()=>deferred.prompt()); });
  const ios=/iPhone|iPad|iPod/.test(navigator.userAgent)&&!/CriOS|FxiOS|FBAN|Instagram/.test(navigator.userAgent);
  if(ios&&visits>=2) setTimeout(()=>hint('<b>Add Overhead to your home screen:</b> tap the Share button, then “Add to Home Screen”.'),2500);

  // ---------- the alerts badge ----------
  const WX='https://raw.githubusercontent.com/RR94M/satellites-/weather/', DATA='https://raw.githubusercontent.com/RR94M/satellites-/data/';
  let loc=null; try{ loc=JSON.parse(get('ovh:loc')||'null'); }catch(e){}
  const km=(a,b,c,d)=>{ const r=Math.PI/180, p=a*r, q=c*r, dl=(d-b)*r; return 6371*2*Math.asin(Math.sqrt(Math.sin((q-p)/2)**2+Math.cos(p)*Math.cos(q)*Math.sin(dl/2)**2)); };
  const j=u=>fetch(u,{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null);
  // ids of things that matter near you right now (the Alerts page shows the same, with details)
  async function important(){ if(!loc) return []; const [st,q,v,kp]=await Promise.all([j(WX+'storms.json'),j(WX+'quakes.json'),j(WX+'volcanoes.json'),j(DATA+'kp-forecast.json')]); const now=Date.now(), out=[];
    for(const s of (st&&st.storms)||[]){ const pts=[s.at].concat((s.forecast||[]).map(p=>[p[0],p[1]])).filter(Boolean); if(pts.some(p=>km(loc.lat,loc.lon,p[1],p[0])<800)) out.push('storm:'+s.id); }
    for(const e of (q&&q.quakes)||[]) if(e.time>now-2*864e5&&e.lat!=null&&(km(loc.lat,loc.lon,e.lat,e.lon)<300||(e.mag>=6&&km(loc.lat,loc.lon,e.lat,e.lon)<1000))) out.push('quake:'+e.id);
    for(const x of (v&&v.volcanoes)||[]) if(x.erupting&&x.lat!=null&&km(loc.lat,loc.lon,x.lat,x.lon)<300) out.push('volcano:'+x.number);
    if(window.AURORA&&Array.isArray(kp)){ const need=AURORA.kpNeeded(loc.lat,loc.lon), top=kp.filter(x=>{ const t=Date.parse(x.time_tag+'Z'); return t+3*36e5>now&&t<now+864e5; }).reduce((m,x)=>Math.max(m,+x.kp),0);
      if(need<8.5&&top>=need) out.push('aurora:'+new Date().toISOString().slice(0,10)); }
    return out; }
  const seen=()=>{ try{ return new Set(JSON.parse(get('ovh:seen')||'[]')); }catch(e){ return new Set(); } };
  window.OVERHEAD={ markSeen:async()=>{ const ids=await important(); set('ovh:seen',JSON.stringify(ids)); const b=document.getElementById('alertBadge'); if(b) b.hidden=true; } };
  async function badge(){ if(here==='alerts.html'){ window.OVERHEAD.markSeen(); return; } const ids=await important(), s=seen(), fresh=ids.filter(i=>!s.has(i)); const b=document.getElementById('alertBadge');
    if(b){ b.textContent=fresh.length; b.hidden=!fresh.length; b.parentNode.setAttribute('aria-label','Alerts'+(fresh.length?', '+fresh.length+' new for you':'')); } }
  setTimeout(badge,1500); setInterval(()=>{ if(document.visibilityState==='visible') badge(); },15*6e4);
})();
