function opaqueWhatsAppFixture(){
 const history=document.querySelector('#history');history.replaceChildren();
 const make=(id,text,outgoing)=>{
  const row=document.createElement('div');row.dataset.id=id;row.dataset.testid='conversation-row';row.setAttribute('role','row');
  const virtual=document.createElement('div');virtual.dataset.virtualized='true';const a=document.createElement('div'),b=document.createElement('div'),bubble=document.createElement('div');bubble.dataset.testid='msg-container';
  const body=document.createElement('span');body.className='selectable-text';body.style.whiteSpace='pre-wrap';body.textContent=text;bubble.append(body);
  if(outgoing){const icon=document.createElement('i');icon.dataset.icon=window.testIcon||'msg-check';bubble.append(icon);}
  b.append(bubble);a.append(b);virtual.append(a);row.append(virtual);return row;
 };
 for(let i=0;i<22;i++)history.append(make('A1B2C3D4E5F6A7B8C9D0'+i.toString(16).padStart(8,'0'),'Fixture history '+i,i%2===0));
 const title=document.querySelector('[data-testid="conversation-info-header-chat-title"]');
 window.fixturePhone='+1 202 555 0101';window.fixturePanelName='Nexus Test Contact';
 title.onclick=()=>{
  const old=document.querySelector('[data-testid="drawer-right"]');if(old){old.remove();return;}
  const panel=document.createElement('aside');panel.dataset.testid='drawer-right';
  const header=document.createElement('header'),label=document.createElement('span');label.textContent='Contact info';header.append(label);
  const close=document.createElement('button');close.textContent='Close contact info';close.setAttribute('aria-label','Close');close.onclick=()=>panel.remove();header.append(close);
  const name=document.createElement('h2');name.textContent=window.fixturePanelName;
  const phone=document.createElement('span');phone.dir='ltr';phone.dataset.testid='fixture-phone';phone.textContent=window.fixturePhone;
  panel.append(header,name,phone);document.body.append(panel);
 };
 document.querySelector('#main footer button').onclick=()=>{
  clicks++;history.append(make('B2C3D4E5F6A7B8C9D0E1F2'+clicks.toString(16).padStart(8,'0'),document.querySelector('#composer').innerText,true));
  document.querySelector('#composer').textContent='';history.scrollTop=history.scrollHeight;
 };
 return true;
}
