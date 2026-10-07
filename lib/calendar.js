/* "Add to calendar" menu, shared by the Tonight and Launches pages.
   No single method works everywhere: iPhone Safari blocks data: links, in-app browsers (Instagram, Facebook) can't
   download files, and Android has no built-in .ics handler. So the menu offers Google and Outlook (their own add-event
   pages) plus "Apple Calendar or other", which downloads a proper .ics file with a reminder.
   CALENDAR.menu(ev) returns the HTML; ev = {title, start, end, detail, allDay, alarmMinutes, url}.
   Call CALENDAR.reset() before re-rendering a page so old events are released. */
const CALENDAR=(function(){
  const events=[];
  const stamp=t=>new Date(t).toISOString().replace(/[-:]/g,'').replace(/\.\d+/,'');
  const day=t=>new Date(t).toISOString().slice(0,10).replace(/-/g,''); // all-day events use the UTC date
  const iso=t=>new Date(t).toISOString().replace(/\.\d+/,'');
  function ics(ev){ const txt=t=>String(t).replace(/\\/g,'\\\\').replace(/[,;]/g,'\\$&').replace(/\r?\n/g,'\\n');
    const fold=l=>{ let out='', n=0; for(const ch of l){ const w=new TextEncoder().encode(ch).length; if(n+w>73){ out+='\r\n '; n=1; } out+=ch; n+=w; } return out; }; // lines must stay under 75 bytes
    const when=ev.allDay?['DTSTART;VALUE=DATE:'+day(ev.start),'DTEND;VALUE=DATE:'+day(ev.start+864e5)]:['DTSTART:'+stamp(ev.start),'DTEND:'+stamp(ev.end)];
    const alarm=ev.alarmMinutes==null?[]:['BEGIN:VALARM','TRIGGER:-PT'+ev.alarmMinutes+'M','ACTION:DISPLAY','DESCRIPTION:'+txt(ev.title)+(ev.allDay?'':' in '+ev.alarmMinutes+' minutes'),'END:VALARM'];
    return ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Overhead//Calendar//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH','BEGIN:VEVENT','UID:'+ev.start+'-'+ev.title.replace(/\W/g,'').slice(0,40)+'@overhead',
      'DTSTAMP:'+stamp(Date.now()),...when,'SUMMARY:'+txt(ev.title),'DESCRIPTION:'+txt(ev.detail+(ev.url?'\n'+ev.url:'')),...(ev.url?['URL:'+ev.url]:[]),
      ...alarm,'END:VEVENT','END:VCALENDAR'].map(fold).join('\r\n')+'\r\n'; }
  function menu(ev){ const k=events.push(ev)-1, q=encodeURIComponent, body=ev.detail+(ev.url?'\n\n'+ev.url:'');
    const google='https://calendar.google.com/calendar/render?action=TEMPLATE&text='+q(ev.title)+'&dates='+(ev.allDay?day(ev.start)+'/'+day(ev.start+864e5):stamp(ev.start)+'/'+stamp(ev.end))+'&details='+q(body);
    const outlook='https://outlook.live.com/calendar/0/deeplink/compose?path=%2Fcalendar%2Faction%2Fcompose&rru=addevent&subject='+q(ev.title)
      +(ev.allDay?'&allday=true&startdt='+new Date(ev.start).toISOString().slice(0,10)+'&enddt='+new Date(ev.start+864e5).toISOString().slice(0,10):'&startdt='+iso(ev.start)+'&enddt='+iso(ev.end))+'&body='+q(body);
    return '<details class="cal"><summary>Add to calendar</summary><div class="calmenu"><button type="button" data-ics="'+k+'">Apple Calendar or other (.ics file)</button>'
      +'<a href="'+google+'" target="_blank" rel="noopener">Google Calendar</a><a href="'+outlook+'" target="_blank" rel="noopener">Outlook</a></div></details>'; }
  document.addEventListener('click',e=>{ const b=e.target.closest('[data-ics]'); if(!b) return; const ev=events[+b.dataset.ics]; if(!ev) return;
    const name=ev.title.toLowerCase().replace(/\W+/g,'-').replace(/^-|-$/g,'').slice(0,60)+'.ics', url=URL.createObjectURL(new Blob([ics(ev)],{type:'text/calendar;charset=utf-8'}));
    const a=document.createElement('a'); a.href=url; a.download=name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(url),120e3);
    b.textContent='Downloaded: open '+name+' to add it'; });
  const isOpen=()=>!!document.querySelector('details.cal[open]');
  return {menu,ics,reset:()=>{ events.length=0; },isOpen};
})();
