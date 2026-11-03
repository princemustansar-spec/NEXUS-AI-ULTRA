'use strict';
let whatsappLastDraft='';
function renderWhatsAppCenter(parent){
 parent.append(node('p','Open the NEXUS WhatsApp window and scan its QR code once. Use the exact saved contact name or an international number. Every Send requires confirmation of the recipient and exact message.'));
 const panel=card(parent,'WhatsApp'),output=node('p');output.id='whatsapp-output';
 const contact=field(panel,'Contact name or international number'),message=field(panel,'Exact message','textarea');contact.id='whatsapp-contact';message.id='whatsapp-message';
 let draft=whatsappLastDraft;
 const show=r=>{output.textContent=r.status+(r.reason?' · '+r.reason:'')+(r.message?' · '+r.message:'')+(r.matches?' · '+r.matches.map(m=>m.name).join(', '):'')+(r.verification?' · Verification: '+JSON.stringify(r.verification):'');};
 const action=(label,fn)=>{const b=button(label,async()=>{if(b.disabled)return;b.disabled=true;try{await fn();}finally{b.disabled=false;}});panel.append(b);};
 action('Open WhatsApp / QR login',async()=>show((await api('tools/whatsapp_open',{})).result));
 action('Check WhatsApp / send status',async()=>show((await api('tools/whatsapp_status',{draft_id:draft})).result));
 action('Find contact',async()=>show((await api('tools/whatsapp_search',{query:contact.value})).result));
 action('Prepare & review send',async()=>{
  const prepared=(await api('tools/whatsapp_prepare',{contact:contact.value,message:message.value})).result;show(prepared);
  if(prepared.status!=='draft_prepared')return;
  draft=prepared.draft_id;whatsappLastDraft=draft;
  const pending=await api('tools/whatsapp_send',{draft_id:draft});
  if(pending.approval_required){await refresh();navigate('Safety Center');toast('Review the recipient and exact message, then approve Send.');}
 });
 panel.append(output);
}
