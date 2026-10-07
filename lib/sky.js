/* Sun position and satellite sightings, shared by the Tonight and Alerts pages. Needs satellite.js.
   Rules for a sighting (checked against astropy): at least 10 degrees up, your sky dark (Sun more than 6 degrees
   below the horizon), and the satellite itself still in sunlight. */
const SKY=(function(){
  const D2R=Math.PI/180;
  function sunEcf(d){ const j=d.getTime()/864e5-10957.5, L=(280.46+0.9856474*j)%360, g=(357.528+0.9856003*j)*D2R;
  const lam=(L+1.915*Math.sin(g)+0.02*Math.sin(2*g))*D2R, eps=23.439*D2R;
  const dec=Math.asin(Math.sin(eps)*Math.sin(lam)), ra=Math.atan2(Math.cos(eps)*Math.sin(lam),Math.cos(lam)), lon=ra-satellite.gstime(d);
  return {x:Math.cos(dec)*Math.cos(lon),y:Math.cos(dec)*Math.sin(lon),z:Math.sin(dec)}; }
  function observer(lat,lon){ const o={latitude:lat*D2R,longitude:lon*D2R,height:0}, e=satellite.geodeticToEcf(o), n=Math.hypot(e.x,e.y,e.z); return {geo:o,up:{x:e.x/n,y:e.y/n,z:e.z/n}}; }
  const sunAlt=(obs,d)=>{ const s=sunEcf(d); return Math.asin(obs.up.x*s.x+obs.up.y*s.y+obs.up.z*s.z)/D2R; };
  function passes(rec,obs,from,to,max){ const out=[]; let cur=null;
  for(let t=from;t<to;t+=30e3){ const d=new Date(t), pv=satellite.propagate(rec,d); if(!pv.position||typeof pv.position!=='object') continue;
    const p=satellite.eciToEcf(pv.position,satellite.gstime(d)), la=satellite.ecfToLookAngles(obs.geo,p), el=la.elevation/D2R;
    let vis=false;
    if(el>=10&&sunAlt(obs,d)<-6){ const S=sunEcf(d), along=p.x*S.x+p.y*S.y+p.z*S.z, r2=p.x*p.x+p.y*p.y+p.z*p.z; vis=along>0||Math.sqrt(Math.max(0,r2-along*along))>6371; }
    if(vis){ if(!cur) cur={start:t,end:t,startAz:la.azimuth,endAz:la.azimuth,maxEl:el,track:[]}; cur.end=t; cur.endAz=la.azimuth; cur.maxEl=Math.max(cur.maxEl,el); cur.track.push([la.azimuth,el]); }
    else if(cur){ out.push(cur); cur=null; if(out.length>=max) break; } }
  if(cur&&out.length<max) out.push(cur); return out; }
  return {sunEcf,observer,sunAlt,passes};
})();
