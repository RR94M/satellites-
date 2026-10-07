/* Finding the visitor's location, shared by the globe and the Tonight page.
   - Asks the device first, retrying once (with GPS) if the quick attempt is slow or fails.
   - Explains what actually went wrong (switched off, not allowed, too slow, in-app browser) instead of "blocked".
   - Offers a place search as a fallback: typed names go to Open-Meteo's free geocoder; typed coordinates stay on the device.
   - The chosen spot is saved on this device only (localStorage 'ovh:loc'), so both pages share it. */
const WHERE=(function(){
  const ua=navigator.userAgent||'';
  const ios=/iPhone|iPad|iPod/.test(ua)||(/Macintosh/.test(ua)&&navigator.maxTouchPoints>1), android=/Android/.test(ua);
  const inApp=/FBAN|FBAV|FB_IAB|Instagram|Snapchat|musical_ly|TikTok|BytedanceWebview|LinkedInApp|Twitter|Line\/|Pinterest/i.test(ua);
  const esc=t=>String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  function saved(){ try{ const l=JSON.parse(localStorage.getItem('ovh:loc')||'null'); return l&&isFinite(l.lat)&&isFinite(l.lon)?l:null; }catch(e){ return null; } }
  function save(l){ try{ localStorage.setItem('ovh:loc',JSON.stringify(l)); }catch(e){} return l; }
  function forget(){ try{ localStorage.removeItem('ovh:loc'); }catch(e){} }

  const once=o=>new Promise((res,rej)=>navigator.geolocation.getCurrentPosition(res,rej,o));
  async function locate(){
    if(!navigator.geolocation||window.isSecureContext===false) throw {code:0};
    let p;
    try{ p=await once({enableHighAccuracy:false,maximumAge:30*60e3,timeout:15000}); } // quick: Wi-Fi/mobile network, or a recent fix
    catch(e){ if(e&&e.code===1) throw e; p=await once({enableHighAccuracy:true,maximumAge:0,timeout:30000}); } // slower: GPS
    return save({lat:+p.coords.latitude.toFixed(2),lon:+p.coords.longitude.toFixed(2),alt:Math.round(p.coords.altitude||0)});
  }

  // what went wrong, in plain words, with the fix for this kind of phone or browser
  function help(err){ const code=err&&err.code;
    if(inApp) return 'This app’s built-in browser can’t share your location. Open the page in '+(ios?'Safari':'Chrome')+' (use the ⋯ menu, then “Open in browser”), or type your town below.';
    if(code===1) return 'Your location isn’t allowed for this site. '+(ios?'On iPhone: Settings › Privacy & Security › Location Services must be on, and “Safari Websites” set to “While Using the App”. Then reload this page and tap “Allow”.'
      :android?'Tap the icon to the left of the web address › Permissions › Location › Allow, then try again. Also check Location is on in your phone’s quick settings.'
      :'Click the icon at the left of the address bar and allow Location for this site, then try again.')+' Or type your town below.';
    if(code===2) return 'Your device couldn’t work out where you are'+(ios||android?' (is Location switched on in your phone’s settings?)':' (computers without Wi-Fi often can’t)')+'. Type your town below instead.';
    if(code===3) return 'Finding you took too long. Try again outdoors or with Wi-Fi on, or type your town below.';
    return 'This browser can’t share your location. Type your town below instead.'; }

  // "51.5, -0.12" style coordinates are used as typed; anything else is looked up
  async function search(q){ q=q.trim(); const m=q.match(/^(-?\d{1,2}(?:\.\d+)?)\s*[,\s]\s*(-?\d{1,3}(?:\.\d+)?)$/);
    if(m&&Math.abs(+m[1])<=90&&Math.abs(+m[2])<=180) return [{name:(+m[1]).toFixed(2)+', '+(+m[2]).toFixed(2),lat:+m[1],lon:+m[2]}];
    const r=await fetch('https://geocoding-api.open-meteo.com/v1/search?count=6&language=en&format=json&name='+encodeURIComponent(q));
    if(!r.ok) throw new Error('search '+r.status); const d=await r.json();
    return (d.results||[]).map(x=>({name:[x.name,x.admin1,x.country].filter((v,i,a)=>v&&a.indexOf(v)===i).join(', '),lat:x.latitude,lon:x.longitude})); }

  // a small "type your town" form; calls onPick({lat,lon,name}) once the visitor picks a result
  function picker(box,onPick){
    box.innerHTML='<form class="placeform" role="search"><input type="search" placeholder="Town, city or postcode" aria-label="Type your town, city or postcode" autocomplete="off"><button type="submit">Find</button></form><div class="places" aria-live="polite"></div>';
    const f=box.querySelector('form'), inp=f.querySelector('input'), out=box.querySelector('.places');
    f.onsubmit=async ev=>{ ev.preventDefault(); if(!inp.value.trim()) return; out.textContent='Searching…';
      try{ const list=await search(inp.value);
        if(!list.length){ out.textContent='Nothing found. Try a nearby city, or type coordinates like 51.5, -0.12.'; return; }
        out.innerHTML=list.map((p,i)=>'<button type="button" data-i="'+i+'">'+esc(p.name)+'</button>').join('');
        out.querySelectorAll('button').forEach(b=>b.onclick=()=>{ const p=list[+b.dataset.i]; onPick(save({lat:+(+p.lat).toFixed(2),lon:+(+p.lon).toFixed(2),name:p.name})); });
      }catch(e){ out.textContent='Place search isn’t reachable right now. You can type coordinates instead, like 51.5, -0.12.'; } };
    return inp; }

  const label=l=>l.name?l.name:Math.abs(l.lat).toFixed(1)+'°'+(l.lat>=0?'N':'S')+', '+Math.abs(l.lon).toFixed(1)+'°'+(l.lon>=0?'E':'W');
  return {saved,save,forget,locate,help,search,picker,label,inApp};
})();
