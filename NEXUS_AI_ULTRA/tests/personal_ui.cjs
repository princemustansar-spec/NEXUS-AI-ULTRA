const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage(),errors=[],calls=[];page.on('pageerror',e=>errors.push(e.message));
 const profile={preferred_name:'',welcome_enabled:false,speak_welcome:true,routine_in_welcome:true,news_on_start:false,emotions:true,tone:'friendly'};
 const state={name:'NEXUS',token:'fixture',personal_settings:profile,providers:[{id:'ollama',name:'Ollama',base:'http://127.0.0.1:11434/v1',model:'',kind:'openai',paid:false,enabled:false}],provider_status:{},tools:[],pending:[],activity:[],notifications:[],roots:[],chat:[],voice:{phase:'idle'},tts:{phase:'idle'},handsfree:{active:false},avatar_settings:{},monitor:{cpu:1,ram_percent:20,disk_percent:20,ram_used:1e9,ram_total:12e9,ram_available:8e9,disk_free:1e11,download:0,upload:0}};
 const personal={profile,routines:[],startup:{available:true,enabled:false},ollama_fallback:false};
 await page.route('https://nexus.test/**',route=>{
  const p=new URL(route.request().url()).pathname;
  if(p==='/api/state')return route.fulfill({json:state});
  if(p==='/api/accounts/status')return route.fulfill({json:{chatgpt:{},claude:{},enabled:{}}});
  if(p==='/api/personal')return route.fulfill({json:personal});
  if(p==='/api/personal/ollama'&&route.request().method()==='GET')return route.fulfill({json:{available:true,models:[{name:'llama3.2:latest'}]}});
  if(p.startsWith('/api/')){
   assert.equal(route.request().headers()['x-nexus-token'],'fixture');const b=route.request().postDataJSON();calls.push({p,b});
   if(p==='/api/personal/settings'){Object.assign(profile,b);return route.fulfill({json:{profile}});}
   if(p==='/api/personal/startup-mode'){personal.startup.enabled=b.enabled;return route.fulfill({json:personal.startup});}
   if(p==='/api/personal/routines'){personal.routines.push({...b,id:1});return route.fulfill({json:{id:1}});}
   if(p==='/api/personal/routines/1'){personal.routines=[];return route.fulfill({json:{deleted:true}});}
   if(p==='/api/personal/briefing')return route.fulfill({json:{text:'Welcome Friend. Study at 19:00.',spoken:true,news:{warnings:[],items:b.news?[{title:'<img src=x onerror=alert(1)> Fixture headline',url:'https://www.dawn.com/news/fixture',source:'Dawn',published:new Date().toISOString()}]:[]}}});
   if(p==='/api/personal/ollama')return route.fulfill({json:b.action==='test'?{verified:true,model:'llama3.2:latest',text:'Local ready',tools_supported:false}:{saved:true}});
   return route.fulfill({json:{saved:true}});
  }
  const file=path.join(root,p==='/'?'static/index.html':p);return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
 });
 try{
  await page.goto('https://nexus.test/');await page.waitForFunction(()=>document.title==='NEXUS');await page.locator('#settings-shortcut').click();
  await page.locator('#personal-name').waitFor();assert.equal(calls.length,0,'Opening settings must not speak, register startup or run inference');
  await page.locator('#personal-name').fill('Friend');await page.locator('#personal-tone').selectOption('calm');await page.getByRole('button',{name:'Save personal settings',exact:true}).click();await page.getByText('Personal settings saved.',{exact:true}).waitFor();assert.equal(profile.preferred_name,'Friend');assert.equal(profile.tone,'calm');
  await page.locator('#personal-login').check();await page.getByRole('button',{name:'Apply Windows startup',exact:true}).click();await page.getByText('Windows sign-in startup enabled.',{exact:true}).waitFor();
  await page.locator('#routine-title').fill('Study');await page.locator('#routine-time').fill('19:00');await page.getByRole('button',{name:'Save routine',exact:true}).click();await page.getByRole('button',{name:'Delete routine',exact:true}).waitFor();assert.equal(personal.routines.length,1);
  await page.getByRole('button',{name:'Show daily briefing',exact:true}).click();await page.locator('#personal-status').getByText(/Study/).waitFor();
  await page.getByRole('button',{name:'Fetch current headlines',exact:true}).click();await page.locator('#personal-news a').waitFor();assert.equal(await page.locator('#personal-news img').count(),0);
  await page.getByRole('button',{name:'Find installed models',exact:true}).click();await page.locator('#personal-ollama-model').selectOption('llama3.2:latest');await page.locator('#personal-ollama-mode').selectOption('local');
  await page.getByRole('button',{name:'Save Ollama mode',exact:true}).click();await page.getByText(/Ollama mode saved/).waitFor();await page.getByRole('button',{name:'Test local reply',exact:true}).click();await page.getByText(/Local chat only; use app commands/).waitFor();
  assert(calls.some(c=>c.p==='/api/personal/ollama'&&c.b.mode==='local'));assert.deepEqual(errors,[]);
  console.log('Personal UI passed: explicit settings, startup opt-in, routines, briefing, inert news titles, installed-model selection and explicit local inference');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
