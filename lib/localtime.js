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
  let abbr=zone; try{ abbr=(new Intl.DateTimeFormat(undefined,{timeZone:zone,timeZoneName:'short'}).formatToParts(new Date()).find(p=>p.type==='timeZoneName')||{}).value||zone; }catch(e){}
  return {
    zone, abbr, time, date,
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
