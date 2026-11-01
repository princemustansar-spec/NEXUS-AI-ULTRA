const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1366,height:768}});const errors=[],calls=[];page.on('pageerror',e=>errors.push(e.message));
 const state={name:'NEXUS',token:'fixture',providers:[],provider_status:{},tools:[],pending:[],activity:[],notifications:[],roots:[],chat:[],voice:{phase:'idle'},tts:{phase:'idle'},handsfree:{active:false},avatar_settings:{desktop_mode:'gui',auto_voice:true,visible:false},monitor:{cpu:3,ram_percent:25,disk_percent:20,ram_used:1e9,ram_total:4e9,ram_available:3e9,disk_free:1e11,download:0,upload:0}};
 await page.route('https://nexus.test/**',async route=>{
  const p=new URL(route.request().url()).pathname;
  if(p==='/api/state')return route.fulfill({json:state});
  if(p.startsWith('/api/')){
   assert.equal(route.request().headers()['x-nexus-token'],'fixture');calls.push(p);
   if(p==='/api/settings')Object.assign(state.avatar_settings,route.request().postDataJSON().avatar_settings);
   if(p==='/api/avatar/show')state.avatar_settings.visible=true;
   if(p==='/api/avatar/close')state.avatar_settings.visible=false;
   return route.fulfill({json:{updated:true,saved:true,visible:state.avatar_settings.visible}});
  }
  const file=path.join(root,p==='/'?'static/index.html':p);return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':'text/html'});
 });
 try{
  await page.goto('https://nexus.test/');await page.waitForFunction(()=>document.querySelector('#cpu').textContent!=='—');
  await page.locator('#settings-shortcut').click();
  await page.locator('#floating-start-mode').selectOption('floating');await page.locator('#floating-auto-voice').uncheck();
  await page.getByRole('button',{name:'Save floating settings',exact:true}).click();
  await page.waitForTimeout(100);assert.equal(state.avatar_settings.desktop_mode,'floating');assert.equal(state.avatar_settings.auto_voice,false);
  await page.getByRole('button',{name:'Show floating AI',exact:true}).click();await page.waitForTimeout(100);
  assert(state.avatar_settings.visible);assert(!calls.includes('/api/handsfree/start'),'show with auto voice off must not enable microphone');
  assert(await page.locator('#workspace').isVisible());assert.equal(await page.locator('#page-title').textContent(),'Settings');
  await page.getByRole('button',{name:'Hide floating AI',exact:true}).click();await page.waitForTimeout(100);assert(!state.avatar_settings.visible);
  await page.getByRole('button',{name:'Update desktop shortcut',exact:true}).click();await page.waitForTimeout(100);assert(calls.includes('/api/desktop/shortcut'));
  assert.deepEqual(errors,[]);console.log('Settings: saved launch mode, opt-out microphone, show/hide without replacing GUI, shortcut update: passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
