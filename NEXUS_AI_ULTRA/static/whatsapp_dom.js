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
 if(!session||session.side!==side){
  session?.abort?.abort();session={side,id:crypto.randomUUID(),proof:null,abort:new AbortController()};
  Object.defineProperty(window,'__nexusWhatsAppSession',{value:session,writable:true,configurable:true});
  const activeSession=session;
  const invalidate=()=>{activeSession.proof=null;activeSession.infoRequest=null;};
  for(const event of ['pointerdown','click','input','keydown'])side.addEventListener(event,invalidate,{capture:true,signal:session.abort.signal});
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.altKey||e.metaKey)&&['ArrowUp','ArrowDown','Tab','PageUp','PageDown'].includes(e.key))invalidate();},{capture:true,signal:session.abort.signal});
 }
 const main=document.querySelector('#main');
 // Test IDs can be on wrappers around the actual editable element.
 const inputs=(root,selector)=>[...new Set([...(root?.querySelectorAll(selector)||[])].flatMap(e=>e.matches('input,[contenteditable="true"]')?[e]:[...e.querySelectorAll('input[type="text"],[contenteditable="true"]')]))].filter(visible);
 const composers=()=>inputs(main?.querySelector('footer'),'[contenteditable="true"][role="textbox"],[data-testid="conversation-compose-box-input"]');
 const composer=()=>{const els=composers();return els.length===1?els[0]:null;};
 const textOf=e=>norm(e?.innerText||e?.textContent||'');
 const headerTitle=()=>main?.querySelector('header [data-testid="conversation-info-header-chat-title"]')||main?.querySelector('header span[title][dir="auto"]')||main?.querySelector('header span[title]');
 const excluded='header,footer,[data-testid*="quoted"],[data-testid*="reply-preview"]';
 const quoted='[data-testid*="quoted"],[data-testid*="reply-preview"]';
 const validId=value=>typeof value==='string'&&value.length>0&&value.length<=512&&!/[\s\x00-\x1f]/.test(value);
 const messageId=e=>{
  const candidates=[e,e.closest('[data-id]'),...e.querySelectorAll('[data-id]')].filter(n=>n&&!n.closest(quoted)&&validId(n.getAttribute('data-id')));
  // Only the outer message ID belongs to this bubble; quoted IDs are not identities.
  const outer=candidates.filter(n=>!candidates.some(other=>other!==n&&other.contains(n)));
  const ids=[...new Set(outer.map(n=>n.getAttribute('data-id')))];return ids.length===1?ids[0]:'';
 };
 const messageRows=()=>{
  // Modern IDs are opaque: discover declared message containers, not ID prefixes.
  const declared=[...(main?.querySelectorAll('[data-testid="msg-container"]')||[])].filter(e=>!e.closest(excluded)).map(e=>e.closest('[data-id]')||e);
  const all=[...(main?.querySelectorAll('[data-id]')||[])].filter(e=>/^(?:true|false)_/.test(e.dataset.id||'')&&!e.closest(excluded));
  const outer=all.filter(e=>!all.some(parent=>parent!==e&&parent.contains(e)));
  const legacy=[...(main?.querySelectorAll('.message-in,.message-out')||[])];
  const candidates=[...new Set([...declared,...outer.map(e=>e.closest('.message-in,.message-out')||e),...legacy])].filter(e=>!e.closest(excluded));
  return candidates.filter(e=>!candidates.some(other=>other!==e&&other.contains(e)));
 };
 const infoLabels=new Set(['contact info','contact information','contact details','معلومات جهة الاتصال','رابطے کی معلومات']);
 const phoneOf=text=>{
  const value=norm(text).replace(/[\u200e\u200f\u202a-\u202e]/g,'').replace(/\s+/g,' ').replace(/[٠-٩۰-۹]/g,c=>String(c.charCodeAt(0)%16));
  if(!/^\+[\d ()-]{6,25}$/.test(value))return '';
  const digits=value.replace(/\D/g,'');return /^[1-9]\d{6,14}$/.test(digits)?'+'+digits:'';
 };
 const isInfoPanel=panel=>{
  if(!panel?.isConnected||!visible(panel)||panel===main||panel===side||panel.contains(main)||panel.contains(side)||panel.querySelector('footer [contenteditable="true"]'))return null;
  if(panel.closest('[data-testid="msg-container"],.message-in,.message-out,'+quoted))return null;
  const labels=[...panel.querySelectorAll('header,header span,header div,h1,h2,[role="heading"]')].filter(visible);
  return labels.some(e=>infoLabels.has(key(textOf(e))));
 };
 const panelRoots=()=>{
  const known=[...document.querySelectorAll('[data-testid="drawer-right"],[data-testid="contact-info-drawer"],[data-testid="contact-info"],[role="dialog"]')];
  const headings=[...document.querySelectorAll('header span,header div,h1,h2,[role="heading"]')].filter(e=>visible(e)&&infoLabels.has(key(textOf(e))));
  return [...new Set([...known,...headings.map(e=>(e.closest('header')||e).parentElement)])].filter(isInfoPanel);
 };
 const readPanel=(panel,contact)=>{
  if(!isInfoPanel(panel))return null;
  const elements=[...panel.querySelectorAll('*')].filter(visible);
  if(!elements.some(e=>key(textOf(e))===key(contact)))return null;
  const phones=[...new Set(elements.map(e=>phoneOf(textOf(e))).filter(Boolean))];
  return phones.length===1?{panel,phone:phones[0]}:null;
 };
 const contactInfo=contact=>{
  const found=panelRoots().map(e=>readPanel(e,contact)).filter(Boolean);
  if(!found.length)return null;
  if(new Set(found.map(v=>v.phone)).size!==1)return null;
  return found.sort((a,b)=>a.panel.querySelectorAll('*').length-b.panel.querySelectorAll('*').length)[0];
 };
 const identity=()=>{
  const title=headerTitle();
  const titleText=norm(title?.getAttribute('title')||textOf(title));
  const rows=messageRows();
  const ids=new Set();let identified=0,opaque=0;for(const e of rows){const id=messageId(e);if(id)identified++;const m=id.match(/^(?:true|false)_(\d+(?:-\d+)?@(?:c\.us|s\.whatsapp\.net|g\.us|lid))(?:_|$)/);if(m)ids.add(m[1]);else if(id)opaque++;}
  if(!ids.size&&/^\+?[\d ()-]+$/.test(titleText)){const digits=titleText.replace(/\D/g,'');if(/^[1-9]\d{6,14}$/.test(digits))ids.add(digits+'@c.us');}
  const proof=session.proof;let phone='',context=session.id;
  if(!ids.size&&proof&&proof.main===main&&proof.header===title&&proof.editor===composer()&&proof.contact===titleText){
   const observed=readPanel(proof.panel,titleText);
   if(observed?.phone===proof.phone){phone=proof.phone;context=proof.nonce;}
  }
  return {recipient:titleText,recipient_id:ids.size===1?[...ids][0]:phone?'phone:'+phone:'',recipient_phone:phone,context,session:session.id,
   verification:{header_found:!!titleText,message_rows:rows.length,identified_rows:identified,opaque_rows:opaque,chat_identifiers:ids.size||(phone?1:0),contact_number_verified:!!phone,composer_count:composers().length}};
 };
 const receiptIcon=e=>{
  const known=new Set(['msg-error','msg-time','msg-dblcheck-ack','msg-dblcheck','msg-check']);
  const selector=[...known].flatMap(k=>['[data-icon="'+k+'"]','[data-testid="'+k+'"]']).join(',');
  const icons=[...e.querySelectorAll(selector)].filter(n=>!n.closest(quoted)).flatMap(n=>[n.getAttribute('data-icon'),n.getAttribute('data-testid')].filter(v=>known.has(v)));
  const unique=[...new Set(icons)];return unique.length===1?unique[0]:'';
 };
 const outgoing=()=>messageRows().filter(e=>{const id=messageId(e);return id.startsWith('true_')||!id.startsWith('false_')&&!!receiptIcon(e);}).slice(-50).map(e=>{
  const id=messageId(e);
  const content=[...e.querySelectorAll('[data-testid="msg-text"],.selectable-text,[data-pre-plain-text]')].find(n=>!n.closest('[data-testid*="quoted"],[data-testid*="reply-preview"]'));
  return {id,text:textOf(content),icon:receiptIcon(e)};
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
 const searchBox=()=>{const els=inputs(side,'[contenteditable="true"][role="textbox"],input[type="text"],[data-testid="chat-list-search"]');return els.length===1?els[0]:null;};
 const rows=()=>{
  let els=[...side.querySelectorAll('#pane-side [role="row"],#pane-side [role="listitem"],[aria-label="Chat list"] [role="row"]')].filter(visible);
  if(!els.length)els=[...side.querySelectorAll('#pane-side [data-testid="cell-frame-container"]')].filter(visible);
  els=els.filter(e=>!els.some(other=>other!==e&&e.contains(other)));
  return els.flatMap(e=>{const title=e.querySelector('[data-testid="cell-frame-title"] span[title],span[title][dir="auto"],span[title]');const name=norm(title?.getAttribute('title')||textOf(title));return name?[{element:e,name}]:[];});
 };
 const op=payload.op,args=payload.args||{};
 if(op==='state')return state();
 if(op==='scroll_bottom'){for(const e of scrollers())e.scrollTop=e.scrollHeight;return state();}
 if(op==='open_contact_info'){
  const title=headerTitle(),contact=norm(title?.getAttribute('title')||textOf(title));session.proof=null;
  if(!title||!contact||key(contact)!==key(args.contact))return {status:'blocked',reason:'Chat name changed before opening Contact info.'};
  const previous=panelRoots();
  // Close old contact/card details first; only a fresh active-chat header action proves the source.
  session.infoRequest={main,header:title,contact,previous,phase:previous.length?'closing':'opening'};
  if(previous.length){
   const buttons=[...new Set(previous.flatMap(p=>[...(p.querySelector('header')?.querySelectorAll('[data-icon="x"],[data-icon="x-alt"],[data-testid="btn-closer-drawer"],button,[role="button"]')||[])].filter(e=>e.matches('[data-icon="x"],[data-icon="x-alt"],[data-testid="btn-closer-drawer"]')||['close','close contact info','×','✕'].includes(key(e.getAttribute('aria-label')||textOf(e)))).map(e=>e.closest('button,[role="button"]')||e)))].filter(e=>visible(e)&&typeof e.click==='function');
   if(buttons.length!==1){session.infoRequest=null;return {status:'blocked',reason:'Close the existing Contact info/card panel, then prepare again.'};}
   buttons[0].click();return {status:'contact_info_closing'};
  }
  title.click();return {status:'opening_contact_info'};
 }
 if(op==='verify_contact_info'){
  const title=headerTitle(),contact=norm(title?.getAttribute('title')||textOf(title)),request=session.infoRequest;
  if(!request||request.main!==main||request.header!==title||request.contact!==contact||key(contact)!==key(args.contact)||!composer())return {status:'blocked',reason:'Chat name or input changed while verifying Contact info.'};
  if(request.phase==='closing'){
   if(request.previous.some(e=>e.isConnected&&visible(e)))return {status:'waiting_contact_info',reason:'Waiting for old Contact info to close.'};
   request.phase='opening';title.click();return {status:'opening_contact_info'};
  }
  const info=contactInfo(contact);
  if(!info)return {status:'waiting_contact_info',reason:'Contact info must show the matching name and one full international phone number.'};
  if(args.phone&&info.phone!=='+'+args.phone)return {status:'blocked',reason:'Contact info phone number does not match the requested number.'};
  const old=session.proof;
  if(!old||old.main!==main||old.header!==title||old.editor!==composer()||old.panel!==info.panel||old.phone!==info.phone||old.contact!==contact)session.proof={main,header:title,editor:composer(),panel:info.panel,contact,phone:info.phone,nonce:crypto.randomUUID()};
  return {status:'contact_verified',recipient:contact,recipient_phone:info.phone};
 }
 if(op==='search'){session.proof=null;session.infoRequest=null;return {status:put(searchBox(),args.query)?'searching':'blocked',reason:'A unique contact search field is required.'};}
 if(op==='results'){
  const box=searchBox();return {status:'ready',session:session.id,query:norm(box?.isContentEditable?box.innerText:box?.value),matches:rows().filter(r=>key(r.name).includes(key(args.query))).map(r=>({name:r.name})).slice(0,20)};
 }
 if(op==='select'){
  session.proof=null;
  session.infoRequest=null;
  const matches=rows().filter(r=>key(r.name)===key(args.contact));
  if(matches.length!==1)return {status:matches.length?'ambiguous':'not_found',matches:matches.map(r=>({name:r.name}))};
  matches[0].element.click();return {status:'selected',recipient:matches[0].name};
 }
 const extraContext=()=>!!main?.querySelector('footer [data-testid*="quoted"],footer [data-testid*="reply-preview"],footer [data-testid*="edit-message"],[data-testid="media-editor"],[data-testid="media-preview"]');
 const pinned=()=>{const s=identity();return s.session===args.session&&s.recipient===args.recipient&&!!s.recipient_id&&s.recipient_id===args.recipient_id&&(!args.context&&!s.recipient_id.startsWith('phone:')||s.context===args.context);};
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
