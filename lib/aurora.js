/* Where the aurora can be seen, shared by the globe and the Tonight page.
   Geomagnetic latitude (dipole pole 80.8N 72.7W) and the Kp at which aurora usually reaches your horizon
   (the visibility line moves about 2 degrees of geomagnetic latitude towards the equator per Kp step).
   Earth's field is lopsided, and the southern aurora zone sits closer to Australia and New Zealand than a centred
   dipole suggests. So in the south we also measure from a point fitted to published guidance (Hobart ~Kp 4-5 from a
   dark site, Melbourne 6-8, Christchurch 6, Invercargill 4-5) and use whichever gives the better chance. */
const AURORA=(function(){
  const D2R=Math.PI/180;
  function magLat(lat,lon){ const a=lat*D2R, b=lon*D2R, from=(pl,pn)=>Math.asin(Math.sin(a)*Math.sin(pl*D2R)+Math.cos(a)*Math.cos(pl*D2R)*Math.cos(b-pn*D2R))/D2R;
    const dip=Math.abs(from(80.8,-72.7)); return lat<0?Math.max(dip,Math.abs(from(-74.25,126))):dip; }
  // Kp needed for aurora on your horizon (0-9)
  const kpNeeded=(lat,lon)=>Math.max(0,Math.min(9,(66.5-magLat(lat,lon))/2.05));
  // the furthest-from-the-pole line it can be seen from at this Kp, as [lat, lon] points, one per hemisphere
  function viewLine(kp){ const limit=66.5-2.05*kp, out={north:[],south:[]};
    for(let lon=-180;lon<=180;lon+=2){
      for(const [key,sign] of [['north',1],['south',-1]]){ let lat=null;
        for(let l=89.5;l>=20;l-=0.25) if(magLat(sign*l,lon)<limit){ lat=sign*(l+0.25); break; }
        if(lat!==null) out[key].push([lat,lon]); } }
    return out; }
  const level=kp=>kp>=8?'severe storm':kp>=7?'strong storm':kp>=6?'storm':kp>=5?'minor storm':kp>=4?'active':kp>=3?'unsettled':'quiet';
  return {magLat,kpNeeded,viewLine,level};
})();
