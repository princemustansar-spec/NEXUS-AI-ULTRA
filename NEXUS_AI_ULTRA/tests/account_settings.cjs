const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1366,height:768}}),calls=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
 const state={name:'NEXUS',token:'fixture',providers:[],provider_status:{},tools:[],pending:[],activity:[],notifications:[],roots:[],chat:[],voice:{phase:'idle'},tts:{phase:'idle'},handsfree:{active:false},avatar_settings:{},monitor:{cpu:3,ram_percent:25,disk_percent:20,ram_used:1e9,ram_total:4e9,ram_available:3e9,disk_free:1e11,download:0,upload:0}};
 const status={chatgpt:{connected:false},claude:{connected:false,installed:false},enabled:{}};
 await page.route('https://nexus.test/**',async route=>{
  const p=new URL(route.request().url()).pathname;
  if(p==='/api/state')return route.fulfill({json:state});
  if(p==='/api/accounts/status')return route.fulfill({json:status});
  if(p.startsWith('/api/')){
   assert.equal(route.request().headers()['x-nexus-token'],'fixture');const body=route.request().postDataJSON();calls.push({p,body});
   if(p.endsWith('/login')){assert.equal(body.consent,true);return route.fulfill({json:{pending:true}});}
   if(p.endsWith('/check'))return route.fulfill({json:{connected:true,account:'owner@example.test'}});
   if(p.endsWith('/models'))return route.fulfill({json:{models:[{slug:'account-model',name:'Account model'}]}});
   if(p.endsWith('/test')){assert.equal(body.consent,true);return route.fulfill({json:{verified:true,text:'Connection works'}});}
   if(p.endsWith('/enable')){assert.equal(body.consent,true);return route.fulfill({json:{enabled:true}});}
   return route.fulfill({json:{ok:true}});
  }
  const f=path.join(root,p==='/'?'static/index.html':p);return route.fulfill({body:fs.readFileSync(f),contentType:f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html'});
 });
 try{
  await page.goto('https://nexus.test/');await page.waitForFunction(()=>document.title==='NEXUS');await page.locator('#navigation [data-page="Settings"]').click();
  const cg=page.locator('[data-account="chatgpt"]'),cl=page.locator('[data-account="claude"]');
  await cg.waitFor();assert.equal(calls.length,0,'Displaying settings must not launch login or spend plan credits');
  await cg.getByRole('button',{name:'Continue with ChatGPT',exact:true}).click();
  await cg.getByRole('button',{name:'Check connection',exact:true}).click();await cg.getByText('Signed in · owner@example.test',{exact:true}).waitFor();
  await cg.getByRole('button',{name:'Load account models',exact:true}).click();await cg.getByRole('combobox').selectOption('account-model');
  await cg.getByRole('button',{name:'Save account model',exact:true}).click();
  await cg.getByRole('button',{name:'Test response (uses plan credits)',exact:true}).click();
  await cg.getByRole('button',{name:'Use for chat and voice',exact:true}).click();
  await cl.getByRole('button',{name:'Open official Claude login',exact:true}).click();
  await cl.getByRole('button',{name:'Check connection',exact:true}).click();
  await cl.getByRole('button',{name:'Test response (uses plan credits)',exact:true}).click();
  await cl.getByRole('button',{name:'Use for chat and voice',exact:true}).click();
  assert(calls.some(c=>c.p==='/api/accounts/chatgpt/model'&&c.body.model==='account-model'));
  assert.deepEqual(errors,[]);console.log('Account settings: no automatic login/spend; ChatGPT login/models/test/enable and official Claude login/test/enable passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
