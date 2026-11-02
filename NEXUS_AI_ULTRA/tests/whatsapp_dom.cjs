const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../static/whatsapp_dom.js'),'utf8');
const fixture=fs.readFileSync(path.join(__dirname,'fixtures/whatsapp/index.html'),'utf8');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage();await page.route('https://web.whatsapp.com/**',r=>r.fulfill({body:fixture,contentType:'text/html'}));
 const call=(op,args={})=>page.evaluate(({source,op,args})=>eval('('+source+')')({op,args}),{source,op,args});
 const reset=async()=>{await page.goto('https://web.whatsapp.com/');await page.waitForFunction(()=>document.querySelector('#composer'));};
 const pin=async(message)=>{const s=await call('state');return {session:s.session,recipient:s.recipient,recipient_id:s.recipient_id,message,approval_before:s.outgoing.map(m=>m.id)};};
 try{
  await reset();assert.equal((await call('search',{query:'Saad Cheema'})).status,'searching');assert.equal((await call('results',{query:'Saad Cheema'})).matches.length,1);
  const message='Kidhar ho?\nQuote " and emoji 😀 </script><img src=x onerror=alert(1)>';
  const pinned=await pin(message);assert.equal((await call('compose',pinned)).status,'composed');assert.equal(await page.evaluate(()=>clicks),0);
  assert(!(await page.locator('#composer img').count()),'Message must stay plain text');
  const sent=await call('send',pinned);assert(sent.clicked);assert.deepEqual(sent.before,['true_923001234567@c.us_OLD']);
  const after=await call('state');assert.equal(after.outgoing.at(-1).text,message);assert.equal(after.outgoing.at(-1).icon,'msg-check');assert.equal(await page.evaluate(()=>clicks),1);
  await reset();let p=await pin('hello');await call('compose',p);await page.locator('#composer').fill('Changed by user');assert(!(await call('send',p)).clicked);assert.equal(await page.evaluate(()=>clicks),0);
  await reset();p=await pin('hello');await call('compose',p);await page.locator('#main header span').evaluate(e=>{e.title='Other Contact';e.textContent='Other Contact';});assert(!(await call('send',p)).clicked);
  await reset();p=await pin('hello');await page.locator('#composer').fill('Existing unsent text');assert.equal((await call('compose',p)).status,'blocked');assert.equal(await page.locator('#composer').innerText(),'Existing unsent text');
  await reset();await page.locator('#pane-side [role=row]').first().evaluate(e=>e.after(e.cloneNode(true)));assert.equal((await call('select',{contact:'Saad Cheema'})).status,'ambiguous');
  await reset();p=await pin('hello');await call('compose',p);await page.locator('footer').evaluate(e=>{const preview=document.createElement('div');preview.dataset.testid='quoted-message';e.append(preview);});assert(!(await call('send',p)).clicked);
  await reset();p=await pin('hello');await call('compose',p);await page.locator('#history').evaluate(e=>{const copy=e.firstElementChild.cloneNode(true);copy.dataset.id='true_923001234567@c.us_INTERVENING';e.append(copy);});assert(!(await call('send',p)).clicked);
  await reset();await page.locator('#side').evaluate(e=>e.remove());await page.locator('body').evaluate(e=>{const qr=document.createElement('div');qr.dataset.ref='fixture-qr';e.append(qr);});assert.equal((await call('state')).status,'login_required');
  await page.route('https://untrusted.test/**',r=>r.fulfill({body:fixture,contentType:'text/html'}));await page.goto('https://untrusted.test/');assert.equal((await call('send',{})).status,'wrong_origin');
  console.log('WhatsApp DOM fixtures: exact search, plain-text insertion, atomic recipient/message/context guards, new IDs/ticks, QR and origin checks passed; no real WhatsApp network or messages');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
