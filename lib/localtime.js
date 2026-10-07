/* Times in the observer's own time zone, not the phone's. Needs lib/tz-lookup.js loaded first.
   localTime(lat, lon) works out the zone from the coordinates (offline), falling back to the phone's zone. */
function localTime(lat, lon){
  const device=Intl.DateTimeFormat().resolvedOptions().timeZone;
  let zone=device;
  try{ const z=typeof tzlookup==='function'?tzlookup(lat,lon):null; if(z){ new Intl.DateTimeFormat('en',{timeZone:z}); zone=z; } }catch(e){}
  const numeric=new Intl.DateTimeFormat('en-US',{timeZone:zone,hourCycle:'h23',year:'numeric',month:'numeric',day:'numeric',hour:'numeric',minute:'numeric'});
  const parts=t=>{ const o={}; for(const p of numeric.formatToParts(new Date(t))) if(p.type!=='literal') o[p.type]=+p.value; o.hour%=24; return o; };
  const dayNumber=t=>{ const p=parts(t); return Date.UTC(p.year,p.month-1,p.day)/864e5; };
  // the instant a given wall-clock time happens in this zone
  const at=(y,mo,d,h)=>{ let g=Date.UTC(y,mo-1,d,h); for(let i=0;i<2;i++){ const p=parts(g); g-=Date.UTC(p.year,p.month-1,p.day,p.hour,p.minute)-Date.UTC(y,mo-1,d,h); } return g; };
  const time=t=>new Date(t).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit',timeZone:zone});
  const date=(t,opts)=>new Date(t).toLocaleDateString(undefined,Object.assign({timeZone:zone},opts));
  // The short zone name ("BST", "EDT", "AEDT") only appears in the English variant of that country, so a phone set to
  // US English would show London as "GMT+1". Try the phone's own English first, then the others, and use the first real
  // name found; places with no common short name keep "GMT+9" style.
  const own=(navigator.language||'').toLowerCase().startsWith('en')?[navigator.language]:[];
  const namers=[...own,'en-GB','en-US','en-AU','en-IN','en-IE','en-ZA','en-NZ','en-CA'].map(l=>{ try{ return new Intl.DateTimeFormat(l,{timeZone:zone,timeZoneName:'short'}); }catch(e){ return null; } }).filter(Boolean);
  const abbrAt=t=>{ let fallback=zone; for(const f of namers){ const v=(f.formatToParts(new Date(t)).find(p=>p.type==='timeZoneName')||{}).value; if(!v) continue; if(/^[A-Z]{2,5}$/.test(v)) return v; if(fallback===zone) fallback=v; } return fallback; };
  const abbr=abbrAt(Date.now());
  return {
    zone, abbr, abbrAt, time, date,
    same: zone===device || time(Date.now())===new Date().toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'}),
    hour: t=>parts(t).hour,
    // local noon starting the night you're in: after midnight "tonight" still means the night that began yesterday
    nightStart(t){ const p=parts(t); let s=at(p.year,p.month,p.day,12); if(p.hour<12){ const q=parts(s-864e5); s=at(q.year,q.month,q.day,12); } return s; },
    nextNoon(s){ const q=parts(s+30*36e5); return at(q.year,q.month,q.day,12); },
    when(t){ const diff=dayNumber(t)-dayNumber(Date.now()), am=parts(t).hour<12;
      const name=diff===0?(am?'This morning':'Tonight'):diff===1?(am?'Tomorrow morning':'Tomorrow evening'):date(t,{weekday:'long',day:'numeric',month:'short'});
      return name+' '+time(t); },
  };
}
