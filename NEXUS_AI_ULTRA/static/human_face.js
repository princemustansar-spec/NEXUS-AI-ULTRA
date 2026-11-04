'use strict';
// Original procedural portrait: static low-poly meshes, no textures or model downloads.
window.createNexusHumanFace=function(api){
 const {surface,draw,mul,translate,rotateZ,rotateY,scale,eye}=api;
 const sphere=surface((u,v)=>{const a=u*Math.PI,b=v*Math.PI*2,x=Math.sin(a)*Math.sin(b),y=Math.cos(a),z=Math.sin(a)*Math.cos(b);return [x,y,z,x,y,z];},10,16);
 const gaussian=(x,y,cx,cy,sx,sy)=>Math.exp(-((x-cx)**2/sx+(y-cy)**2/sy));
 const point=(u,v)=>{
  const a=u*Math.PI,b=v*Math.PI*2,y=Math.cos(a),s=Math.sin(a),front=Math.max(0,Math.cos(b));
  const x=.63*s*Math.sin(b)*(1-.16*Math.max(0,-y)),py=.89*y;
  let z=.53*s*Math.cos(b);
  z+=front**5*(.025*gaussian(x,py,0,.30,.15,.06)+.045*gaussian(x,py,0,-.59,.09,.025));
  z-=front**6*.025*(gaussian(x,py,-.235,.14,.012,.008)+gaussian(x,py,.235,.14,.012,.008));
  z+=front**8*(.050*gaussian(x,py,0,.09,.004,.025)+.095*gaussian(x,py,0,-.07,.004,.0035));
  z+=front**6*.028*(gaussian(x,py,-.29,-.14,.025,.04)+gaussian(x,py,.29,-.14,.025,.04));
  return [x,py,z];
 };
 const head=surface((u,v)=>{
  const p=point(u,v),a=point(Math.min(.9999,u+.001),v),b=point(u,v+.001),x=a.map((q,i)=>q-p[i]),y=b.map((q,i)=>q-p[i]);
  let n=[x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0]],length=Math.hypot(...n);
  if(length<.0000001){n=[p[0],p[1],p[2]];length=Math.hypot(...n)||1;}
  return [...p,...n.map(q=>q/length)];
 },28,56);
 const hair=surface((u,v)=>{const b=v*Math.PI*2,front=(1+Math.cos(b))/2,a=u*(1.72-.75*front+.11*Math.sin(b)),x=Math.sin(a)*Math.sin(b),y=Math.cos(a),z=Math.sin(a)*Math.cos(b),sweep=Math.sin(u*Math.PI)**2*front**3;return [.665*x,.915*y+.012+sweep*(.045+.025*Math.sin(b)),.57*z+sweep*.025,x,y,z];},18,32);
 const lip=(lower,smile)=>surface((u,v)=>{
  const x=(u*2-1)*.20,b=v*Math.PI*2,edge=(x/.20)**2;
  const y=smile*edge+(lower?-.012*(1-edge):.007*Math.cos(x*30));
  return [x,y+Math.sin(b)*.011,.552+Math.cos(b)*.008,0,Math.sin(b),Math.cos(b)];
 },16,6);
 const lips={neutral:[lip(false,.006),lip(true,.006)],friendly:[lip(false,.025),lip(true,.025)],happy:[lip(false,.050),lip(true,.050)],caring:[lip(false,.006),lip(true,.006)],curious:[lip(false,.010),lip(true,.010)]};
 const brow=surface((u,v)=>{const x=(u*2-1)*.15,b=v*Math.PI*2;return [x,.018*(1-(x/.15)**2)+.012*Math.sin(b),.010*Math.cos(b),0,Math.sin(b),Math.cos(b)];},12,5);
 const halo=surface((u,v)=>{const a=(.13+u*.78)*Math.PI*2,b=v*Math.PI*2,r=1.02+.011*Math.cos(b);return [r*Math.cos(a),r*Math.sin(a),.011*Math.sin(b),Math.cos(b)*Math.cos(a),Math.cos(b)*Math.sin(a),Math.sin(b)];},52,4);
 const skin=[.83,.56,.44],lipColor=[.61,.28,.25],hairColor=[.065,.10,.15];
 return function render({root,t,moving,phase,mood,tint,gaze}){
  const emotion=['idle','speaking','listening'].includes(phase)?mood:'neutral';
  const pose=mul(root,mul(rotateZ(moving?Math.sin(t*.45)*.025:0),scale(1.12,1.12,1.12)));
  const part=(mesh,x,y,z,sx,sy,sz,color,glow=0,angle=0)=>draw(mesh,mul(pose,mul(translate(x,y,z),mul(rotateZ(angle),scale(sx,sy,sz)))),color,glow);
  draw(halo,mul(root,mul(translate(0,.02,-.36),rotateZ(moving?t*.05:0))),tint,.4);
  draw(head,pose,skin,.07);draw(hair,pose,hairColor,.02);
  for(let i=0;i<3;i++)part(brow,-.13+i*.035,.64+i*.052,.425-i*.035,1.28,.35,.25,[.10,.16,.20],.015,-.22);
  for(const side of [-1,1]){
   part(sphere,side*.62,.01,-.01,.075,.16,.08,skin,.03);
   part(sphere,side*.641,.005,.055,.025,.079,.017,[.52,.27,.22]);
   // Slim cyan temple accents give the portrait its NEXUS identity.
   part(eye,side*.545,.245,.25,.014,.10,1,tint,.8,side*.12);
  }
  for(const side of [-1,1]){
   part(sphere,side*.047,-.107,.600,.024,.017,.015,skin,.015);
   part(sphere,side*.036,-.113,.615,.010,.005,.005,[.25,.12,.10]);
  }
  const blink=moving&&(t%5)>4.83?.13:1;
  const squint=emotion==='happy'?.70:emotion==='caring'?.88:emotion==='friendly'?.9:1;
  for(const side of [-1,1]){
   const x=side*.235,y=.155;
   part(sphere,x,y,.475,.138,.052*blink*squint,.034,[.94,.94,.90],.08);
   part(sphere,x+gaze[0]*.020,y+gaze[1]*.013,.511,.036,.039*blink*squint,.009,[.08,.47,.48],.10);
   part(sphere,x+gaze[0]*.020,y+gaze[1]*.013,.521,.018,.025*blink*squint,.005,[.012,.025,.031]);
   if(blink>.5)part(sphere,x-.010+gaze[0]*.020,y+.014,.528,.006,.008,.004,[.95,1,1],.35);
   part(brow,x,.196,.496,.90,.42,.35,[.59,.36,.29],.015);
   const lift=emotion==='curious'&&side===1?.055:emotion==='caring'?.015:emotion==='happy'?.018:0;
   const angle=emotion==='caring'?-side*.14:emotion==='curious'&&side===1?.12:-side*.045;
   part(brow,x,.285+lift,.484,1,1,1,[.11,.075,.065],.015,angle);
  }
  const opening=phase==='speaking'?(moving?.18+.70*Math.abs(Math.sin(t*7.2)*Math.cos(t*3.1)):.35):0;
  part(sphere,0,-.317-opening*.012,.523,.196,.011+opening*.048,.011,[.12,.044,.045]);
  if(opening>.2)part(eye,0,-.303,.540,.18,.019,1,[.89,.89,.83],.05);
  const shape=lips[emotion]||lips.neutral;
  part(shape[0],0,-.310+opening*.012,0,1,1,1,lipColor,.045);
  part(shape[1],0,-.308-opening*.063,0,1,1,1,lipColor,.065);
  part(sphere,0,-.70,.26,.15,.065,.035,skin,.025);
 };
};
