'use strict';
async function renderHumanAvatarSettings(parent){
 const box=card(parent,'Avatar appearance'),status=node('p'),choose=node('input'),mode=node('select');
 mode.id='human-avatar-mode';mode.append(new Option('Original AI Core','core'),new Option('Human Avatar','human'));
 choose.type='file';choose.accept='image/png,.nexus-avatar,.zip';choose.id='human-avatar-file';
 mode.disabled=true;choose.disabled=true;
 const modeLabel=node('label','Avatar ');modeLabel.append(mode);
 const photoLabel=node('label','Choose local PNG photo or avatar pack ');photoLabel.append(choose);
 const preview=node('img');preview.id='human-avatar-photo';preview.alt='Selected local avatar';preview.hidden=true;
 box.append(node('p','Your portrait stays on this laptop. A matching local expression pack adds natural eyelids and speaking mouth shapes.'),modeLabel,photoLabel,preview,status);
 const detail=node('details'),summary=node('summary','Adjust expression alignment');detail.append(summary);const fields={};
 for(const [key,label,min,max] of [['x','Face horizontal offset',-.15,.15],['y','Face vertical offset',-.15,.15],['scale','Face scale',.7,1.3]]){const input=field(detail,label,'number');input.min=min;input.max=max;input.step='.01';input.id='human-align-'+key;fields[key]=input;}
 box.append(detail);
 function describe(p){mode.disabled=false;choose.disabled=false;mode.value=p.enabled?'human':'core';preview.hidden=!p.present;if(p.present)preview.src=p.photo;else preview.removeAttribute('src');detail.hidden=!p.frames;
  for(const [key,input] of Object.entries(fields))input.value=p.alignment?.[key]??(key==='scale'?1:0);
  status.textContent=!p.present?'AI Core is active. Choose a portrait to enable Human Avatar.':p.frames?(p.enabled?'Human Avatar is active.':'AI Core is active; your Human Avatar is saved.')+' Voice synchronization starts with the next spoken reply.':'Photo loaded. Add a matching expression pack for blinking and speaking lips.';
 }
 try{describe(await api('human-avatar',undefined,'GET'));}catch(e){status.textContent=e.message;return;}
 choose.onchange=async()=>{
  const file=choose.files[0];if(!file)return;
  if(file.size>4000000){status.textContent='Choose an avatar file smaller than 4 MB.';choose.value='';return;}
  choose.disabled=true;status.textContent='Loading avatar locally…';
  try{const r=await fetch('/api/human-avatar/import',{method:'POST',headers:{'X-Nexus-Token':state.token,'Content-Type':file.type==='image/png'?'image/png':'application/zip'},body:file}),p=await r.json();if(!r.ok)throw Error(p.detail||'Could not import portrait.');describe(p);await refresh();}
  catch(e){status.textContent=e.message;}finally{choose.disabled=false;choose.value='';}
 };
 box.append(button('Apply avatar',async()=>{const alignment=Object.fromEntries(Object.entries(fields).map(([key,input])=>[key,Number(input.value)]));describe(await api('human-avatar/settings',{enabled:mode.value==='human',alignment}));await refresh();}),button('Remove local avatar',async()=>{describe(await api('human-avatar/photo',undefined,'DELETE'));await refresh();}));
}
