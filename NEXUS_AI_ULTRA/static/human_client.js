'use strict';
(()=>{
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('nexus-human-playback'):null;
 const clients=new Set();let browserJob=null;
 function deliver(value){for(const client of clients)client.browserEvent(value);}
 function publish(value){deliver(value);channel?.postMessage(value);}
 if(channel)channel.onmessage=e=>deliver(e.data);
 window.NexusHumanSpeech={
  start(){const id=crypto.randomUUID();browserJob={id,start:Date.now()};publish({action:'start',id,sent:Date.now()});return id;},
  word(id,text){if(!browserJob||id!==browserJob.id)return;const at=Date.now()-browserJob.start,word=String(text).toLowerCase(),pose=/[ou]/.test(word)?2:/a/.test(word)?3:1;publish({action:'word',id,sent:Date.now(),position:at,cues:[[at,.7,pose],[at+Math.max(80,Math.min(300,word.length*40)),0,0]]});},
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
   else if(this.browser?.id===value.id){if(value.action==='end')this.browser=null;else if(Array.isArray(value.cues)&&value.cues.length===2)this.browser=value;}
   this.apply();
  }
  disconnect(){this.stream?.close();this.stream=null;this.renderer?.setState({phase:'idle',animation:{playing:false}});}
  release(){this.disconnect();this.renderer?.dispose();this.renderer=null;this.revision='';this.canvas.hidden=true;this.options.onActive?.(false);}
  dispose(){this.disposed=true;this.generation++;this.release();clients.delete(this);document.removeEventListener('visibilitychange',this.visibility);}
 };
 const scene=document.querySelector('.core-scene');
 if(scene){
  const canvas=document.createElement('canvas');canvas.id='human-core';canvas.hidden=true;canvas.setAttribute('aria-label','Human NEXUS avatar');scene.append(canvas);
  const motion=()=>{const p=localStorage.getItem('core-motion')||'system';return p==='on'||p!=='off'&&!matchMedia('(prefers-reduced-motion: reduce)').matches;};
  const client=new NexusHumanClient(canvas,{motion,onActive:on=>scene.classList.toggle('human-avatar-mode',on)});
  window.syncNexusHuman=config=>client.configure(config);
  canvas.addEventListener('pointermove',e=>{if(client.renderer)client.renderer.look=Math.max(-1,Math.min(1,e.offsetX/canvas.clientWidth*2-1));});canvas.addEventListener('pointerleave',()=>{if(client.renderer)client.renderer.look=0;});
  addEventListener('beforeunload',()=>client.dispose());
 }
})();
