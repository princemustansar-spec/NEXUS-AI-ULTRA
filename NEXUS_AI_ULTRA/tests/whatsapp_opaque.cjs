const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),source=fs.readFileSync(path.join(root,'static/whatsapp_dom.js'),'utf8');
const fixture=fs.readFileSync(path.join(__dirname,'fixtures/whatsapp/index.html'),'utf8'),nested=fs.readFileSync(path.join(__dirname,'fixtures/whatsapp/nested.js'),'utf8'),opaque=fs.readFileSync(path.join(__dirname,'fixtures/whatsapp/opaque.js'),'utf8');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});const page=await browser.newPage();
 await page.route('https://web.whatsapp.com/**',r=>r.fulfill({body:fixture,contentType:'text/html'}));
 const call=(op,args={})=>page.evaluate(({source,op,args})=>eval('('+source+')')({op,args}),{source,op,args});
 const reset=async()=>{await page.goto('https://web.whatsapp.com/');await page.evaluate(s=>eval('('+s+')')(),nested);await page.evaluate(s=>eval('('+s+')')(),opaque);};
 const verify=async(phone='')=>{assert(['opening_contact_info','contact_info_open','contact_info_closing'].includes((await call('open_contact_info',{contact:'Nexus Test Contact'})).status));let result;for(let i=0;i<3;i++){result=await call('verify_contact_info',{contact:'Nexus Test Contact',phone});if(result.status!=='opening_contact_info')return result;}return result;};
 const prepare=async()=>{await call('scroll_bottom');const s=await call('state');const p={session:s.session,recipient:s.recipient,recipient_id:s.recipient_id,context:s.context,message:'Opaque layout message',approval_before:s.outgoing.map(m=>m.id)};assert.equal((await call('compose',p)).status,'composed');return p;};
 try{
  await reset();let s=await call('state');assert.equal(s.verification.message_rows,22);assert.equal(s.verification.identified_rows,22);assert.equal(s.verification.opaque_rows,22);assert.equal(s.recipient_id,'');assert.equal(s.outgoing.length,11);
  assert.equal((await verify()).status,'contact_verified');s=await call('state');assert.equal(s.recipient_phone,'+12025550101');assert.equal(s.recipient_id,'phone:+12025550101');
  let p=await prepare();assert.equal(await page.evaluate(()=>clicks),0);assert((await call('send',p)).clicked);s=await call('state');assert.equal(s.outgoing.at(-1).text,p.message);assert.equal(s.outgoing.at(-1).icon,'msg-check');assert.equal(await page.evaluate(()=>clicks),1);
  await reset();await verify();p=await prepare();await page.locator('[data-testid="fixture-phone"]').evaluate(e=>e.textContent='+1 202 555 0102');assert(!(await call('send',p)).clicked);assert.equal(await page.evaluate(()=>clicks),0);
  await reset();await verify();p=await prepare();await page.locator('[data-testid="drawer-right"]').evaluate(e=>e.remove());assert(!(await call('send',p)).clicked);
  await reset();await verify();p=await prepare();await page.locator('#pane-side [role="row"]').first().click();assert(!(await call('send',p)).clicked,'Even a same-name sidebar click invalidates the reviewed context');
  await reset();await page.evaluate(()=>fixturePhone='Hidden');assert.equal((await verify()).status,'waiting_contact_info');assert.equal((await call('state')).recipient_id,'');
  await reset();await page.evaluate(()=>fixturePanelName='Wrong Contact');assert.equal((await verify()).status,'waiting_contact_info');
  await reset();assert.equal((await verify('12025550199')).status,'blocked');assert.equal((await call('state')).recipient_id,'');
  await reset();await page.locator('[data-testid="conversation-info-header-chat-title"]').click();await page.locator('[data-testid="fixture-phone"]').evaluate(e=>e.textContent='+1 202 555 0102');assert.equal((await verify()).recipient_phone,'+12025550101','An old contact/card panel is closed and reopened from the active chat header');
  await reset();await call('open_contact_info',{contact:'Nexus Test Contact'});await page.locator('[data-testid="fixture-phone"]').evaluate(e=>{e.innerHTML='<span>+١</span> <span>٢٠٢</span> <span>٥٥٥</span> <span>٠١٠١</span>';});assert.equal((await call('verify_contact_info',{contact:'Nexus Test Contact'})).recipient_phone,'+12025550101');
  await reset();await page.locator('#history').evaluate(e=>e.replaceChildren());assert.equal((await verify()).status,'contact_verified');p=await prepare();assert((await call('send',p)).clicked);assert.equal((await call('state')).outgoing.at(-1).icon,'msg-check');
  await reset();await call('open_contact_info',{contact:'Nexus Test Contact'});await page.locator('[data-testid="drawer-right"] header span').evaluate(e=>e.textContent='Group info');assert.equal((await call('verify_contact_info',{contact:'Nexus Test Contact'})).status,'waiting_contact_info');
  await reset();await page.locator('#history [data-icon]').evaluateAll(els=>els.forEach(e=>{e.dataset.testid=e.dataset.icon;delete e.dataset.icon;}));assert.equal((await call('state')).outgoing.length,11);
  await reset();await call('open_contact_info',{contact:'Nexus Test Contact'});await page.locator('[data-testid="drawer-right"]').evaluate(e=>{const p=document.createElement('span');p.textContent='+1 202 555 0102';e.append(p);});assert.equal((await call('verify_contact_info',{contact:'Nexus Test Contact'})).status,'waiting_contact_info');
  await reset();await page.locator('#history [data-id]').nth(1).evaluate(e=>{const quote=document.createElement('div');quote.dataset.testid='quoted-message';quote.innerHTML='<div data-testid="msg-container" data-id="QUOTEDOPAQUE"><span class="selectable-text">Quoted outgoing text</span><i data-icon="msg-check"></i></div>';e.append(quote);});s=await call('state');assert.equal(s.outgoing.length,11,'Quoted receipt icons cannot turn incoming messages into outgoing messages');
  console.log('Opaque WhatsApp fixtures passed: 22 opaque rows, live Contact info number, exact approval context, receipts, missing/ambiguous/wrong number, closed panel, sidebar changes and quoted receipts; no real messages.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
