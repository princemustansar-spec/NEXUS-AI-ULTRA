const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try {
  for(const mode of ['native','bridge']) {
   const page=await browser.newPage();const actions=[];
   await page.route('http://nexus.test/**',route=>{
    const p=new URL(route.request().url()).pathname;
    if(p==='/api/avatar/status')return route.fulfill({json:{token:'fixture',available:true,drag_mode:mode,voice:{phase:'idle'},tts:{phase:'idle'}}});
    if(p.startsWith('/api/avatar/')){assert.equal(route.request().headers()['x-nexus-token'],'fixture');actions.push(p);return route.fulfill({json:{requested:true}});}
    const f=path.join(root,p);return route.fulfill({body:fs.readFileSync(f),contentType:f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html'});
   });
   await page.goto('http://nexus.test/static/avatar.html');await page.waitForFunction(()=>document.querySelector('#phase').textContent==='READY');
   await page.evaluate(()=>{window.moves=[];window.pywebview={platform:'edgechromium',_jsApiCallback:(...a)=>moves.push(a)};});
   if(process.env.PYWEBVIEW_CUSTOMIZE_JS){let sdk=fs.readFileSync(process.env.PYWEBVIEW_CUSTOMIZE_JS,'utf8');for(const [k,v]of Object.entries({text_select:'False',easy_drag:'False',drag_region_direct_target_only:'False',drag_selector:'.pywebview-drag-region',zoomable:'False',draggable:'False'}))sdk=sdk.replaceAll(`%(${k})s`,v);await page.addScriptTag({content:sdk});}
   await page.locator('canvas').hover();await page.mouse.down();await page.mouse.move(350,300);await page.waitForTimeout(150);await page.mouse.up();
   if(mode==='native'){assert.deepEqual(actions,['/api/avatar/drag']);assert.equal(await page.evaluate(()=>moves.length),0);}
   else if(process.env.PYWEBVIEW_CUSTOMIZE_JS)assert((await page.evaluate(()=>moves)).some(a=>a[0]==='pywebviewMoveWindow'));
   await page.locator('canvas').hover();await page.locator('#dashboard').click();assert(actions.includes('/api/avatar/dashboard'));assert.equal(actions.filter(a=>a==='/api/avatar/drag').length,mode==='native'?1:0);
   await page.close();
  }
  console.log('Avatar drag: authenticated native dispatch, SDK fallback and independent buttons passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
