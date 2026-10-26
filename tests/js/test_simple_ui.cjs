const assets=require('node:path').resolve(__dirname,'../../scripts/diagnostics/display_review_assets');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const frames=ci=>['a','m','z'].map((id,i)=>({id:id+ci,uri:'file:///synthetic/'+id+ci+'.png',tick:i}));
const cases=[0,1].map(i=>({id:'c'+i,frames:frames(i),views:[{id:'native',all_native_images:true,frame_ids:['a'+i,'m'+i,'z'+i]}]}));
const data={packet:{cases},template:{internal_End_tick:null,formal_events:[],cases:cases.map(c=>({id:c.id,points:[],boundaries:[],scopes:[],interval_claims:[]}))}};
class Element{constructor(id){this.id=id;this.hidden=false;this.value='';this.checked=false;this.disabled=false;this.children=[];this.className='';this.textContent='';}decode(){return Promise.resolve();}replaceChildren(){this.children=[];}append(x){this.children.push(x);}click(){this.onclick?.();}showModal(){}close(){}}
const names=['data','image0','image1','extra','player','progress','review','summary','back','summaryText','title','help','numbers','choices','loading','full','noAppearance','noScore','cut','save','saved','dialog','original','close','play','stop','playerImage','playerIndex'];
const el=Object.fromEntries(names.map(n=>[n,new Element(n)]));el.data.textContent=JSON.stringify(data);
const digits=Array.from({length:4},()=>new Element('digit'));
const doc={getElementById:id=>{assert(el[id],'missing element '+id);return el[id];},querySelectorAll:s=>s==='.digit'?digits:s==='.needs-ready'?[...digits,...el.choices.children.filter(x=>x.className==='needs-ready')]:[],createElement:()=>new Element('new')};
let exported;
const box={document:doc,structuredClone,Date,Promise,Set,setTimeout,console,Blob:class{constructor(parts){exported=JSON.parse(parts[0]);}},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}}};vm.createContext(box);
const code=['frame_gate.js','simple_model.js','simple_ui.js'].map(f=>fs.readFileSync(assets+'/'+f,'utf8')).join('\n');vm.runInContext(code,box);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 assert.equal(el.choices.children[0].disabled,true,'answers disabled during original-image decode');
 el.choices.children[0].click();assert.equal(el.progress.textContent,'1 / 3','early click cannot create an answer');
 await flush();assert.equal(el.choices.children[0].disabled,false);
 el.choices.children[0].click();await flush();assert.equal(el.progress.textContent,'2 / 3');
 ['1','2','1','3'].forEach((v,i)=>digits[i].value=v);el.choices.children[0].click();await flush();assert.equal(el.progress.textContent,'3 / 3');
 el.choices.children[0].click();assert.equal(el.progress.textContent,'確認終了');
 el.save.click();assert(exported,'download generated');
 assert.equal(exported.cases[0].boundaries.length,2);assert.equal(exported.cases[1].boundaries.length,1);
 assert(exported.cases.every(c=>!c.scopes[0].full_interval_reviewed));
 assert(exported.cases.every(c=>c.interval_claims.every(x=>x.occurred==='UNKNOWN')));
 assert.equal(exported.ui_protocol,'simple_pair_review_v2_wait_decode');
 assert.equal(exported.internal_End_tick,null);assert.equal(exported.formal_events.length,0);
 console.log('mocked-DOM wizard/decode/wire-format checks passed; no browser rendering claim');
})().catch(e=>{console.error(e);process.exitCode=1;});
