const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1366,height:768}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const sent=[];let pending;
 const state={name:'NEXUS',token:'fixture',providers:[],provider_status:{},tools:[],pending:[],activity:[],notifications:[],chat:[],voice:{phase:'idle'},tts:{phase:'idle'},monitor:{cpu:1,ram_percent:20,disk_percent:20,ram_used:1e9,ram_total:4e9,ram_available:3e9,disk_free:1e11,download:0,upload:0}};
 await page.route('http://nexus.test/**',async route=>{
  const pathname=new URL(route.request().url()).pathname;
  if(pathname==='/api/state')return route.fulfill({json:state});
  if(pathname==='/api/chat'){sent.push(route.request().postDataJSON());pending=route;return;}
  const file=path.join(__dirname,'..',pathname==='/'?'static/index.html':pathname);
  return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':'text/html'});
 });
 const input=page.locator('#chat-input');
 const settle=async()=>{await pending.fulfill({json:{text:'fixture reply'}});pending=null;await page.waitForFunction(()=>!document.querySelector('#send-chat').disabled);};
 try{
  await page.goto('http://nexus.test/');await page.waitForFunction(()=>document.querySelector('#cpu').textContent!=='—');
  await input.fill('First line');await input.press('Shift+Enter');await input.press('a');
  assert.equal(await input.inputValue(),'First line\na');assert.equal(sent.length,0);
  await input.press('Enter');await page.waitForFunction(()=>document.querySelector('#send-chat').disabled);
  await page.waitForTimeout(80);assert.equal(sent.length,1);assert.equal(sent[0].text,'First line\na');assert.equal(sent[0].allow_paid,false);
  await input.press('Enter');await page.waitForTimeout(80);assert.equal(sent.length,1,'busy Enter must not duplicate request');
  await settle();assert.equal(await input.inputValue(),'');
  await input.fill('   ');await input.press('Enter');await page.waitForTimeout(80);assert.equal(sent.length,1,'whitespace must not send');
  await input.fill('IME draft');await input.dispatchEvent('keydown',{key:'Enter',isComposing:true});await input.dispatchEvent('keydown',{key:'Enter',keyCode:229});await page.waitForTimeout(80);assert.equal(sent.length,1,'IME composition Enter must not send');
  await input.dispatchEvent('keydown',{key:'Enter',repeat:true});await page.waitForTimeout(80);assert.equal(sent.length,1,'held key must not send');
  await input.fill('Manual send');await page.locator('#send-chat').click();await page.waitForTimeout(80);assert.equal(sent.length,2,'button must still send');await settle();
  await input.fill('Preserve on failure');await input.press('Enter');await page.waitForTimeout(80);assert.equal(sent.length,3);
  await pending.fulfill({status:503,json:{detail:'Synthetic offline'}});pending=null;await page.waitForFunction(()=>!document.querySelector('#send-chat').disabled);
  assert.equal(await input.inputValue(),'Preserve on failure');
  assert.deepEqual(errors,[]);console.log('Enter send / Shift+Enter newline / busy and held key / whitespace / IME / button / failure draft: passed');
 }finally{if(pending)await pending.fulfill({json:{text:'cleanup'}});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
