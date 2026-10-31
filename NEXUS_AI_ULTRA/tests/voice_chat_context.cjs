// Exercise the real capture-completion and submit handlers without hardware.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('static/app.js','utf8');
const elements=new Map();
const $=selector=>{if(!elements.has(selector))elements.set(selector,{value:'',checked:false,focus(){},addEventListener(event,fn){this[event]=fn;}});return elements.get(selector);};
const sent=[];
let failChat=false;
const context=vm.createContext({$,console,chatInputSource:'text',voiceJob:{id:'capture-1',operation:'capture'},listening:false,busy:false,page:'AI Chat',state:{},localStorage:{getItem(){return 'no';}},
 api:async(route,payload)=>{if(route==='voice/status')return {job_id:'capture-1',phase:'done',result:{text:'Meri awaaz aa rahi hai?'}};if(route==='chat'){sent.push(payload);if(failChat)throw Error('offline');return {text:'Ji'};}throw Error(route);},
 refresh:async()=>{},navigate(){},toast(){},setCore(){},renderVoiceStatus(){},error(){},speak(){},setTimeout(){},voiceDevices:[]});
vm.runInContext(source.slice(source.indexOf('async function pollVoice(){'),source.indexOf('async function cancelVoice(){')),context);
vm.runInContext(source.slice(source.indexOf("$('#chat-input').addEventListener('input'"),source.indexOf('function clock(){')),context);
(async()=>{
 await context.pollVoice();
 assert.equal(sent.length,0,'capture must wait for user review and Send');
 assert.equal($('#chat-input').value,'Meri awaaz aa rahi hai?');
 failChat=true;
 await $('#chat-form').onsubmit({preventDefault(){}});
 assert.equal(sent[0].input_source,'voice');
 assert.equal($('#chat-input').value,'Meri awaaz aa rahi hai?','failed send keeps transcript');
 failChat=false;
 await $('#chat-form').onsubmit({preventDefault(){}});
 assert.equal(sent[1].input_source,'voice','retry retains source');
 assert.equal(sent[1].allow_paid,false);
 $('#chat-input').value='Typed follow-up';
 await $('#chat-form').onsubmit({preventDefault(){}});
 assert.equal(sent[2].input_source,'text','next typed turn must not inherit voice');
 context.voiceJob={id:'capture-1',operation:'capture'};
 await context.pollVoice();
 $('#chat-input').value='';$('#chat-input').input();
 $('#chat-input').value='Replacement typed message';
 await $('#chat-form').onsubmit({preventDefault(){}});
 assert.equal(sent[3].input_source,'text','clearing a transcript resets its source');
 console.log('Voice capture → reviewed Send → retry → typed follow-up: passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
