const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage(),calls=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
 const state={token:'fixture',available:true,voice:{phase:'listening'},tts:{phase:'speaking'},handsfree:{active:true,phase:'speaking',interrupt_mode:'any'}};
 await page.route('http://nexus.test/**',route=>{
  const p=new URL(route.request().url()).pathname;
  if(p==='/api/avatar/status')return route.fulfill({json:state});
  if(p==='/api/handsfree/interrupt'){assert.equal(route.request().headers()['x-nexus-token'],'fixture');calls.push(p);state.handsfree.phase='listening';state.tts.phase='cancelled';return route.fulfill({json:{interrupted:true}});}
  const f=path.join(root,p);return route.fulfill({body:fs.readFileSync(f),contentType:f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html'});
 });
 try{
  await page.goto('http://nexus.test/static/avatar.html');await page.waitForFunction(()=>!document.querySelector('#interrupt').disabled);
  await page.locator('canvas').hover();await page.getByRole('button',{name:'Stop reply and listen',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#phase').textContent==='LISTENING');
  assert.equal(await page.locator('#mic').getAttribute('data-active'),'true');assert.equal(calls.length,1);
  assert(await page.locator('#interrupt').isDisabled());assert.deepEqual(errors,[]);
  console.log('Floating interruption: authenticated stop/listen button, auto voice remains active and state returns to listening passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
