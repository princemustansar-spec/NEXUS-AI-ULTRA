'use strict';
async function renderPersonalSettings(parent){
 const panel=node('section');panel.id='personal-panel';parent.append(panel);parent=panel;
 const box=card(parent,'Personal Assistant'),status=node('p');status.id='personal-status';box.append(status);
 try{
  const data=await api('personal',undefined,'GET'),p=data.profile;
  const name=field(box,'What should NEXUS call you?','text',p.preferred_name);name.id='personal-name';
  const tone=node('select');tone.id='personal-tone';for(const [label,value] of [['Friendly & playful','friendly'],['Calm & supportive','calm'],['Short & warm','concise']])tone.append(new Option(label,value));tone.value=p.tone;box.append(node('label','Reply style'),tone);
  const look=node('select');look.id='personal-avatar-style';look.append(new Option('NEXUS human face','human'),new Option('Classic robot','robot'));look.value=p.avatar_style||'human';box.append(node('label','Floating face'),look);
  const checks={};for(const [key,label] of [['welcome_enabled','Welcome when NEXUS starts'],['speak_welcome','Speak the welcome (respects mute)'],['routine_in_welcome','Include today routine and reminders'],['news_on_start','Fetch Pakistan/world headlines at startup (online)'],['emotions','Expressive avatar']]){
   const input=node('input');input.type='checkbox';input.checked=p[key];input.id='personal-'+key;const lab=node('label',' '+label);lab.prepend(input);box.append(lab);checks[key]=input;
  }
  box.append(button('Save personal settings',async()=>{await api('personal/settings',{preferred_name:name.value,tone:tone.value,avatar_style:look.value,...Object.fromEntries(Object.entries(checks).map(([k,v])=>[k,v.checked]))});await refresh();status.textContent='Personal settings saved.';}));
  const login=node('input');login.type='checkbox';login.checked=data.startup.enabled;login.disabled=!data.startup.available;login.id='personal-login';const label=node('label',' Start NEXUS when I sign in to Windows');label.prepend(login);box.append(label);
  const saveStartup=button('Apply Windows startup',async()=>{const r=await api('personal/startup-mode',{enabled:login.checked});status.textContent=r.enabled?'Windows sign-in startup enabled.':'Windows sign-in startup disabled.';});saveStartup.disabled=!data.startup.available;box.append(saveStartup);
  box.append(button('Show daily briefing',async()=>{const r=await api('personal/briefing',{news:false,speak:false});status.textContent=r.text;}),button('Speak daily briefing',async()=>{status.textContent='Preparing briefing…';const r=await api('personal/briefing',{news:checks.news_on_start.checked,speak:true});status.textContent=r.text+(r.spoken?'':' · '+r.reason);}));
  const news=card(parent,'Pakistan & international headlines'),newsOutput=node('div');newsOutput.id='personal-news';news.append(node('p','Dated headlines from Dawn and BBC, with sources and links.'),button('Fetch current headlines',async()=>{
   newsOutput.textContent='Fetching headlines…';try{const r=await api('personal/briefing',{news:true,speak:false});newsOutput.replaceChildren();for(const item of r.news.items){const row=node('p'),link=node('a',item.title);link.href=item.url;link.target='_blank';link.rel='noopener noreferrer';row.append(node('small',item.source+' · '+new Date(item.published).toLocaleString()+' '),link);newsOutput.append(row);}for(const warning of r.news.warnings)newsOutput.append(node('p',warning));}catch(e){newsOutput.textContent=e.message;}
  }),newsOutput);
  const routines=card(parent,'Daily routine');routines.append(node('p','Uses this computer’s local time. Due items notify once per day while NEXUS runs, including overdue items after restart.'));
  const title=field(routines,'Routine title'),when=field(routines,'Time','time');title.id='routine-title';when.id='routine-time';const weekdays=[];
  for(const [day,label] of ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].entries()){const input=node('input');input.type='checkbox';input.checked=true;input.dataset.day=day;const lab=node('label',' '+label);lab.prepend(input);routines.append(lab);weekdays.push(input);}
  routines.append(button('Save routine',async()=>{await api('personal/routines',{title:title.value,time:when.value,days:weekdays.map((v,i)=>v.checked?i:-1).filter(i=>i>=0),enabled:true});await refresh();renderPage();}));
  for(const r of data.routines){const row=node('p',r.time+' · '+r.title+' · '+r.days.map(d=>['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][d]).join(', '));row.append(button('Delete routine',async()=>{await api('personal/routines/'+r.id,undefined,'DELETE');renderPage();}));routines.append(row);}
  const local=card(parent,'Ollama on this laptop'),localStatus=node('p'),models=node('select'),mode=node('select');models.id='personal-ollama-model';mode.id='personal-ollama-mode';
  for(const [label,value] of [['Use local model only','local'],['Fallback if primary provider fails','fallback'],['Disabled','disabled']])mode.append(new Option(label,value));
  mode.value=state.preferred_provider==='ollama'?'local':data.ollama_fallback?'fallback':'disabled';
  let selected=state.providers.find(p=>p.id==='ollama')?.model||'';
  local.append(node('p','Uses installed models only, a longer cold start and a 4096-token context. Some small models support chat only; app commands and approvals remain available.'),models,mode);
  local.append(button('Find installed models',async()=>{const r=await api('personal/ollama',undefined,'GET');models.replaceChildren(...r.models.map(m=>new Option(m.name,m.name)));if([...models.options].some(o=>o.value===selected))models.value=selected;localStatus.textContent=r.available?'Local server found. Choose a model and mode.':r.error;}));
  local.append(button('Save Ollama mode',async()=>{await api('personal/ollama',{action:'configure',model:models.value,mode:mode.value});selected=models.value;await refresh();localStatus.textContent='Ollama mode saved. Test local reply to verify inference.';}),button('Test local reply',async()=>{localStatus.textContent='Testing local inference; a cold start can take up to two minutes…';try{const r=await api('personal/ollama',{action:'test'});localStatus.textContent=r.model+' · '+r.text+' · '+(r.tools_supported?'Model tool calls supported':'Local chat only; use app commands for actions');}catch(e){localStatus.textContent=e.message;}}),localStatus);
 }catch(e){status.textContent=e.message;}
}
