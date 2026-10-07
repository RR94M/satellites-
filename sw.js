/* Offline support. Pages and data: network first, falling back to the last copy, so you always get the newest
   version when online and something useful when not. Libraries, fonts and icons: served from the copy, refreshed in
   the background. Bump VERSION to clear old copies. */
const VERSION='overhead-v1';
const SHELL=['./','index.html','tonight.html','launches.html','alerts.html','spaceweather.html','manifest.webmanifest',
  'lib/app.css','lib/app.js','lib/tz-lookup.js','lib/localtime.js','lib/aurora.js','lib/where.js','lib/calendar.js','lib/sky.js','lib/spacewx.js',
  'icons/icon-192.png','fonts/space-grotesk-latin-400-normal.woff2','fonts/space-grotesk-latin-500-normal.woff2','fonts/space-grotesk-latin-600-normal.woff2'];
self.addEventListener('install',e=>{ e.waitUntil(caches.open(VERSION).then(c=>c.addAll(SHELL).catch(()=>{})).then(()=>self.skipWaiting())); });
self.addEventListener('activate',e=>{ e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim())); });
const networkFirst=async req=>{ const c=await caches.open(VERSION); try{ const r=await fetch(req); if(r&&r.ok) c.put(req,r.clone()); return r; }catch(e){ const hit=await c.match(req,{ignoreSearch:req.mode==='navigate'}); if(hit) return hit; throw e; } };
const staleWhileRevalidate=async req=>{ const c=await caches.open(VERSION), hit=await c.match(req); const net=fetch(req).then(r=>{ if(r&&(r.ok||r.type==='opaque')) c.put(req,r.clone()); return r; }).catch(()=>hit); return hit||net; };
self.addEventListener('fetch',e=>{ const req=e.request; if(req.method!=='GET') return; const u=new URL(req.url);
  if(req.mode==='navigate'||u.pathname.endsWith('.html')) return e.respondWith(networkFirst(req));
  if(u.hostname==='raw.githubusercontent.com'||u.hostname.endsWith('noaa.gov')) return e.respondWith(networkFirst(req)); // data
  if(u.origin===location.origin||/cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net/.test(u.hostname)) return e.respondWith(staleWhileRevalidate(req)); // code, fonts, icons, map data
});
