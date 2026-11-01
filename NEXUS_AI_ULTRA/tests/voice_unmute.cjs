const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1366,height:768}}),calls=[];
 const state={name:'NEXUS',token:'fixture',voice_muted:true,providers:[],provider_status:{},tools:[],pending:[],activity:[],notifications:[],roots:[],chat:[],voice:{phase:'cancelled'},tts:{phase:'idle'},handsfree:{active:false},avatar_settings:{},monitor:{cpu:3,ram_percent:25,disk_percent:20,ram_used:1e9,ram_total:4e9,ram_available:3e9,disk_free:1e11,download:0,upload:0}};
 await page.route('http://nexus.test/**',async route=>{
  const p=new URL(route.request().url()).pathname;
  if(p==='/api/state')return route.fulfill({json:state});
  if(p==='/api/avatar/status')return route.fulfill({json:{token:'fixture',available:true,voice_muted:state.voice_muted,voice:state.voice,tts:state.tts,handsfree:state.handsfree}});
  if(p.startsWith('/api/')){
   const body=route.request().postDataJSON();calls.push({p,body});assert.equal(route.request().headers()['x-nexus-token'],'fixture');
   if(p==='/api/voice/mute'){state.voice_muted=body.muted;await new Promise(r=>setTimeout(r,200));return route.fulfill({json:{muted:body.muted}});}
   if(p==='/api/handsfree/start'){assert.equal(body.unmute,true);assert(body.consent&&body.online_consent);state.voice_muted=false;state.handsfree={active:true,phase:'listening'};return route.fulfill({json:state.handsfree});}
   if(p==='/api/handsfree/stop'){state.handsfree={active:false};return route.fulfill({json:state.handsfree});}
   return route.fulfill({json:{}});
  }
  const f=path.join(root,p==='/'?'static/index.html':p);return route.fulfill({body:fs.readFileSync(f),contentType:f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html'});
 });
 try {
  await page.goto('http://nexus.test/');await page.locator('#navigation').getByRole('button',{name:'Voice Assistant',exact:false}).click();
  const unmute=page.locator('#voice-mute-button');await unmute.click();assert(await unmute.isDisabled());
  await page.waitForFunction(()=>document.querySelector('#voice-mute-button').textContent==='Mute microphone & speaker');
  assert.deepEqual(calls.filter(c=>c.p==='/api/voice/mute').map(c=>c.body),[{muted:false}]);
  assert(!calls.some(c=>['/api/voice/cancel','/api/tts/stop'].includes(c.p)),'Unmute must not cancel a voice session');
  state.voice_muted=true;await page.goto('http://nexus.test/static/avatar.html');await page.waitForFunction(()=>document.querySelector('#phase').textContent==='READY');
  assert.equal(calls.filter(c=>c.p==='/api/handsfree/start').length,0,'Opening avatar must not clear saved mute');
  await page.locator('canvas').hover();await page.getByRole('button',{name:'Unmute and start auto voice',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#mic').dataset.active==='true');assert(!state.voice_muted);
  await page.locator('#mic').click();await page.waitForFunction(()=>document.querySelector('#mic').dataset.active==='false');
  console.log('Unmute: explicit GUI value, pending-click guard, no cancellation, floating click-to-unmute/start, pause passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
