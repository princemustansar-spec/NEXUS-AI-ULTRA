// The browser-speech fallback (static/human_client.js) must pick the same mouth shapes as
// nexus/avatar_audio.py. Both are checked against tests/fixtures/viseme_words.json.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/viseme_words.json'),'utf8'));
const sandbox={crypto:{randomUUID:()=>'fixture'},document:{addEventListener(){}}};sandbox.window=sandbox;
vm.runInNewContext(fs.readFileSync(path.join(root,'static/human_client.js'),'utf8'),sandbox);
const {shapes,cues,OPEN,FALLBACK}=sandbox.NexusHumanShapes;
for(const [word,expected] of Object.entries(fixture.words))assert.deepEqual(Array.from(shapes(word)),expected,'shapes for '+JSON.stringify(word));
const c=fixture.cues;assert.deepEqual(JSON.parse(JSON.stringify(cues(c.position,c.duration,shapes(c.word)))),c.expected,'word cues');
assert.equal(shapes('a'.repeat(5)+'bcdefghijklmnop').length<=12,true,'sequence is bounded');
for(let shape=1;shape<=8;shape++){assert(Array.isArray(FALLBACK[shape])&&FALLBACK[shape].includes(shape),'fallback keeps its own shape first/listed: '+shape);assert(shape in OPEN);}
assert.equal(OPEN[5],0,'pressed lips are closed');
console.log('Viseme parity passed: '+Object.keys(fixture.words).length+' words and word cues match nexus/avatar_audio.py.');
