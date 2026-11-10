// Extended expression packs (3x3 sheet, 8 mouth shapes), old 3-frame packs, and smooth jaw motion.
// Synthetic portraits only. Set AVATAR_SHOT_DIR to also save screenshots for a visual check.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),shots=process.env.AVATAR_SHOT_DIR;
const mouth=[[.35,.475,.30,.157],[.369,.487,.247,.133]];
const eyes=[[0,[.35,.335,.16,.115],[.352,.333,.122,.093]],[0,[.51,.335,.16,.115],[.500,.340,.122,.093]]];
const legacyRig={eyes,mouths:[1,2,3].map(i=>[i,...mouth]),pivot:[.493,.685],neck:[.53,.79]};
const fullRig={eyes,mouths:[1,2,3,4,5,6,7,8].map(i=>[i,...mouth]),shapes:[1,2,3,4,5,6,7,8],grid:[3,3],pivot:[.493,.685],neck:[.53,.79]};
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext(),helper=await context.newPage();
  const assets=await helper.evaluate(()=>{
   function image(cells,cols){const c=document.createElement('canvas');const size=cells?320*cols:320;c.width=size;c.height=cells?320*cols:292;const x=c.getContext('2d');
    for(let i=0;i<(cells||1);i++){x.save();x.translate(cells?(i%cols)*320:0,cells?Math.floor(i/cols)*320:0);x.fillStyle='#d9aa91';x.beginPath();x.ellipse(158,98,80,90,0,0,7);x.fill();x.fillRect(130,170,55,40);x.fillStyle='#718f91';x.fillRect(70,205,180,80);
     x.fillStyle='#453d38';if(i===0&&cells){x.fillRect(120,113,25,2);x.fillRect(175,113,25,2);}else{x.fillRect(125,110,12,10);x.fillRect(180,110,12,10);}
     x.fillStyle='hsl('+(i*37)%360+',45%,38%)';x.beginPath();x.ellipse(158,155,10+i*3,2+(i%4)*4,0,0,7);x.fill();x.restore();}
    return c.toDataURL().split(',')[1];}
   return {base:image(0,0),sheet2:image(4,2),sheet3:image(9,3)};
  });await helper.close();
  async function open(rig,sheet,photoOnly=false){
   const profile={present:true,enabled:true,frames:!photoOnly,revision:'fixture',photo:'/api/human-avatar/assets/portrait.png?v=fixture',expressions:photoOnly?'':'/api/human-avatar/assets/expressions.png?v=fixture',rig,alignment:{x:0,y:0,scale:1}};
   const page=await context.newPage({viewport:{width:280,height:290}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(()=>{window.__sources=[];window.EventSource=class{constructor(){window.__sources.push(this);}close(){this.closed=true;}};});
   await page.route('https://nexus.test/**',route=>{const p=new URL(route.request().url()).pathname;
    if(p==='/api/avatar/status')return route.fulfill({json:{token:'fixture',drag_mode:'native',voice:{phase:'idle'},tts:{phase:'idle'},handsfree:{active:false},human_avatar:profile}});
    if(p.includes('/api/human-avatar/assets/'))return route.fulfill({body:Buffer.from(p.includes('portrait')?assets.base:sheet,'base64'),contentType:'image/png'});
    if(p.startsWith('/api/'))return route.fulfill({json:{}});
    const f=path.join(root,p);return route.fulfill({body:fs.readFileSync(f),contentType:f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html'});});
   await page.goto('https://nexus.test/static/avatar.html');await page.waitForFunction(()=>Number(document.querySelector('#human-floating')?.dataset.frames)>1);
   await page.evaluate(()=>localStorage.setItem('core-motion','on'));
   const emit=value=>page.evaluate(value=>{for(const s of window.__sources.filter(s=>!s.closed))s.onmessage?.({data:JSON.stringify(value)});},value);
   const idle={enabled:true,blocked:false,phase:'idle',emotion:'neutral',job_id:'j',animation:{playing:false}};
   const speak=shape=>emit({...idle,phase:'speaking',animation:{playing:true,mode:'audio-envelope',position_ms:100,age_ms:0,cues:[[100,.9,shape],[520,.9,shape],[580,0,0]]}});
   return {page,errors,emit,idle,speak,face:page.locator('#human-floating')};
  }
  const slotOf=async(h,shape)=>{await h.speak(shape);await h.page.waitForFunction(s=>document.querySelector('#human-floating').dataset.pose===String(s),shape);await h.page.waitForTimeout(160);return h.face.getAttribute('data-slot');};

  // 1. A 3x3 pack with eight mouth patches uses a different patch for every shape.
  let h=await open(fullRig,assets.sheet3);
  for(let shape=1;shape<=8;shape++)assert.equal(await slotOf(h,shape),String(shape),'8-frame pack: shape '+shape+' uses its own patch');
  // 2. Jaw follows the opening and settles smoothly back to rest.
  await h.speak(3);await h.page.waitForFunction(()=>Number(document.querySelector('#human-floating').dataset.jaw)>.12);
  const openShot=await h.face.screenshot();if(shots){fs.mkdirSync(shots,{recursive:true});fs.writeFileSync(path.join(shots,'speaking-open.png'),openShot);}
  await h.emit(h.idle);await h.page.waitForFunction(()=>Number(document.querySelector('#human-floating').dataset.jaw)<.02);
  await h.page.waitForTimeout(250);const restShot=await h.face.screenshot();if(shots)fs.writeFileSync(path.join(shots,'resting.png'),restShot);
  assert(!openShot.equals(restShot),'Open mouth and jaw must look different from rest');assert(restShot.length>1500);
  // 3. Mouth blends instead of snapping: for a few frames both the old and the new patch are partly visible.
  await h.speak(3);await h.page.waitForFunction(()=>document.querySelector('#human-floating').dataset.slot==='3');await h.page.waitForTimeout(160);
  const samples=await h.page.evaluate(()=>new Promise(resolve=>{const out=[],face=document.querySelector('#human-floating'),stop=performance.now()+420;
   window.__sources.filter(s=>!s.closed).forEach(s=>s.onmessage({data:JSON.stringify({enabled:true,blocked:false,phase:'speaking',emotion:'neutral',job_id:'j',animation:{playing:true,mode:'audio-envelope',position_ms:100,age_ms:0,cues:[[100,.9,2],[520,.9,2],[580,0,0]]}})}));
   (function sample(){out.push(face.dataset.mix.split(',').map(Number));if(performance.now()<stop)requestAnimationFrame(sample);else resolve(out);})();}));
  assert(samples.some(m=>m[3]>.05&&m[2]>.05),'Old and new mouth patches overlap while one shape fades into the next');
  assert(samples.at(-1)[2]>.8&&samples.at(-1)[3]<.02,'The new shape ends fully in, the old one fully out');
  // 4. Mute closes the mouth at once, with no fade.
  await h.speak(3);await h.page.waitForFunction(()=>document.querySelector('#human-floating').dataset.pose==='3');
  await h.emit({...h.idle,blocked:true});await h.page.waitForFunction(()=>document.querySelector('#human-floating').dataset.pose==='0'&&Number(document.querySelector('#human-floating').dataset.jaw)===0);
  assert.deepEqual(h.errors,[]);await h.page.close();

  // 5. An original 2x2 pack with three patches still works; missing shapes use the nearest patch.
  h=await open(legacyRig,assets.sheet2);
  const expected={1:'1',2:'2',3:'3',4:'1',5:'0',6:'1',7:'2',8:'3'};
  for(const [shape,slot] of Object.entries(expected))assert.equal(await slotOf(h,Number(shape)),slot,'3-frame pack: shape '+shape);
  assert.deepEqual(h.errors,[]);await h.page.close();

  // 6. Photo only (no expression sheet): no mouth patch exists, but the jaw still follows the voice.
  h=await open(legacyRig,assets.sheet2,true);
  await h.speak(3);await h.page.waitForFunction(()=>Number(document.querySelector('#human-floating').dataset.jaw)>.12);
  assert.equal(await h.face.getAttribute('data-slot'),'0');assert.deepEqual(h.errors,[]);await h.page.close();
  console.log('Extended avatar frames passed: 8 mouth shapes on a 3x3 sheet, nearest-frame fallback for original packs, blended shape changes, jaw motion and instant mute.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
