'use strict';
// Uses the existing authenticated API helper and native secure account adapters.
async function renderAccountConnections(parent){
 const box=card(parent,'ChatGPT and Claude accounts');box.id='account-connections';
 box.append(node('p','Connect your own account, test a real response, then choose Use for chat and voice. Requests consume plan limits or credits; extra usage may cost money. Voice uses your existing NEXUS speech settings.'));
 let snapshot;try{snapshot=await api('accounts/status',undefined,'GET');}catch(e){box.append(node('p',e.message));return;}
 for(const [id,title] of [['chatgpt','ChatGPT'],['claude','Claude Code (official app)']]){
  const c=card(box,title),status=node('p'),output=node('p');c.dataset.account=id;
  function label(s){status.textContent=(s.connected?'Signed in':'Not connected')+(s.account?' · '+s.account:'')+(s.pending?' · Sign-in pending':'')+(s.error?' · '+s.error:'');}
  label(snapshot[id]||{});c.append(status);
  if(id==='claude')c.append(node('p','Install official Claude Code first: winget install Anthropic.ClaudeCode. Complete its own login; NEXUS does not read or copy Claude tokens.'));
  const controls=node('div',undefined,'row');c.append(controls,output);
  const act=(text,action,body={})=>{const b=button(text,async()=>{b.disabled=true;try{const r=await api('accounts/'+id+'/'+action,body);output.textContent=r.text||r.message||r.note||(r.verified?'Connection tested':r.enabled===true?'Selected for chat and voice':r.enabled===false?'Connection disabled':'Done');if(action==='check')label(r);if(action==='login')output.textContent=r.message||'Complete sign-in in the browser, then click Check connection.';await refresh();}finally{b.disabled=false;}});controls.append(b);return b;};
  const loginButton=act(id==='chatgpt'?'Continue with ChatGPT':'Open official Claude login','login',{consent:true});if(id==='chatgpt')loginButton.setAttribute('data-oai-siwc-button','');
  act('Check connection','check');
  if(id==='chatgpt'){
   const select=node('select');select.setAttribute('aria-label','ChatGPT account model');
   controls.append(button('Load account models',async()=>{const r=await api('accounts/chatgpt/models',{});select.replaceChildren(new Option('Choose a model',''));for(const m of r.models)select.append(new Option(m.name,m.slug));}),select,button('Save account model',async()=>{if(!select.value)throw Error('Choose an account model first.');await api('accounts/chatgpt/model',{model:select.value});output.textContent='Model saved. Test the connection next.';}));
  }
  act('Test response (uses plan credits)','test',{consent:true});
  act('Use for chat and voice','enable',{consent:true});act('Disable in NEXUS','disable');
  if(id==='chatgpt')act('Disconnect ChatGPT','disconnect');
 }
}
