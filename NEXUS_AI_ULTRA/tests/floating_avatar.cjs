const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:310,height:370},deviceScaleFactor:1});const errors=[],requests=[],actions=[];
 page.on('pageerror',e=>errors.push(e.message));
 let state={token:'fixture-session',available:true,voice:{phase:'idle'},tts:{phase:'idle'},thinking:false,emergency:false};
 await page.route('http://nexus.test/**',async route=>{
  const pathname=new URL(route.request().url()).pathname;requests.push(pathname);
  if(pathname==='/api/avatar/status')return route.fulfill({json:state});
  if(pathname.startsWith('/api/handsfree/')){const body=route.request().postDataJSON();assert(body.consent&&body.online_consent);assert.equal(route.request().headers()['x-nexus-token'],'fixture-session');actions.push(pathname);state.handsfree={active:pathname.endsWith('/start'),phase:pathname.endsWith('/start')?'listening':'off'};return route.fulfill({json:state.handsfree});}
  if(pathname.startsWith('/api/avatar/')){assert.equal(route.request().headers()['x-nexus-token'],'fixture-session');actions.push(pathname);return route.fulfill({json:{requested:true}});}
  const file=path.join(root,pathname);return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':'text/html'});
 });
 try{
  await page.goto('http://nexus.test/static/avatar.html');
  await page.waitForFunction(()=>document.querySelector('#avatar').dataset.renderer==='webgl');
  await page.waitForFunction(()=>document.querySelector('#phase').textContent==='READY');
  assert.equal(await page.locator('.avatar-shell').evaluate(e=>getComputedStyle(e).backgroundImage),'none');
  assert.equal(await page.locator('.avatar-shell').evaluate(e=>getComputedStyle(e).borderTopWidth),'0px');
  await page.mouse.move(500,500);await page.waitForTimeout(820);
  assert.equal(await page.locator('#mic').evaluate(e=>getComputedStyle(e).opacity),'0');
  assert.equal(await page.locator('header').evaluate(e=>getComputedStyle(e).opacity),'0');
  await page.locator('canvas').hover();await page.waitForTimeout(180);
  assert.equal(await page.locator('#mic').evaluate(e=>getComputedStyle(e).opacity),'1');
  await page.locator('#mic').click();await page.waitForFunction(()=>document.querySelector('#mic').dataset.active==='true');
  await page.locator('#mic').click();await page.waitForFunction(()=>document.querySelector('#mic').dataset.active==='false');
  assert.equal(actions.filter(a=>a==='/api/handsfree/start').length,1);
  assert.equal(actions.filter(a=>a==='/api/handsfree/stop').length,1);
  assert.equal(await page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
  const before=await page.locator('canvas').screenshot();await page.waitForTimeout(350);const after=await page.locator('canvas').screenshot();
  assert(!before.equals(after),'3D geometry must visibly move');
  state.voice={phase:'listening',level_dbfs:-15};await page.waitForFunction(()=>document.querySelector('#phase').textContent==='LISTENING');
  assert.equal(await page.locator('#level').evaluate(e=>e.style.width),'100%');
  state.voice={phase:'idle'};state.thinking=true;await page.waitForFunction(()=>document.querySelector('#phase').textContent==='THINKING');
  state.thinking=false;state.tts={phase:'speaking'};await page.waitForFunction(()=>document.querySelector('#phase').textContent==='SPEAKING');
  state.tts={phase:'idle'};state.emergency=true;await page.waitForFunction(()=>document.querySelector('#phase').textContent==='STOPPED');
  await page.locator('canvas').hover();await page.locator('#dashboard').click();await page.locator('#close').click();
  assert(actions.includes('/api/avatar/dashboard')&&actions.includes('/api/avatar/close'));
  await page.evaluate(()=>{localStorage.setItem('core-motion','off');dispatchEvent(new StorageEvent('storage'));});
  await page.waitForTimeout(150);const stillA=await page.locator('canvas').screenshot();await page.waitForTimeout(250);const stillB=await page.locator('canvas').screenshot();assert(stillA.equals(stillB),'motion Off must stop visible animation');
  if(process.env.AVATAR_SCREENSHOT_DIR){fs.mkdirSync(process.env.AVATAR_SCREENSHOT_DIR,{recursive:true});state.emergency=false;state.voice={phase:'listening',level_dbfs:-25};await page.waitForFunction(()=>document.querySelector('#phase').textContent==='LISTENING');await page.mouse.move(500,500);await page.waitForTimeout(820);await page.screenshot({path:path.join(process.env.AVATAR_SCREENSHOT_DIR,'floating-avatar.png'),omitBackground:true});}
  state.emergency=false;state.emotion='happy';await page.waitForFunction(()=>document.querySelector('#avatar').dataset.pose?.endsWith(':idle:happy'));
  const happy=await page.locator('canvas').screenshot();state.emotion='caring';await page.waitForFunction(()=>document.querySelector('#avatar').dataset.pose?.endsWith(':idle:caring'));
  const caring=await page.locator('canvas').screenshot();assert(!happy.equals(caring),'Avatar expression changes must affect rendered pixels even with motion Off');
  assert(requests.every(p=>p.startsWith('/static/')||p.startsWith('/api/avatar/')||p.startsWith('/api/handsfree/')),'avatar must not request AI providers, chat history or voice capture');assert.deepEqual(errors,[]);
  console.log('Figure-only + auto-voice start/stop:  WebGL pixels/movement, transparent background, live states, level, motion Off, authenticated controls, telemetry-only requests: passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
