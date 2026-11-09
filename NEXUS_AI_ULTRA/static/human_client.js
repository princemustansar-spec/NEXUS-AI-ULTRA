'use strict';
(()=>{
 // Mouth shape tables. Keep identical to nexus/avatar_audio.py (tests/fixtures/viseme_words.json checks both).
 // 0 rest · 1 parted · 2 round · 3 wide open · 4 wide smile · 5 lips pressed · 6 teeth on lip · 7 pursed · 8 mid open
 const OPEN={0:0,1:.35,2:.6,3:.9,4:.5,5:0,6:.3,7:.45,8:.65},LONG=new Set([2,3,4,8]);
 const LETTER={a:3,e:4,i:4,o:2,u:2,y:4,w:2,m:5,b:5,p:5,f:6,v:6,r:7,j:7,h:8,k:8,g:8,q:8,c:1,s:1,z:1,t:1,d:1,n:1,l:1,x:1};
 const PAIR={sh:7,ch:7,th:1,ph:6,oo:2,ou:2,ow:2,ee:4,ea:4,ie:4,ai:3,ay:3};
 // When a pack has no frame for a shape, the renderer uses the first listed shape it does have (none = lips rest).
 const FALLBACK={1:[1],2:[2,7,1],3:[3,8,2],4:[4,1,3],5:[5],6:[6,1],7:[7,2,1],8:[8,3,2]};
 function shapes(word,limit=12){
  const text=String(word).toLowerCase().replace(/[^a-z]/g,''),out=[];
  for(let i=0;i<text.length&&out.length<limit;){
   let shape=PAIR[text.slice(i,i+2)],step=2;if(shape===undefined){shape=LETTER[text[i]]??1;step=1;}
   if(!out.length||out[out.length-1]!==shape)out.push(shape);i+=step;
  }
  return out.length?out:[1];
 }
 function cues(position,duration,list){
  const weights=list.map(s=>LONG.has(s)?1.5:1),total=weights.reduce((a,b)=>a+b,0),out=[];let at=position;
  list.forEach((shape,i)=>{out.push([Math.round(at),OPEN[shape],shape]);at+=duration*weights[i]/total;});
  out.push([Math.round(position+duration),0,0]);return out;
 }
 window.NexusHumanShapes={OPEN,FALLBACK,shapes,cues};
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('nexus-human-playback'):null;
 const clients=new Set();let browserJob=null;
 function deliver(value){for(const client of clients)client.browserEvent(value);}
 function publish(value){deliver(value);channel?.postMessage(value);}
 if(channel)channel.onmessage=e=>deliver(e.data);
 window.NexusHumanSpeech={
  start(){const id=crypto.randomUUID();browserJob={id,start:Date.now()};publish({action:'start',id,sent:Date.now()});return id;},
  word(id,text){if(!browserJob||id!==browserJob.id)return;const at=Date.now()-browserJob.start,word=String(text);publish({action:'word',id,sent:Date.now(),position:at,cues:cues(at,Math.max(80,Math.min(420,word.length*45)),shapes(word))});},
  end(id){publish({action:'end',id,sent:Date.now()});if(browserJob?.id===id)browserJob=null;},
  stop(){if(browserJob)this.end(browserJob.id);}
 };
 window.attachNexusHumanVoice=(utterance,text)=>{
  let id=null;
  utterance.addEventListener('start',()=>{id=window.NexusHumanSpeech.start();});
  utterance.addEventListener('boundary',event=>{if(event.name==='word')window.NexusHumanSpeech.word(id,text.slice(event.charIndex,event.charIndex+(event.charLength||1)));});
  for(const event of ['end','error'])utterance.addEventListener(event,()=>window.NexusHumanSpeech.end(id));
 };
 window.NexusHumanClient=class {
  constructor(canvas,options={}){this.canvas=canvas;this.options=options;this.config=null;this.renderer=null;this.generation=0;this.stream=null;this.browser=null;this.native={};this.disposed=false;clients.add(this);this.visibility=()=>{if(document.hidden)this.disconnect();else if(this.renderer)this.connect();};document.addEventListener('visibilitychange',this.visibility);}
  async configure(config){
   const key=JSON.stringify(config||{});if(key===this.key)return;this.key=key;this.config=config;const generation=++this.generation;
   if(!config?.enabled){this.release();return;}
   if(this.renderer&&config.revision===this.revision){this.renderer.alignment=config.alignment;return;}
   this.release();
   const load=src=>new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=reject;image.src=src;});
   try{
    const [base,sheet]=await Promise.all([load(config.photo),config.expressions?load(config.expressions):null]);
    if(generation!==this.generation||this.disposed)return;
    this.renderer=new NexusHumanRenderer(this.canvas,base,sheet,config.rig,{motion:this.options.motion,alignment:config.alignment});this.revision=config.revision;this.canvas.hidden=false;this.options.onActive?.(true);this.connect();
    this.canvas.title=sheet?'Human avatar · playback synchronization follows the selected voice.':'Photo only · add a matching expression pack for eyelids and speaking mouth shapes.';
   }catch(e){if(generation===this.generation){this.canvas.dataset.error=e.message||'Portrait image failed to load';this.release();this.options.onError?.('Portrait unavailable; AI Core remains available.');}}
  }
  connect(){
   if(this.stream||!this.renderer||(document.hidden)||this.disposed)return;
   this.stream=new EventSource('/api/human-avatar/events');
   this.stream.onmessage=event=>{try{const value=JSON.parse(event.data);this.native=value;if(!value.enabled){this.release();this.key='';this.options.onDisabled?.();return;}this.apply();}catch{this.renderer?.setState({phase:'idle',animation:{playing:false}});}};
   this.stream.onerror=()=>{this.browser=null;this.renderer?.setState({phase:'idle',animation:{playing:false}});};
  }
  apply(){
   if(!this.renderer)return;let value=this.native;
   if(this.browser&&Date.now()-this.browser.sent<1200&&!value.blocked&&!value.animation?.playing)value={...value,phase:'speaking',job_id:this.browser.id,animation:{playing:true,mode:'word-boundary',position_ms:this.browser.position||0,age_ms:Date.now()-this.browser.sent,cues:this.browser.cues||[]}};
   this.renderer.setState(value);
   if(this.config?.frames){const mode=value.animation?.mode;this.canvas.title=value.phase==='speaking'?(mode==='viseme'?'Speech sync: voice mouth cues':mode==='audio-envelope'?'Speech sync: audio timing, approximate mouth shapes':'Limited speech sync with this voice'):'Human Avatar';}
  }
  browserEvent(value){
   if(!value||typeof value.id!=='string'||!['start','word','end'].includes(value.action)||!Number.isFinite(value.sent)||Math.abs(Date.now()-value.sent)>1500)return;
   if(value.action==='start')this.browser=value;
   else if(this.browser?.id===value.id){if(value.action==='end')this.browser=null;else if(Array.isArray(value.cues)&&value.cues.length>=2&&value.cues.length<=16&&value.cues.every(c=>Array.isArray(c)&&c.length===3&&c.every(Number.isFinite)))this.browser=value;}
   this.apply();
  }
  disconnect(){this.stream?.close();this.stream=null;this.renderer?.setState({phase:'idle',animation:{playing:false}});}
  release(){this.disconnect();this.renderer?.dispose();this.renderer=null;this.revision='';this.canvas.hidden=true;this.options.onActive?.(false);}
  dispose(){this.disposed=true;this.generation++;this.release();clients.delete(this);document.removeEventListener('visibilitychange',this.visibility);}
 };
})();
