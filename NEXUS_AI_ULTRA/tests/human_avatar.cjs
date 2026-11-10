const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const rig={eyes:[[0,[.35,.335,.16,.115],[.352,.333,.122,.093]],[0,[.51,.335,.16,.115],[.500,.340,.122,.093]]],mouths:[[1,[.35,.475,.30,.157],[.369,.487,.247,.133]],[2,[.35,.475,.30,.157],[.369,.487,.247,.141]],[3,[.35,.475,.30,.157],[.369,.486,.247,.137]]],pivot:[.493,.685],neck:[.53,.79]};
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext();
  const helper=await context.newPage();
  const assets=await helper.evaluate(()=>{
   function image(sheet){const c=document.createElement('canvas');c.width=sheet?640:320;c.height=sheet?640:292;const x=c.getContext('2d');
    for(let i=0;i<(sheet?4:1);i++){const ox=sheet?(i%2)*320:0,oy=sheet?Math.floor(i/2)*320:0;x.save();x.translate(ox,oy);x.fillStyle='#d9aa91';x.beginPath();x.ellipse(158,98,80,90,0,0,7);x.fill();x.fillStyle='#d9aa91';x.fillRect(130,170,55,40);x.fillStyle='#718f91';x.fillRect(70,205,180,80);x.fillStyle='#453d38';if(i===0&&sheet){x.fillRect(120,113,25,2);x.fillRect(175,113,25,2);}else{x.fillRect(125,110,12,10);x.fillRect(180,110,12,10);}x.fillStyle='#9b4f4b';x.beginPath();x.ellipse(158,155,18,i?12:2,0,0,7);x.fill();x.restore();}return c.toDataURL().split(',')[1];}
   return {base:image(false),sheet:image(true)};
  });await helper.close();
  const profile={present:false,enabled:false,frames:false,revision:'',photo:'',expressions:'',rig,alignment:{x:0,y:0,scale:1}};
  const ready={present:true,enabled:true,frames:true,revision:'fixture',photo:'/api/human-avatar/assets/portrait.png?v=fixture',expressions:'/api/human-avatar/assets/expressions.png?v=fixture',rig,alignment:{x:0,y:0,scale:1}};
  const personal={profile:{preferred_name:'',welcome_enabled:false,speak_welcome:false,routine_in_welcome:false,news_on_start:false,emotions:true,tone:'friendly'},routines:[],startup:{available:false,enabled:false},ollama_fallback:false};
  const state={name:'NEXUS',token:'fixture',personal_settings:personal.profile,human_avatar:profile,providers:[],provider_status:{},tools:[],pending:[],activity:[],notifications:[],roots:[],chat:[],voice:{phase:'idle'},tts:{phase:'idle'},handsfree:{active:false},avatar_settings:{},monitor:{cpu:1,ram_percent:20,disk_percent:20,ram_used:1e9,ram_total:12e9,ram_available:8e9,disk_free:1e11,download:0,upload:0}};
  const page=await context.newPage({viewport:{width:1366,height:900}}),errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{window.__sources=[];window.EventSource=class{constructor(url){this.url=url;window.__sources.push(this);}close(){this.closed=true;}};});
  await page.route('https://nexus.test/**',route=>{
   const req=route.request(),p=new URL(req.url()).pathname;
   if(p==='/api/state')return route.fulfill({json:state});
   if(p==='/api/accounts/status')return route.fulfill({json:{chatgpt:{},claude:{},enabled:{}}});
   if(p==='/api/personal')return route.fulfill({json:personal});
   if(p==='/api/human-avatar')return route.fulfill({json:profile});
   if(p==='/api/human-avatar/assets/portrait.png'||p==='/api/human-avatar/assets/expressions.png')return route.fulfill({body:Buffer.from(p.includes('portrait.png')?assets.base:assets.sheet,'base64'),contentType:'image/png'});
   if(p.startsWith('/api/')){
    assert.equal(req.headers()['x-nexus-token'],'fixture');writes.push(p);
    if(p==='/api/human-avatar/import'){assert(req.postDataBuffer().length);Object.assign(profile,ready);return route.fulfill({json:profile});}
    if(p==='/api/human-avatar/settings'){Object.assign(profile,req.postDataJSON());return route.fulfill({json:profile});}
    if(p==='/api/human-avatar/photo'){Object.assign(profile,{present:false,enabled:false,frames:false});return route.fulfill({json:profile});}
    return route.fulfill({json:{saved:true}});
   }
   const f=path.join(root,p==='/'?'static/index.html':p);return route.fulfill({body:fs.readFileSync(f),contentType:f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('https://nexus.test/');await page.waitForFunction(()=>document.title==='NEXUS');
  assert.equal(await page.locator('#human-core').count(),0);assert.equal(await page.locator('#ai-core').evaluate(e=>getComputedStyle(e).visibility),'visible');
  await page.locator('#settings-shortcut').click();await page.locator('#human-avatar-file').waitFor();assert.equal(writes.length,0,'Opening settings has no voice/inference/import side effects');
  await page.waitForFunction(()=>!document.querySelector('#human-avatar-file').disabled);await page.locator('#human-avatar-file').setInputFiles({name:'fixture.nexus-avatar',mimeType:'application/zip',buffer:Buffer.from('synthetic transport fixture')});
  await page.waitForFunction(()=>state.human_avatar.enabled===true);
  assert.equal(await page.locator('#human-core').count(),0,'Import must not mount a dashboard portrait');
  assert.equal(await page.evaluate(()=>window.__sources.length),0,'Dashboard must not open an avatar stream');
  await page.locator('#human-avatar-mode').selectOption('core');await page.getByRole('button',{name:'Apply avatar',exact:true}).click();await page.waitForFunction(()=>state.human_avatar.enabled===false);
  await page.locator('#human-avatar-mode').selectOption('human');await page.getByRole('button',{name:'Apply avatar',exact:true}).click();await page.waitForFunction(()=>state.human_avatar.enabled===true);
  await page.locator('[data-page="Dashboard"]').click();await page.evaluate(()=>setCore('listening'));
  assert.equal(await page.locator('#ai-core').evaluate(e=>getComputedStyle(e).visibility),'visible');assert.equal(await page.locator('#human-core').count(),0);
  console.log('Floating settings passed: local import, mode switching and unchanged dashboard AI Core; no dashboard portrait renderer or stream.');
  for(const noGL of [false,true]){
   const floating=await context.newPage({viewport:{width:280,height:290}}),actions=[],floaterErrors=[];floating.on('pageerror',e=>floaterErrors.push(e.message));
   await floating.addInitScript(noGL=>{window.__sources=[];window.EventSource=class{constructor(url){window.__sources.push(this);}close(){this.closed=true;}};if(noGL){const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl'?null:original.call(this,type,...args);};}},noGL);
   const packet={token:'fixture',drag_mode:'native',voice:{phase:'idle'},tts:{phase:'idle'},handsfree:{active:false},human_avatar:ready};
   await floating.route('https://nexus.test/**',route=>{const request=route.request(),p=new URL(request.url()).pathname;
    if(p==='/api/avatar/status')return route.fulfill({json:packet});
    if(p.includes('/api/human-avatar/assets/'))return route.fulfill({body:Buffer.from(p.includes('portrait')?assets.base:assets.sheet,'base64'),contentType:'image/png'});
    if(p.startsWith('/api/')){assert.equal(request.headers()['x-nexus-token'],'fixture');actions.push(p);return route.fulfill({json:{requested:true}});}
    const f=path.join(root,p);return route.fulfill({body:fs.readFileSync(f),contentType:f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html'});
   });
   await floating.goto('https://nexus.test/static/avatar.html');await floating.waitForFunction(()=>Number(document.querySelector('#human-floating')?.dataset.frames)>1);
   await floating.evaluate(()=>localStorage.setItem('core-motion','on'));
   const face=floating.locator('#human-floating');
   const emit=value=>floating.evaluate(value=>{for(const source of window.__sources.filter(s=>!s.closed))source.onmessage?.({data:JSON.stringify(value)});},value);
   const idle={enabled:true,blocked:false,phase:'idle',emotion:'neutral',job_id:'j1',animation:{playing:false}};
   await emit({...idle,phase:'thinking'});await floating.waitForFunction(()=>document.querySelector('#human-floating').dataset.phase==='thinking');assert.equal(await face.getAttribute('data-pose'),'0');
   await emit({...idle,phase:'listening'});await floating.waitForFunction(()=>document.querySelector('#human-floating').dataset.phase==='listening');
   await emit({...idle,phase:'speaking',animation:{playing:true,mode:'audio-envelope',position_ms:100,age_ms:0,cues:[[100,.9,2],[400,.9,2],[500,0,0]]}});await floating.waitForFunction(()=>document.querySelector('#human-floating').dataset.pose==='2');
   await floating.waitForTimeout(650);assert.equal(await face.getAttribute('data-pose'),'0','Expired cues close the floating mouth');await emit(idle);
   for(const emotion of ['happy','curious']){await emit({...idle,emotion});await floating.waitForTimeout(120);assert((await face.screenshot()).length>1500,'Expression must keep the floating portrait visible');}await emit(idle);
   await floating.evaluate(()=>localStorage.setItem('core-motion','off'));await floating.waitForTimeout(130);const before=await face.screenshot();await floating.waitForTimeout(250);assert(before.equals(await face.screenshot()),'Motion Off keeps a stable portrait');await floating.evaluate(()=>localStorage.setItem('core-motion','on'));
   if(!noGL){
    // Actual BroadcastChannel between GUI speech observers and the floating view.
    await page.evaluate(()=>{window.testUtterance=new SpeechSynthesisUtterance('Ooh');attachNexusHumanVoice(testUtterance,'Ooh');testUtterance.dispatchEvent(new Event('start'));const e=new Event('boundary');Object.defineProperties(e,{name:{value:'word'},charIndex:{value:0},charLength:{value:3}});testUtterance.dispatchEvent(e);window.testWordTimer=setInterval(()=>testUtterance.dispatchEvent(e),90);});
    await floating.waitForFunction(()=>document.querySelector('#human-floating').dataset.pose==='2');await page.evaluate(()=>clearInterval(window.testWordTimer));
    await emit({...idle,blocked:true});await floating.waitForFunction(()=>document.querySelector('#human-floating').dataset.pose==='0');await page.evaluate(()=>testUtterance.dispatchEvent(new Event('end')));await emit(idle);
    assert.equal(await page.locator('#human-core').count(),0,'Cross-window speech must leave the dashboard Core intact');
   }
   const target=noGL?'#human-floating':'#avatar';await floating.locator(target).hover();await floating.locator(target).dispatchEvent('pointerdown',{button:0});await floating.getByRole('button',{name:'Open NEXUS',exact:true}).click();assert(actions.includes('/api/avatar/drag')&&actions.includes('/api/avatar/dashboard'));
   packet.human_avatar={enabled:false};await floating.waitForFunction(()=>!document.querySelector('#human-floating'));if(!noGL)assert.equal(await floating.locator('#avatar').evaluate(e=>getComputedStyle(e).opacity),'1');else assert(await floating.locator('#fallback').isVisible());assert.deepEqual(floaterErrors,[]);await floating.close();
  }
  assert.deepEqual(errors,[]);await page.close();
  console.log('Floating-only Human Avatar passed: states, actual cue timing/expiry, cross-window browser boundaries, mute, motion Off, expressions, native drag dispatch, original floating Core restore and no-WebGL fallback.');

 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
