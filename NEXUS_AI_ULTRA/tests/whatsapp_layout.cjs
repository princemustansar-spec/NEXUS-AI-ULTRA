const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'diagnostics/whatsapp_layout.py'),'utf8').match(/LAYOUT_JS = r"""([\s\S]*?)"""/)[1];
const fixture=fs.readFileSync(path.join(__dirname,'fixtures/whatsapp/index.html'),'utf8');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage();await page.route('https://web.whatsapp.com/**',r=>r.fulfill({body:fixture,contentType:'text/html'}));
 try{
  await page.goto('https://web.whatsapp.com/');const before=await page.content();let data=await page.evaluate(source);
  assert.equal(data.main.prefixed_ids,1);assert.equal(data.main.message_classes,1);assert.equal(await page.content(),before,'Inspection must not mutate the DOM');
  let text=JSON.stringify(data);assert(!text.includes('923001234567')&&!text.includes('Saad Cheema')&&!text.includes('Old message'));
  await page.locator('#history').evaluate(e=>document.body.append(e));data=await page.evaluate(source);
  assert.equal(data.main.prefixed_ids,0);assert.equal(data.document.prefixed_ids,1);assert(data.document_samples.some(chain=>chain.some(n=>n.in_main===false)));
  await page.locator('#history .message-out').evaluate(e=>{e.className='layout-bubble';e.dataset.messageId=e.dataset.id;delete e.dataset.id;});data=await page.evaluate(source);
  assert.equal(data.document.message_classes,0);assert.equal(data.document.alternate_ids,1);assert.equal(await page.evaluate(()=>clicks),0);
  await page.evaluate(()=>{const host=document.createElement('div');document.body.append(host);host.attachShadow({mode:'open'}).innerHTML='<div data-id="true_923001234567@c.us_SHADOW"></div>';});data=await page.evaluate(source);
  assert.equal(data.shadow_roots[0].counts.prefixed_ids,1);assert(!JSON.stringify(data).includes('923001234567'));
  console.log('Layout diagnostics passed: no DOM mutation/send, no chat text/names/raw IDs, global-vs-main roots, alternate attributes and open shadow roots.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
