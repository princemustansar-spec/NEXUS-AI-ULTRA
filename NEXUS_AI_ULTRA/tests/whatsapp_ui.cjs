const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));let sends=0;
 const state={name:'NEXUS',token:'fixture',providers:[],provider_status:{},tools:[],pending:[],activity:[],notifications:[],roots:[],chat:[],voice:{phase:'idle'},tts:{phase:'idle'},monitor:{cpu:1,ram_percent:20,disk_percent:20,ram_used:1e9,ram_total:4e9,ram_available:3e9,disk_free:1e11,download:0,upload:0}};
 await page.route('https://nexus.test/**',route=>{
  const p=new URL(route.request().url()).pathname;
  if(p==='/api/state')return route.fulfill({json:state});
  if(p.startsWith('/api/')){
   assert.equal(route.request().headers()['x-nexus-token'],'fixture');const body=route.request().postDataJSON();
   if(p==='/api/tools/whatsapp_open')return route.fulfill({json:{result:{status:'login_required',reason:'Scan QR in NEXUS WhatsApp'}}});
   if(p==='/api/tools/whatsapp_prepare'){assert.equal(body.contact,'Nexus Test Contact');assert.equal(body.message,'Kidhar ho?');return route.fulfill({json:{result:{status:'draft_prepared',draft_id:'fixture-draft',recipient:'Nexus Test Contact',message:'Kidhar ho?',sent:false}}});}
   if(p==='/api/tools/whatsapp_send'){assert.equal(body.draft_id,'fixture-draft');state.pending=[{id:'approval-one',name:'whatsapp_send',args:{draft_id:'fixture-draft',recipient:'Nexus Test Contact',recipient_id:'12025550101@c.us',message:'Kidhar ho?'}}];return route.fulfill({json:{approval_required:true,id:'approval-one',args:state.pending[0].args}});}
   if(p==='/api/approvals/approval-one'){assert(body.approve);sends++;state.pending=[];return route.fulfill({json:{result:{status:'sent_verified',sent:true,delivery_verified:false}}});}
   return route.fulfill({json:{result:{status:'ready'}}});
  }
  const f=path.join(root,p==='/'?'static/index.html':p);return route.fulfill({body:fs.readFileSync(f),contentType:f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html'});
 });
 try{
  await page.goto('https://nexus.test/');await page.waitForFunction(()=>document.title==='NEXUS');await page.locator('#navigation [data-page="WhatsApp Center"]').click();
  await page.getByRole('button',{name:'Open WhatsApp / QR login',exact:true}).click();await page.locator('#whatsapp-output').getByText(/Scan QR/).waitFor();
  await page.locator('#whatsapp-contact').fill('Nexus Test Contact');await page.locator('#whatsapp-message').fill('Kidhar ho?');await page.getByRole('button',{name:'Prepare & review send',exact:true}).click();
  await page.getByRole('button',{name:'Approve this action',exact:true}).waitFor();assert.equal(sends,0);assert((await page.locator('#workspace').innerText()).includes('Nexus Test Contact'));assert((await page.locator('#workspace').innerText()).includes('Kidhar ho?'));
  await page.getByRole('button',{name:'Approve this action',exact:true}).click();await page.locator('#result-content').getByText(/sent_verified/).waitFor();assert.equal(sends,1);assert.deepEqual(errors,[]);
  console.log('WhatsApp Center: QR prompt, exact contact/message review and approval-only send UI passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
