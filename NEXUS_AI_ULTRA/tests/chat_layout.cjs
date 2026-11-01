const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox']});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const state={name:'NEXUS AI ULTRA',token:'test',providers:[],provider_status:{},tools:[],pending:[],activity:[],notifications:[],roots:[],chat:Array.from({length:16},(_,i)=>({role:i%2?'assistant':'user',text:'A readable chat message. '.repeat(15),provider:'Test',model:'test'})),voice:{phase:'idle'},monitor:{cpu:3,ram_percent:25,disk_percent:20,ram_used:1e9,ram_total:4e9,ram_available:3e9,disk_free:1e11,download:0,upload:0}};
 await page.route('http://nexus.test/**',async route=>{
  const url=new URL(route.request().url());
  if(url.pathname==='/api/state')return route.fulfill({json:state});
  const file=path.join(root,url.pathname==='/'?'static/index.html':url.pathname);
  return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':'text/html'});
 });
 try{
  for(const [width,height] of [[1366,768],[1920,1080],[800,600],[390,844]]){
   await page.setViewportSize({width,height});await page.goto('http://nexus.test/');
   await page.waitForFunction(()=>document.querySelector('#cpu').textContent!=='—');
   await page.locator('#chat-input').fill('Keep my unsent question');
   await page.locator('#chat-expand').click();
   await page.waitForTimeout(250);
   const layout=await page.evaluate(()=>{const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {width:r.width,height:r.height,bottom:r.bottom,top:r.top};};return {panel:rect('.chat-panel'),messages:rect('.messages'),input:rect('#chat-input'),send:rect('#send-chat'),width:document.documentElement.scrollWidth,main:rect('main')};});
   assert(layout.width<=width+1,'horizontal overflow');
   assert(layout.panel.width>=layout.main.width-40,'chat must use main content width');
   assert(layout.messages.height>=140,'reading area too short');
   assert(layout.input.height>=64,'composer too short');
   assert(layout.send.bottom<=layout.panel.bottom+1,'Send clipped');
   if(width>1100)assert(layout.panel.bottom<=height+1,'desktop panel below viewport');
   assert.equal(await page.locator('#chat-input').inputValue(),'Keep my unsent question');
   if(process.env.CHAT_SCREENSHOT_DIR){fs.mkdirSync(process.env.CHAT_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.CHAT_SCREENSHOT_DIR,`chat-${width}x${height}.png`)});}
   await page.locator('#chat-expand').click();
   assert(await page.locator('.hero-grid').isVisible(),'dashboard must restore');
   const dashboardComposer=await page.evaluate(()=>({send:document.querySelector('#send-chat').getBoundingClientRect().bottom,panel:document.querySelector('.chat-panel').getBoundingClientRect().bottom}));
   assert(dashboardComposer.send<=dashboardComposer.panel+1,'dashboard Send clipped');
   assert.equal(await page.locator('#chat-input').inputValue(),'Keep my unsent question');
   console.log(`${width}x${height}: full chat ${Math.round(layout.panel.width)}x${Math.round(layout.panel.height)}, reading area ${Math.round(layout.messages.height)}px; controls and draft preserved`);
  }
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
