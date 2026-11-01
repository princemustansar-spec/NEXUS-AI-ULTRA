// Execute the production controller scripts against a local media fixture.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../nexus/youtube.py'),'utf8');
const script=name=>{const match=source.match(new RegExp(name+' = """([\\s\\S]*?)"""'));assert(match,name);return match[1];};
const rate=8000,frames=rate*3,wav=Buffer.alloc(44+frames*2);
wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(rate,24);wav.writeUInt32LE(rate*2,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(frames*2,40);
for(let i=0;i<frames;i++)wav.writeInt16LE(Math.round(Math.sin(i*2*Math.PI*220/rate)*500),44+i*2);
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox','--autoplay-policy=no-user-gesture-required']});
 const page=await browser.newPage();let requests=0;
 await page.route('https://www.youtube.com/**',route=>{
  requests++;const url=new URL(route.request().url());
  const body=url.pathname==='/results'?'<ytd-video-renderer><a id="video-title" href="/watch?v=one">Fixture one</a></ytd-video-renderer>':`<h1><yt-formatted-string>Fixture ${url.searchParams.get('v')}</yt-formatted-string></h1><video loop src="data:audio/wav;base64,${wav.toString('base64')}"></video><a class="ytp-next-button" href="/watch?v=two">Next</a>`;
  return route.fulfill({body,contentType:'text/html'});
 });
 try{
  await page.goto('https://www.youtube.com/results?search_query=fixture');
  assert(await page.evaluate(script('FIRST_JS')));
  await page.waitForURL('**/watch?v=one');
  await page.waitForFunction(()=>document.querySelector('video').readyState>=2);
  assert(await page.evaluate(script('PLAY_JS')));
  await page.waitForTimeout(200);
  const first=await page.evaluate(script('STATE_JS'));
  assert(!first.paused&&first.time>0&&first.ready>=2);
  assert(await page.evaluate(script('PAUSE_JS')));
  assert((await page.evaluate(script('STATE_JS'))).paused);
  await page.evaluate(script('PLAY_JS'));await page.waitForTimeout(100);
  assert(!(await page.evaluate(script('STATE_JS'))).paused);
  assert(await page.evaluate(script('NEXT_JS')));
  await page.waitForURL('**/watch?v=two');
  await page.waitForFunction(()=>document.querySelector('video').readyState>=2);
  await page.evaluate(script('PLAY_JS'));await page.waitForTimeout(200);
  const next=await page.evaluate(script('STATE_JS'));
  assert(next.url.endsWith('v=two')&&!next.paused&&next.time>0);
  assert(requests>=3);console.log('Production DOM scripts: select search result, observed playback time, pause, resume, next video: passed (local fixture, not live YouTube)');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
