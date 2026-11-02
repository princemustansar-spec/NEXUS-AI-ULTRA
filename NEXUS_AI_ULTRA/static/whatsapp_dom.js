/* Evaluated only by the native WhatsApp controller, never registered as a remote JS API. */
function nexusWhatsApp(payload){
 'use strict';
 if(location.origin!=='https://web.whatsapp.com')return {status:'wrong_origin',reason:'WhatsApp controls require web.whatsapp.com'};
 const norm=s=>String(s||'').replace(/\r\n/g,'\n').replace(/\u00a0/g,' ').trim();
 const key=s=>norm(s).normalize('NFKC').replace(/[\u200e\u200f\u202a-\u202e]/g,'').replace(/\s+/g,' ').toLocaleLowerCase();
 const visible=e=>!!e&&!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length);
 const side=document.querySelector('#side');
 if(!side){const qr=document.querySelector('[data-ref],canvas[aria-label*="QR"], [data-testid="qrcode"], [data-testid="link-device-phone-number-code-screen"]');return {status:qr?'login_required':'loading',reason:qr?'Scan the QR code in the NEXUS WhatsApp window.':'WhatsApp is loading; check the window and retry.'};}
 let session=window.__nexusWhatsAppSession;
 if(!session||session.side!==side){session={side,id:crypto.randomUUID()};Object.defineProperty(window,'__nexusWhatsAppSession',{value:session,writable:true,configurable:true});}
 const main=document.querySelector('#main');
 const composer=()=>{const els=[...document.querySelectorAll('#main footer [contenteditable="true"][role="textbox"], #main footer [data-testid="conversation-compose-box-input"]')].filter(visible);return els.length===1?els[0]:null;};
 const textOf=e=>norm(e?.innerText||e?.textContent||'');
 const identity=()=>{
  const title=main?.querySelector('header span[title][dir="auto"], header [data-testid="conversation-info-header-chat-title"], header span[title]');
  const titleText=norm(title?.getAttribute('title')||textOf(title));
  const ids=new Set();for(const e of main?.querySelectorAll('.message-in,.message-out')||[]){const raw=e.getAttribute('data-id')||e.closest('[data-id]')?.getAttribute('data-id')||'';const m=raw.match(/(?:^|_)(\d+(?:-\d+)?@(?:c\.us|s\.whatsapp\.net|g\.us|lid))/);if(m)ids.add(m[1]);}
  if(!ids.size&&/^\+?[\d ()-]+$/.test(titleText)){const digits=titleText.replace(/\D/g,'');if(/^[1-9]\d{6,14}$/.test(digits))ids.add(digits+'@c.us');}
  return {recipient:titleText,recipient_id:ids.size===1?[...ids][0]:'',session:session.id};
 };
 const outgoing=()=>[...(main?.querySelectorAll('.message-out')||[])].slice(-50).map(e=>{
  const id=e.getAttribute('data-id')||e.closest('[data-id]')?.getAttribute('data-id')||e.querySelector('[data-id]')?.getAttribute('data-id')||'';
  const content=e.querySelector('[data-testid="msg-text"],.selectable-text');
  const icon=e.querySelector('[data-icon="msg-error"],[data-icon="msg-time"],[data-icon="msg-dblcheck-ack"],[data-icon="msg-dblcheck"],[data-icon="msg-check"]');
  return {id,text:textOf(content),icon:icon?.getAttribute('data-icon')||''};
 });
 const scrollers=()=>[...(main?.querySelectorAll('div')||[])].filter(e=>!e.closest('footer,header')&&e.clientHeight>100&&e.scrollHeight>e.clientHeight+8);
 const atBottom=()=>scrollers().every(e=>e.scrollHeight-e.scrollTop-e.clientHeight<8);
 const state=()=>({status:'ready',at_bottom:atBottom(),...identity(),composer:composer()?textOf(composer()):null,outgoing:outgoing()});
 const put=(e,text)=>{
  if(!e||!visible(e))return false;e.focus();
  if(e.isContentEditable){const range=document.createRange();range.selectNodeContents(e);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);if(!document.execCommand('insertText',false,text))return false;}
  else{const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')?.set;if(!set)return false;set.call(e,text);e.dispatchEvent(new Event('input',{bubbles:true}));}
  return norm(e.isContentEditable?e.innerText:e.value)===norm(text);
 };
 const searchBox=()=>{const els=[...side.querySelectorAll('[contenteditable="true"][role="textbox"],input[type="text"],[data-testid="chat-list-search"]')].filter(visible);return els.length===1?els[0]:null;};
 const rows=()=>{
  let els=[...side.querySelectorAll('#pane-side [role="row"],#pane-side [role="listitem"],[aria-label="Chat list"] [role="row"]')].filter(visible);
  if(!els.length)els=[...side.querySelectorAll('#pane-side [data-testid="cell-frame-container"]')].filter(visible);
  els=els.filter(e=>!els.some(other=>other!==e&&e.contains(other)));
  return els.flatMap(e=>{const title=e.querySelector('[data-testid="cell-frame-title"] span[title],span[title][dir="auto"],span[title]');const name=norm(title?.getAttribute('title')||textOf(title));return name?[{element:e,name}]:[];});
 };
 const op=payload.op,args=payload.args||{};
 if(op==='state')return state();
 if(op==='scroll_bottom'){for(const e of scrollers())e.scrollTop=e.scrollHeight;return state();}
 if(op==='search')return {status:put(searchBox(),args.query)?'searching':'blocked',reason:'A unique contact search field is required.'};
 if(op==='results'){
  const box=searchBox();return {status:'ready',session:session.id,query:norm(box?.isContentEditable?box.innerText:box?.value),matches:rows().filter(r=>key(r.name).includes(key(args.query))).map(r=>({name:r.name})).slice(0,20)};
 }
 if(op==='select'){
  const matches=rows().filter(r=>key(r.name)===key(args.contact));
  if(matches.length!==1)return {status:matches.length?'ambiguous':'not_found',matches:matches.map(r=>({name:r.name}))};
  matches[0].element.click();return {status:'selected',recipient:matches[0].name};
 }
 const extraContext=()=>!!main?.querySelector('footer [data-testid*="quoted"],footer [data-testid*="reply-preview"],footer [data-testid*="edit-message"],[data-testid="media-editor"],[data-testid="media-preview"]');
 const pinned=()=>{const s=identity();return s.session===args.session&&s.recipient===args.recipient&&!!s.recipient_id&&s.recipient_id===args.recipient_id;};
 if(op==='compose'){
  if(extraContext())return {status:'blocked',reason:'Remove any reply, edit or media attachment preview before preparing a new text message.'};
  if(!pinned())return {status:'blocked',reason:'Recipient identity changed.'};
  const e=composer();if(!e)return {status:'blocked',reason:'Unique message composer not found.'};
  const old=textOf(e);if(old&&old!==norm(args.message))return {status:'blocked',reason:'Existing unsent draft protected. Clear or send it yourself first.'};
  if(old!==norm(args.message)&&!put(e,args.message))return {status:'blocked',reason:'Message could not be inserted exactly.'};
  return {...state(),status:textOf(e)===norm(args.message)?'composed':'blocked'};
 }
 if(op==='send'){
  if(extraContext())return {clicked:false,reason:'Reply/edit/media context changed after confirmation.'};
  // All checks and the single click run synchronously in the same DOM turn.
  if(!pinned())return {clicked:false,reason:'Recipient/session changed after confirmation.'};
  const e=composer();if(!e||textOf(e)!==norm(args.message))return {clicked:false,reason:'Draft changed after confirmation.'};
  const messages=outgoing();const before=messages.map(m=>m.id);
  if(!atBottom()||before.some(id=>!id)||JSON.stringify(before)!==JSON.stringify(args.approval_before))return {clicked:false,reason:'Chat history changed or is not at the latest message. Prepare again.'};
  const candidates=[...document.querySelectorAll('#main footer [data-testid="send"],#main footer [data-icon="send"],#main footer button[aria-label="Send"],#main footer [role="button"][aria-label="Send"]')].map(e=>e.closest('button,[role="button"]')||e);
  const buttons=[...new Set(candidates)].filter(e=>visible(e)&&!e.disabled&&e.getAttribute('aria-disabled')!=='true');
  if(buttons.length!==1)return {clicked:false,reason:'Unique enabled Send button not found.'};
  buttons[0].click();return {clicked:true,before};
 }
 return {status:'blocked',reason:'Unknown WhatsApp operation'};
}
