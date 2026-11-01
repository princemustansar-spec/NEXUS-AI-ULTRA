'use strict';
(()=>{
 const $=id=>document.getElementById(id),canvas=$('avatar');
 let token='',dragMode='bridge',autoVoice=false,polling=false,phase='idle',signal=0,pollTimer=0,frame=0,last=0,disposed=false;
 const shell=document.querySelector('.avatar-shell');let controlsTimer=0;
 shell.addEventListener('pointerenter',()=>{clearTimeout(controlsTimer);shell.classList.add('controls-open');});
 shell.addEventListener('pointerleave',()=>{clearTimeout(controlsTimer);controlsTimer=setTimeout(()=>shell.classList.remove('controls-open'),600);});
 const media=matchMedia('(prefers-reduced-motion: reduce)');
 const motion=()=>{const p=localStorage.getItem('core-motion')||'system';return p==='on'||(p!=='off'&&!media.matches);};
 function motionLabel(){$('motion').textContent='Motion: '+(motion()?'On':'Off');$('motion').setAttribute('aria-pressed',String(motion()));}
 $('motion').onclick=()=>{const values=['system','on','off'],p=localStorage.getItem('core-motion')||'system';localStorage.setItem('core-motion',values[(values.indexOf(p)+1)%3]);motionLabel();};
 media.addEventListener('change',motionLabel);addEventListener('storage',motionLabel);motionLabel();
 async function action(name){try{if(!token)return;const r=await fetch('/api/avatar/'+name,{method:'POST',headers:{'X-Nexus-Token':token}});if(!r.ok){const data=await r.json();throw Error(data.detail||'Action unavailable');}}catch(e){$('detail').textContent=e.message;}}
 document.querySelectorAll('.pywebview-drag-region').forEach(region=>region.addEventListener('pointerdown',event=>{if(event.button!==0||dragMode!=='native'||!token)return;event.preventDefault();event.stopImmediatePropagation();action('drag');},true));
 $('mic').onclick=async()=>{try{if(!token)return;const r=await fetch('/api/handsfree/'+(autoVoice?'stop':'start'),{method:'POST',headers:{'Content-Type':'application/json','X-Nexus-Token':token},body:JSON.stringify({consent:true,online_consent:true})});const data=await r.json();if(!r.ok)throw Error(data.detail||'Auto voice unavailable');autoVoice=data.active;poll();}catch(e){$('phase').textContent='VOICE ERROR';$('phase').style.display='block';$('phase').title=e.message;}};
 document.querySelectorAll('button').forEach(button=>button.addEventListener('pointerup',()=>setTimeout(()=>button.blur(),0)));
 $('close').onclick=()=>action('close');$('dashboard').onclick=()=>action('dashboard');
 function status(data){
  token=data.token;dragMode=data.drag_mode||'bridge';const voice=data.voice||{},tts=data.tts||{},hf=data.handsfree||{};autoVoice=!!hf.active;$('mic').dataset.active=String(autoVoice);$('mic').setAttribute('aria-label',autoVoice?'Pause auto voice':'Start auto voice');$('mic').title=autoVoice?'Auto voice ON — capture pauses while speaking; click to pause':'Start auto voice — Google mode sends clips online';
  phase=data.emergency?'emergency':hf.phase==='error'?'error':hf.active?(hf.phase==='approval'?'approval':hf.phase==='speaking'?'speaking':hf.phase==='thinking'?'thinking':voice.phase==='calibrating'?'calibrating':'listening'):voice.phase==='error'?'error':['calibrating','listening'].includes(voice.phase)?voice.phase:voice.phase==='transcribing'||data.thinking?'thinking':tts.phase==='speaking'?'speaking':'idle';
  signal=phase==='listening'&&Number.isFinite(voice.level_dbfs)?Math.max(0,Math.min(1,(voice.level_dbfs+60)/45)):0;
  const labels={idle:'READY',calibrating:'CALIBRATING',listening:'LISTENING',thinking:'THINKING',speaking:'SPEAKING',error:'VOICE ERROR',approval:'APPROVAL',emergency:'STOPPED'};
  $('phase').textContent=labels[phase];$('phase').title=hf.error||'';$('detail').textContent=phase==='listening'?'Input '+Math.round(voice.level_dbfs??-60)+' dBFS':phase==='calibrating'?'Wait quietly, then speak':phase==='thinking'?'Working on your request':phase==='speaking'?'NEXUS reply voice is active':phase==='error'?'Open NEXUS → Voice Assistant':phase==='emergency'?'Resume from Safety Center':'Mic off · use Voice in NEXUS';
  $('level').style.width=(signal*100)+'%';document.documentElement.dataset.phase=phase;
 }
 async function poll(){clearTimeout(pollTimer);if(disposed||polling)return;polling=true;try{const r=await fetch('/api/avatar/status');if(!r.ok)throw Error('NEXUS unavailable');status(await r.json());}catch(e){phase='error';signal=0;$('level').style.width='0%';$('phase').textContent='OFFLINE';$('detail').textContent='Reconnect to NEXUS';}finally{polling=false;if(!disposed)pollTimer=setTimeout(poll,['listening','calibrating','speaking','thinking'].includes(phase)?300:1200);}}
 function fallback(message){$('fallback').hidden=false;canvas.hidden=true;$('fallback').querySelector('p').textContent=message;}
 let gl;try{gl=canvas.getContext('webgl',{alpha:true,antialias:true,powerPreference:'low-power',preserveDrawingBuffer:false});}catch(e){}
 if(!gl){fallback('3D graphics unavailable · status still active');poll();return;}
 function shader(type,text){const s=gl.createShader(type);gl.shaderSource(s,text);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
 try{
  const program=gl.createProgram();
  gl.attachShader(program,shader(gl.VERTEX_SHADER,`attribute vec3 aPosition;attribute vec3 aNormal;uniform mat4 uModel;uniform float uAspect;varying vec3 vNormal;varying vec3 vPosition;void main(){vec3 p=(uModel*vec4(aPosition,1.)).xyz;float d=4.2-p.z;gl_Position=vec4(p.x*2.7/uAspect,p.y*2.7,d*.96-.2,d);vNormal=normalize(mat3(uModel)*aNormal);vPosition=p;}`));
  gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`precision mediump float;varying vec3 vNormal;varying vec3 vPosition;uniform vec3 uColor;uniform float uGlow;void main(){vec3 n=normalize(vNormal);float light=max(0.,dot(n,normalize(vec3(-.5,.8,1.))));float rim=pow(1.-max(0.,dot(n,normalize(vec3(0.,0.,4.2)-vPosition))),2.);float shine=pow(max(0.,dot(reflect(-normalize(vec3(-.5,.8,1.)),n),normalize(vec3(0.,0.,4.2)-vPosition))),24.);vec3 color=uColor*(.2+light*.65+uGlow)+vec3(.05,.6,.8)*rim*.8+vec3(.6,.9,1.)*shine*.5;gl_FragColor=vec4(color,1.);}`));
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('3D program unavailable');gl.useProgram(program);
  const loc={p:gl.getAttribLocation(program,'aPosition'),n:gl.getAttribLocation(program,'aNormal'),model:gl.getUniformLocation(program,'uModel'),color:gl.getUniformLocation(program,'uColor'),glow:gl.getUniformLocation(program,'uGlow'),aspect:gl.getUniformLocation(program,'uAspect')};
  function mesh(vertices){const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);return {buffer:b,count:vertices.length/6};}
  function surface(fn,rows,cols){const vertices=[];for(let i=0;i<rows;i++)for(let j=0;j<cols;j++){const q=[fn(i/rows,j/cols),fn((i+1)/rows,j/cols),fn((i+1)/rows,(j+1)/cols),fn(i/rows,(j+1)/cols)];for(const index of [0,1,2,0,2,3])vertices.push(...q[index]);}return mesh(vertices);}
  const sphere=surface((u,v)=>{const a=u*Math.PI,b=v*Math.PI*2,x=Math.sin(a)*Math.cos(b),y=Math.cos(a),z=Math.sin(a)*Math.sin(b);return [x,y,z,x,y,z];},20,32);
  const ring=surface((u,v)=>{const a=u*Math.PI*2,b=v*Math.PI*2,r=1.16+.026*Math.cos(b);return [r*Math.cos(a),r*Math.sin(a),.026*Math.sin(b),Math.cos(b)*Math.cos(a),Math.cos(b)*Math.sin(a),Math.sin(b)];},80,6);
  const eye=mesh([-.5,-.5,0,0,0,1,.5,-.5,0,0,0,1,.5,.5,0,0,0,1,-.5,-.5,0,0,0,1,.5,.5,0,0,0,1,-.5,.5,0,0,0,1]);
  const identity=()=>[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
  function mul(a,b){const out=Array(16).fill(0);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[c*4+r]+=a[k*4+r]*b[c*4+k];return out;}
  const scale=(x,y,z)=>[x,0,0,0,0,y,0,0,0,0,z,0,0,0,0,1];
  const translate=(x,y,z)=>[1,0,0,0,0,1,0,0,0,0,1,0,x,y,z,1];
  const rotateY=a=>[Math.cos(a),0,-Math.sin(a),0,0,1,0,0,Math.sin(a),0,Math.cos(a),0,0,0,0,1];
  const rotateX=a=>[1,0,0,0,0,Math.cos(a),Math.sin(a),0,0,-Math.sin(a),Math.cos(a),0,0,0,0,1];
  const rotateZ=a=>[Math.cos(a),Math.sin(a),0,0,-Math.sin(a),Math.cos(a),0,0,0,0,1,0,0,0,0,1];
  function draw(mesh,model,color,glow=0){gl.bindBuffer(gl.ARRAY_BUFFER,mesh.buffer);gl.vertexAttribPointer(loc.p,3,gl.FLOAT,false,24,0);gl.vertexAttribPointer(loc.n,3,gl.FLOAT,false,24,12);gl.uniformMatrix4fv(loc.model,false,new Float32Array(model));gl.uniform3fv(loc.color,color);gl.uniform1f(loc.glow,glow);gl.drawArrays(gl.TRIANGLES,0,mesh.count);}
  gl.enableVertexAttribArray(loc.p);gl.enableVertexAttribArray(loc.n);gl.enable(gl.DEPTH_TEST);gl.clearColor(0,0,0,0);
  let frames=0,lastStatic='';
  function render(now){if(disposed||gl.isContextLost())return;frame=requestAnimationFrame(render);const active=['listening','thinking','speaking'].includes(phase),interval=1000/(active?24:15);if(now-last<interval)return;last=now;
   const ratio=Math.min(devicePixelRatio||1,1.5),w=Math.max(1,Math.round(canvas.clientWidth*ratio)),h=Math.max(1,Math.round(canvas.clientHeight*ratio));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}const moving=motion()&&!document.hidden&&phase!=='emergency',staticKey=[phase,signal.toFixed(3),w,h].join(':');if(!moving&&lastStatic===staticKey)return;lastStatic=moving?'':staticKey;gl.viewport(0,0,w,h);gl.uniform1f(loc.aspect,w/h);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
   const t=moving?now*.0018:0,float=moving?Math.sin(t*1.5)*.055:0,pulse=phase==='listening'?signal*.07:phase==='speaking'&&moving?(.5+.5*Math.sin(t*9))*.045:0;
   const root=mul(translate(0,float,0),mul(rotateY(moving?Math.sin(t*.65)*.25:0),scale(1+pulse,1+pulse,1+pulse)));
   const tint=phase==='listening'?[.04,.95,.65]:phase==='thinking'?[.55,.25,.95]:phase==='speaking'?[.15,.8,1]:phase==='approval'?[1,.64,.1]:phase==='error'||phase==='emergency'?[1,.25,.2]:[.02,.65,.95];
   draw(sphere,mul(root,scale(.70,.76,.63)),[.025,.13,.22]);
   for(const x of [-.76,.76])draw(sphere,mul(root,mul(translate(x,0,0),scale(.085,.20,.13))),tint,.25);
   const blink=moving&&(t%5)>4.84?.12:1;
   for(const x of [-.23,.23])draw(eye,mul(root,mul(translate(x,.13,.635),scale(.23,.095*blink,1))),tint,1.2);
   for(const x of [-.13,0,.13])draw(eye,mul(root,mul(translate(x,-.22,.60),scale(.085,.026,1))),tint,.6);
   draw(ring,mul(translate(0,float,0),mul(rotateY(t*.4),rotateX(1.05))),tint,.35);
   draw(ring,mul(translate(0,float,0),mul(rotateZ(-.55+t*.18),rotateY(.72))),[.06,.32,.65],.15);
   canvas.dataset.frames=String(++frames);canvas.dataset.renderer='webgl';
  }
  frame=requestAnimationFrame(render);
  canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();cancelAnimationFrame(frame);fallback('3D paused · graphics context lost');});canvas.addEventListener('webglcontextrestored',()=>location.reload());
 }catch(e){fallback('3D unavailable · status still active');}
 poll();addEventListener('beforeunload',()=>{disposed=true;clearTimeout(pollTimer);clearTimeout(controlsTimer);cancelAnimationFrame(frame);});
})();
