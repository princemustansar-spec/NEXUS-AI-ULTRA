const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),out=process.env.HUMAN_AVATAR_PREVIEW||'/tmp/nexus-human-preview';
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:360,height:420},deviceScaleFactor:1});const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));
 let state={token:'fixture',available:true,avatar_style:'human',emotion:'friendly',voice:{phase:'idle'},tts:{phase:'idle'},handsfree:{active:false},thinking:false,emergency:false};
 await page.addInitScript(()=>localStorage.setItem('core-motion','off'));
 await page.route('http://nexus.test/**',r=>{const p=new URL(r.request().url()).pathname;requests.push(p);if(p==='/api/avatar/status')return r.fulfill({json:state});const file=path.join(root,p);return r.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});});
 try{
  await page.goto('http://nexus.test/static/avatar.html');await page.waitForFunction(()=>document.querySelector('#avatar').dataset.style==='human');
  await page.mouse.move(600,600);await page.waitForTimeout(800);fs.mkdirSync(out,{recursive:true});
  await page.screenshot({path:path.join(out,'nexus-human-avatar.png'),omitBackground:true});
  const box=await page.locator('#avatar').boundingBox(),clip={x:box.x+box.width*.33,y:box.y+box.height*.56,width:box.width*.34,height:box.height*.20};
  const quiet=await page.screenshot({clip});state.tts={phase:'speaking'};await page.waitForFunction(()=>document.querySelector('#avatar').dataset.pose==='human:speaking:friendly');const speaking=await page.screenshot({clip});assert(!quiet.equals(speaking),'Speech phase must visibly change the mouth region');
  await page.screenshot({path:path.join(out,'nexus-human-speaking.png'),omitBackground:true});
  state.tts={phase:'idle'};state.emotion='happy';await page.waitForFunction(()=>document.querySelector('#avatar').dataset.pose==='human:idle:happy');const happy=await page.locator('#avatar').screenshot();
  await page.screenshot({path:path.join(out,'nexus-human-happy.png'),omitBackground:true});
  state.emotion='caring';await page.waitForFunction(()=>document.querySelector('#avatar').dataset.pose==='human:idle:caring');assert(!happy.equals(await page.locator('#avatar').screenshot()),'Supportive expression must differ from happy');
  state.avatar_style='robot';await page.waitForFunction(()=>document.querySelector('#avatar').dataset.style==='robot');await page.screenshot({path:path.join(out,'nexus-classic-robot.png'),omitBackground:true});
  assert.deepEqual(errors,[]);assert(requests.every(p=>p.startsWith('/static/')||p==='/api/avatar/status'));
  assert.equal(await page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
  console.log('Human avatar passed: rendered portrait, mouth-region speech change, happy/caring expressions, live classic switch, transparency and telemetry-only requests. Preview: '+out);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
