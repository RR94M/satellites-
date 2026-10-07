/* Plain-English wording for NOAA space weather alerts, shared by the Alerts and Space weather pages. */
const SPACEWX=(function(){
  const PLAIN=[[/Geomagnetic Storm Category G(\d) Predicted/i,m=>'A '+['','minor','moderate','strong','severe','extreme'][+m[1]]+' geomagnetic storm (G'+m[1]+') is expected: aurora further from the poles than usual'],
  [/Geomagnetic K-index of (\d)( expected)?/i,m=>(m[2]?'Expected: ':'')+'Earth’s magnetic field '+(+m[1]>=5?'is stormy':'is unsettled')+' (Kp '+m[1]+')'+(+m[1]>=5?', so aurora can reach lower latitudes':'')],
  [/Geomagnetic Sudden Impulse/i,()=>'A burst of solar wind has just hit Earth’s magnetic field'],
  [/X-ray Flux exceeded M(\d)|X-ray Event exceeded X/i,()=>'A strong solar flare: short radio blackouts are possible on the sunlit side of Earth'],
  [/Proton Event/i,()=>'A solar radiation storm: higher radiation for astronauts and on polar flights'],
  [/Electron 2MeV Integral Flux/i,()=>'High-energy electrons are building up around Earth: they can upset satellites (no effect on the ground)'],
  [/Type II Radio Emission/i,()=>'A radio burst from the Sun, usually the sign of a big eruption heading out into space'],
  [/Type IV Radio Emission/i,()=>'A long radio burst from the Sun, often linked to a major eruption'],
  [/10cm Radio Burst/i,()=>'A burst of radio noise from the Sun, usually with a solar flare']];
  function plain(h){ for(const [re,f] of PLAIN){ const m=h.match(re); if(m) return f(m); } return h; }
  return {plain};
})();
