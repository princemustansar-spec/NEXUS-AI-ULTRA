'use strict';
// Shared, local-only connected portrait renderer. Mouth poses follow playback cues.
window.NexusHumanRenderer = class {
 constructor(canvas,base,sheet,rig,options={}){
  this.canvas=canvas;this.base=base;this.sheet=sheet;this.options=options;this.rig=rig;this.phase='idle';this.emotion='neutral';this.packet={};this.received=0;this.alignment=options.alignment||{x:0,y:0,scale:1};
  this.playing=true;this.start=performance.now();this.last=0;this.look=0;this.frames=0;
  this.w=base.width;this.h=base.height;this.cells=[0,1,2,3].map(i=>({x:i%2*(sheet?sheet.width:2)/2,y:Math.floor(i/2)*(sheet?sheet.height:2)/2,w:(sheet?sheet.width:2)/2,h:(sheet?sheet.height:2)/2}));
  const textureScale=Math.min(1,768/Math.max(this.w,this.h));
  this.surface=document.createElement('canvas');this.surface.width=Math.max(1,Math.round(this.w*textureScale));this.surface.height=Math.max(1,Math.round(this.h*textureScale));this.paint=this.surface.getContext('2d');
  this.gl=canvas.getContext('webgl',{alpha:true,antialias:true,powerPreference:'low-power',preserveDrawingBuffer:false});
  if(this.gl)this.setupMesh();else this.fallback=canvas.getContext('2d');
  this.closedEyes=sheet?rig.eyes.map(([i,src,dest])=>this.patch(i,src,dest)):[];
  this.mouths=sheet?[null,...rig.mouths.map(([i,src,dest])=>this.patch(i,src,dest))]:[null];
  this.openEyes=rig.eyes.map(([,src,dest])=>this.patch(-1,dest,dest));this.textureKey='';
  this.tick=this.tick.bind(this);this.frame=requestAnimationFrame(this.tick);
 }
 patch(index,source,destination){
  const c=index<0?{x:0,y:0,w:this.w,h:this.h}:this.cells[index],[sx,sy,sw,sh]=source,[dx,dy,dw,dh]=destination,layer=document.createElement('canvas');layer.width=Math.round(dw*this.w);layer.height=Math.round(dh*this.h);
  const x=layer.getContext('2d');x.drawImage(index<0?this.base:this.sheet,c.x+sx*c.w,c.y+sy*c.h,sw*c.w,sh*c.h,0,0,layer.width,layer.height);
  // Feather just the boundary; the eyes/lips themselves are generated facial pixels.
  x.globalCompositeOperation='destination-in';
  // Scale the radial mask to an ellipse so the patch has no rectangular seam.
  const maskCanvas=document.createElement('canvas');maskCanvas.width=layer.width;maskCanvas.height=layer.height;const m=maskCanvas.getContext('2d');m.translate(layer.width/2,layer.height/2);m.scale(1,layer.height/layer.width);
  const g=m.createRadialGradient(0,0,layer.width*.24,0,0,layer.width*.50);g.addColorStop(0,'white');g.addColorStop(.55,'white');g.addColorStop(1,'transparent');m.fillStyle=g;m.fillRect(-layer.width/2,-layer.width/2,layer.width,layer.width);x.drawImage(maskCanvas,0,0);
  return {image:layer,x:dx*this.w,y:dy*this.h,w:dw*this.w,h:dh*this.h};
 }
 overlay(p,alpha=1){this.paint.save();this.paint.globalAlpha=alpha;const a=this.alignment,cx=this.w*.5,cy=this.h*.44;this.paint.drawImage(p.image,cx+(p.x-cx)*a.scale+a.x*this.w,cy+(p.y-cy)*a.scale+a.y*this.h,p.w*a.scale,p.h*a.scale);this.paint.restore();}
 setupMesh(){
  const gl=this.gl;
  const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
  const p=gl.createProgram();
  gl.attachShader(p,shader(gl.VERTEX_SHADER,`attribute vec2 aPosition;uniform vec2 uSource;uniform vec2 uView;uniform float uFit;uniform float uRoll;uniform float uNod;uniform float uYaw;uniform float uBreath;uniform vec2 uPivot;uniform vec2 uNeck;uniform float uMood;varying vec2 vUV;
   void main(){
    vUV=aPosition;vec2 point=aPosition*uSource;vec2 pivot=uPivot*uSource;vec2 delta=point-pivot;
    float head=1.-smoothstep(uNeck.x,uNeck.y,aPosition.y);
    float c=cos(uRoll),s=sin(uRoll);vec2 turned=vec2(c*delta.x-s*delta.y,s*delta.x+c*delta.y);
    turned.x+=uYaw*delta.y;turned.y+=uNod*delta.y;
    point+=head*(turned-delta);
    point.y+=(1.-head)*uBreath*(point.y-uSource.y);
    point.x+=(1.-head)*uBreath*.18*(point.x-uSource.x*.5);
    vec2 cheekDelta=(aPosition-vec2(.5,.45))/vec2(.21,.07);float cheek=exp(-dot(cheekDelta,cheekDelta));
    if(uMood==1.)point.y-=cheek*uSource.y*.002;
    vec2 browDelta=(aPosition-vec2(.57,.34))/vec2(.07,.04);
    if(uMood==3.)point.y-=exp(-dot(browDelta,browDelta))*uSource.y*.003;
    vec2 screen=(point-uSource*.5)*uFit*2./uView;gl_Position=vec4(screen.x,-screen.y,0.,1.);
   }`));
  gl.attachShader(p,shader(gl.FRAGMENT_SHADER,`precision mediump float;uniform sampler2D uImage;varying vec2 vUV;void main(){gl_FragColor=texture2D(uImage,vUV);}`));
  gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error('Avatar mesh unavailable');gl.useProgram(p);
  const vertices=[],cols=24,rows=30;
  for(let y=0;y<rows;y++)for(let x=0;x<cols;x++)for(const [dx,dy] of [[0,0],[1,0],[1,1],[0,0],[1,1],[0,1]])vertices.push((x+dx)/cols,(y+dy)/rows);
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);
  const attr=gl.getAttribLocation(p,'aPosition');gl.enableVertexAttribArray(attr);gl.vertexAttribPointer(attr,2,gl.FLOAT,false,0,0);this.count=vertices.length/2;this.buffer=buffer;this.program=p;gl.getAttachedShaders(p).forEach(s=>gl.deleteShader(s));
  this.uniform={};for(const name of ['uSource','uView','uFit','uRoll','uNod','uYaw','uBreath','uPivot','uNeck','uMood'])this.uniform[name]=gl.getUniformLocation(p,name);
  this.texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,this.texture);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,true);gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);gl.clearColor(0,0,0,0);
 }
 setState(packet){this.packet=packet;this.phase=packet.phase||'idle';this.emotion=packet.emotion||'neutral';this.received=performance.now();if((packet.blocked||this.phase!=='speaking'||!packet.animation?.playing)&&Number(this.canvas.dataset.pose)>0)this.draw((this.received-this.start)/1000,this.received);}
 audioAt(now){
  const a=this.packet.animation||{};
  if(!a.playing||this.phase!=='speaking'||now-this.received>600||!Array.isArray(a.cues)||a.cues.length<2)return {pose:0,level:0};
  const position=(a.position_ms||0)+(a.age_ms||0)+now-this.received,cues=a.cues;
  if(position<cues[0][0]||position>=cues[cues.length-1][0])return {pose:0,level:0};
  let i=0;while(i+1<cues.length&&cues[i+1][0]<=position)i++;
  const current=cues[i],next=cues[Math.min(i+1,cues.length-1)],mix=(position-current[0])/Math.max(1,next[0]-current[0]);
  const level=Math.max(0,Math.min(1,current[1]+(next[1]-current[1])*mix));
  return {pose:level>.08?current[2]:0,level};
 }
 draw(seconds,now=performance.now()){
  if(document.hidden||!this.canvas.clientWidth||!this.canvas.clientHeight)return;
  const motion=this.playing&&(!this.options.motion||this.options.motion())&&this.phase!=='emergency';
  const ratio=Math.min(devicePixelRatio||1,1.25),cw=Math.round(this.canvas.clientWidth*ratio),ch=Math.round(this.canvas.clientHeight*ratio);
  if(this.canvas.width!==cw||this.canvas.height!==ch){this.canvas.width=cw;this.canvas.height=ch;this.textureKey='';}
  const fit=Math.min((cw-12*ratio)/this.w,(ch-12*ratio)/this.h),t=motion?seconds:0,ctx=this.paint,audio=motion?this.audioAt(now):{pose:0,level:0};
  const cycle=t%5.1,blink=motion&&cycle>4.68&&cycle<4.92?Math.sin((cycle-4.68)/.24*Math.PI):0;
  const pose=audio.pose>=1&&audio.pose<=3?audio.pose:0;
  const gaze=motion&&this.closedEyes.length&&blink<.05?(this.phase==='thinking'?.65:this.phase==='listening'?this.look*.45:Math.sin(Math.floor(t/4)*1.7)*.2):0;
  const key=[pose,audio.level.toFixed(2),blink.toFixed(2),gaze.toFixed(2),JSON.stringify(this.alignment)].join(':');
  if(key!==this.textureKey){
   ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,this.surface.width,this.surface.height);ctx.setTransform(this.surface.width/this.w,0,0,this.surface.height/this.h,0,0);ctx.drawImage(this.base,0,0);
   if(gaze)for(const p of this.openEyes){ctx.save();ctx.translate(gaze*this.w*.004,this.phase==='thinking'?-this.h*.0015:0);this.overlay(p);ctx.restore();}
   if(blink>.01)for(const eye of this.closedEyes)this.overlay(eye,Math.min(1,blink*1.6));
   if(pose&&this.mouths[pose])this.overlay(this.mouths[pose],Math.min(1,audio.level*2));
   this.textureKey=key;this.textureDirty=true;
  }
  const roll=motion?(this.phase==='thinking'?.016:0)+Math.sin(t*.83)*.020+this.look*.012:0;
  const nod=motion?(this.phase==='speaking'?audio.level*.008:Math.sin(t*.9)*.004):0,breath=motion?Math.sin(t*1.6)*.006:0,yaw=motion?Math.sin(t*.6)*.012:0;
  const staticKey=[key,this.phase,this.emotion,cw,ch].join(':');if(!motion&&this.staticKey===staticKey)return;this.staticKey=motion?'':staticKey;
  if(this.gl){
   const gl=this.gl,u=this.uniform;if(gl.isContextLost())return;gl.viewport(0,0,cw,ch);gl.clear(gl.COLOR_BUFFER_BIT);gl.bindTexture(gl.TEXTURE_2D,this.texture);
   if(this.textureDirty){gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,this.surface);this.textureDirty=false;}
   gl.uniform2f(u.uSource,this.w,this.h);gl.uniform2f(u.uView,cw,ch);gl.uniform1f(u.uFit,fit);gl.uniform1f(u.uRoll,roll);gl.uniform1f(u.uNod,nod);gl.uniform1f(u.uYaw,yaw);gl.uniform1f(u.uBreath,breath);gl.uniform2f(u.uPivot,...this.rig.pivot);gl.uniform2f(u.uNeck,...this.rig.neck);gl.uniform1f(u.uMood,this.emotion==='happy'?1:this.emotion==='curious'?3:0);gl.drawArrays(gl.TRIANGLES,0,this.count);
  }else{
   const x=this.fallback;x.clearRect(0,0,cw,ch);x.save();x.translate(cw/2,ch/2);x.rotate(roll*.4);x.scale(fit,fit*(1+breath*.4));x.drawImage(this.surface,-this.w/2,-this.h/2,this.w,this.h);x.restore();
  }
  this.canvas.dataset.renderer=this.gl?'continuous-mesh':'unified-2d';this.canvas.dataset.phase=this.phase;this.canvas.dataset.pose=String(pose);this.canvas.dataset.blink=blink.toFixed(3);this.canvas.dataset.frames=String(++this.frames);
 }
 tick(now){this.frame=requestAnimationFrame(this.tick);if(now-this.last<1000/(this.phase==='speaking'?24:12))return;this.last=now;this.draw((now-this.start)/1000,now);}
 dispose(){cancelAnimationFrame(this.frame);if(this.gl){this.gl.deleteTexture(this.texture);this.gl.deleteBuffer(this.buffer);this.gl.deleteProgram(this.program);}}
}
