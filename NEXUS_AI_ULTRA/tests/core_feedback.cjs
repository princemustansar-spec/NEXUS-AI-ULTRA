const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1366,height:768},reducedMotion:'reduce'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));let captures=0;
 const state={name:'NEXUS AI ULTRA',token:'fixture',providers:[],provider_status:{},tools:[],pending:[],activity:[],notifications:[],chat:[],voice:{phase:'idle'},tts:{phase:'idle'},monitor:{cpu:3,ram_percent:25,disk_percent:20,ram_used:1e9,ram_total:4e9,ram_available:3e9,disk_free:1e11,download:0,upload:0}};
 await page.route('http://nexus.test/**',async route=>{
  const url=new URL(route.request().url());
  if(url.pathname==='/api/state')return route.fulfill({json:state});
  if(url.pathname==='/api/tts/stop')return route.fulfill({json:{stopped:true}});
  if(url.pathname==='/api/voice/start'){captures++;state.voice={job_id:'capture-1',operation:'capture',phase:'starting'};return route.fulfill({json:state.voice});}
  if(url.pathname==='/api/voice/status')return route.fulfill({json:state.voice});
  const file=path.join(root,url.pathname==='/'?'static/index.html':url.pathname);
  return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':'text/html'});
 });
 try{
  await page.goto('http://nexus.test/');await page.waitForFunction(()=>document.querySelector('#cpu').textContent!=='—');
  assert.equal(captures,0,'idle must never open microphone');
  assert.equal(await page.locator('#core-motion').textContent(),'Animation: Off (system)');
  assert.equal(await page.locator('.orbit-mid').evaluate(e=>getComputedStyle(e).animationName),'none');
  await page.locator('#core-motion').click();
  assert.equal(await page.locator('#core-motion').textContent(),'Animation: On');
  const before=await page.locator('.orbit-mid').evaluate(e=>getComputedStyle(e).transform);
  await page.waitForTimeout(200);
  const after=await page.locator('.orbit-mid').evaluate(e=>getComputedStyle(e).transform);
  assert.notEqual(before,after,'explicit On must animate even with OS reduced motion');
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/voice/start')),page.locator('#mic-button').click()]);assert.equal(captures,1);
  state.voice.phase='calibrating';await page.waitForFunction(()=>document.querySelector('#core-state').textContent.includes('CALIBRATING'));
  state.voice.phase='listening';state.voice.level_dbfs=-60;
  await page.waitForFunction(()=>document.querySelector('#core-state').textContent.includes('-60 dBFS'));
  assert.equal(await page.locator('#mic-button').getAttribute('aria-pressed'),'true');
  const quiet=Number(await page.locator('.core-scene').evaluate(e=>e.style.getPropertyValue('--voice-level')));
  state.voice.level_dbfs=-15;
  await page.waitForFunction(()=>document.querySelector('#core-state').textContent.includes('-15 dBFS'));
  const loud=Number(await page.locator('.core-scene').evaluate(e=>e.style.getPropertyValue('--voice-level')));
  assert(loud>quiet,'louder measured input must increase reaction');
  await page.locator('nav button[data-page="Voice Assistant"]').click();
  assert(await page.locator('#voice-level').isVisible(),'Voice Assistant needs visible input feedback');
  await page.waitForFunction(()=>document.querySelector('#voice-level').getAttribute('aria-valuetext')==='-15 dBFS');
  assert.equal(await page.locator('#voice-level').evaluate(e=>e.value),1);
  await page.locator('nav button[data-page="Dashboard"]').click();
  state.voice.phase='transcribing';await page.waitForFunction(()=>document.querySelector('#core-state').textContent==='TRANSCRIBING');
  assert.equal(Number(await page.locator('.core-scene').evaluate(e=>e.style.getPropertyValue('--voice-level'))),0,'old level must not remain after capture');
  state.voice.phase='error';state.voice.error='Microphone unavailable';
  await page.waitForFunction(()=>document.querySelector('#core-state').textContent.includes('MIC ERROR'));
  assert.equal(await page.locator('#mic-button').getAttribute('aria-pressed'),'false');
  await page.locator('#core-motion').click();
  assert.equal(await page.locator('.orbit-mid').evaluate(e=>getComputedStyle(e).animationName),'none');
  await page.reload();await page.waitForFunction(()=>document.querySelector('#core-motion').textContent==='Animation: Off');
  assert.equal(await page.locator('.orbit-mid').evaluate(e=>getComputedStyle(e).animationName),'none');
  assert.equal(captures,1,'reload must not restart microphone');
  assert.deepEqual(errors,[]);
  console.log('Core feedback: reduced-motion override/persistence, real animation frames, explicit capture, calibration, live levels, transcription, errors: passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
