const D=JSON.parse(document.getElementById('data').textContent);
const answers=emptySimpleAnswers(), chronology=[], reviewState={};
const cases=D.packet.cases, nativeViews=cases.map(c=>c.views.find(v=>v.all_native_images));
for(const c of cases) reviewState[c.id]={decodedFrames:new Set(),attestedFull:false,explicitNoAppearance:false,explicitNoScoreChange:false,cutSuspected:false};
let step=0, sequence=0, pairStates=[], playing=0;
const byId=Object.fromEntries(cases.map(c=>[c.id,Object.fromEntries(c.frames.map(f=>[f.id,f]))]));
function log(action,caseId=null,frameId=null,extra={}){chronology.push({at_UTC:new Date().toISOString(),action,case_id:caseId,frame_id:frameId,...extra});}
function activeIndex(){return step===2?1:0;}
function currentPair(){const ci=activeIndex(),v=nativeViews[ci];return [byId[cases[ci].id][v.frame_ids[0]],byId[cases[ci].id][v.frame_ids.at(-1)]];}
function pairReady(){const f=currentPair();return pairStates.length===2&&f.every((x,i)=>canRecordFrame(pairStates[i],x.id));}
function showNumbers(){const inputs=[...document.querySelectorAll('.digit')];for(let i=0;i<4;i++)inputs[i].value=([...answers.beforeScore,...answers.afterScore][i]??'');}
function readNumbers(){const x=[...document.querySelectorAll('.digit')].map(el=>el.value===''?null:Number(el.value));if(x.some(v=>v!==null&&(!Number.isInteger(v)||v<0||v>99)))throw Error('見えた数字を入力してください。読めない欄は空欄で構いません。');answers.beforeScore=x.slice(0,2);answers.afterScore=x.slice(2);}
function saveViewChecks(){if(step>2)return;const id=cases[activeIndex()].id,s=reviewState[id];s.attestedFull=document.getElementById('full').checked;s.explicitNoAppearance=document.getElementById('noAppearance').checked;s.explicitNoScoreChange=document.getElementById('noScore').checked;s.cutSuspected=document.getElementById('cut').checked;}
function setReady(enabled){for(const el of document.querySelectorAll('.needs-ready'))el.disabled=!enabled;}
async function showPair(){
 const token=++sequence,ci=activeIndex(),c=cases[ci],frames=currentPair();setReady(false);document.getElementById('loading').textContent='画像を読み込み中…';
 pairStates=frames.map(()=>({displaySequence:token,loadedFrameId:null,decodedFrames:reviewState[c.id].decodedFrames}));
 const states=pairStates;
 const good=await Promise.all(frames.map(async(f,i)=>{const img=document.getElementById('image'+i);img.src=f.uri;const ok=await decodeFrameReady(states[i],f.id,[img],token);if(ok)log('frame_decoded_not_attention_proof',c.id,f.id,{view_id:nativeViews[ci].id});return ok;}));
 if(token!==sequence)return;
 const ready=good.every(Boolean)&&pairReady();setReady(ready);document.getElementById('loading').textContent=ready?'画像を確認して、分かる回答を選んでください。':'画像を読み込めませんでした。「分からない」で進めます。';updateFullGate();
}
function updateFullGate(){const ci=activeIndex(),s=reviewState[cases[ci].id],eligible=canAttestFullNative(s,nativeViews[ci]);document.getElementById('full').disabled=!eligible;if(!eligible)document.getElementById('full').checked=false;}
function render(){
 playing++;sequence++;document.getElementById('extra').open=false;document.getElementById('player').hidden=true;
 const summary=step===3;document.getElementById('review').hidden=summary;document.getElementById('summary').hidden=!summary;
 document.getElementById('back').hidden=step===0;document.getElementById('back').disabled=false;
 document.getElementById('progress').textContent=summary?'確認終了':`${step+1} / 3`;
 if(summary){document.getElementById('summaryText').textContent=`終了文字：${{NEW:'新しく出た',BOTH:'両方にある',NEITHER:'どちらにもない',UNKNOWN:'分からない'}[answers.appearance]}\nScore：${{CHANGED:'変わった',SAME:'同じだった',UNKNOWN:'分からない'}[answers.score]}\n終了文字の消失：${{GONE:'消えた',BOTH:'両方にある',NEITHER:'どちらにもない',UNKNOWN:'分からない'}[answers.disappearance]}`;return;}
 document.getElementById('title').textContent=['終了の文字は、新しく出ましたか？','前後のScoreを、そのまま入力してください','終了の文字は、消えましたか？'][step];
 document.getElementById('help').textContent=step===1?'上の数字を転記してください。分からなければ、空欄のまま「分からない」で進めます。':'中央の大きな勝敗などの文字を見てください。購入フェーズの文字は含めません。';
 document.getElementById('numbers').hidden=step!==1;
 if(step===1)showNumbers();
 const choices=step===0?[
  ['NEW','右で新しく出た',true],['BOTH','両方に出ている',true],['NEITHER','どちらにも出ていない',true],['UNKNOWN','分からない・スキップ',false]
 ]:step===1?[
  ['CHANGED','この2枚の間で数字が変わった',true],['SAME','同じ数字だった',true],['UNKNOWN','読めない・分からない',false]
 ]:[
  ['GONE','右では消えた',true],['BOTH','両方に出ている',true],['NEITHER','どちらにも出ていない',true],['UNKNOWN','分からない・スキップ',false]
 ];
 const buttons=document.getElementById('choices');buttons.replaceChildren();
 for(const [value,label,ready] of choices){const b=document.createElement('button');b.textContent=label;if(ready)b.className='needs-ready';b.onclick=()=>answer(value);buttons.append(b);}
 const ci=activeIndex(),s=reviewState[cases[ci].id];for(const [id,key] of [['full','attestedFull'],['noAppearance','explicitNoAppearance'],['noScore','explicitNoScoreChange'],['cut','cutSuspected']])document.getElementById(id).checked=s[key];
 updateFullGate();showPair();
}
function answer(choice){
 if(choice!=='UNKNOWN'&&!pairReady())return;
 try{
  if(step===1){readNumbers();const complete=[...answers.beforeScore,...answers.afterScore].every(x=>x!==null);const equal=JSON.stringify(answers.beforeScore)===JSON.stringify(answers.afterScore);
   if(choice==='CHANGED'&&(!complete||equal))throw Error('両方の画像の数字を入力してください。同じ数字なら「同じ」、読めなければ「分からない」を選びます。');
   if(choice==='SAME'&&(!complete||!equal))throw Error('両方の画像を転記してください。数字が異なる場合は「変わった」、読めない場合は「分からない」を選びます。');
   answers.score=choice;
  }else if(step===0)answers.appearance=choice;else answers.disappearance=choice;
  const pair=currentPair();log('human_explicit_pair_answer',cases[activeIndex()].id,null,{question:step,choice,frame_ids:pair.map(x=>x.id)});saveViewChecks();step++;render();
 }catch(e){document.getElementById('loading').textContent=e.message;}
}
document.getElementById('back').onclick=()=>{if(step<3){if(step===1)readNumbers();saveViewChecks();}if(step>0){step--;render();}};
document.getElementById('save').onclick=()=>{
 try{log('export_requested');const result=simpleResponse(D.packet,D.template,answers,reviewState,chronology);const uri=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=uri;a.download='boundary_simple_'+D.packet.cases[0].id.split('_')[0]+'_human_review.json';a.click();setTimeout(()=>URL.revokeObjectURL(uri),1000);document.getElementById('saved').textContent='JSONを保存しました。このファイルのパスをチャットで教えてください。';}
 catch(e){document.getElementById('saved').textContent=e.message;}
};
for(let i=0;i<2;i++)document.getElementById('image'+i).onclick=()=>{if(!pairReady())return;document.getElementById('original').src=currentPair()[i].uri;document.getElementById('dialog').showModal();};
document.getElementById('close').onclick=()=>document.getElementById('dialog').close();
document.getElementById('play').onclick=async()=>{
 const token=++playing,ci=activeIndex(),c=cases[ci],v=nativeViews[ci],img=document.getElementById('playerImage'),s=reviewState[c.id];document.getElementById('player').hidden=false;
 document.getElementById('play').disabled=true;
 for(let i=0;i<v.frame_ids.length;i++){
  if(token!==playing)break;const f=byId[c.id][v.frame_ids[i]];img.src=f.uri;
  const gate={displaySequence:token,loadedFrameId:null,decodedFrames:s.decodedFrames};const ok=await decodeFrameReady(gate,f.id,[img],token);
  if(token!==playing)break;if(!ok){document.getElementById('playerIndex').textContent='画像を読み込めません。全体確認にはしません。';break;}
  log('frame_decoded_not_attention_proof',c.id,f.id,{view_id:v.id});document.getElementById('playerIndex').textContent=`${i+1} / ${v.frame_ids.length}`;updateFullGate();await new Promise(resolve=>setTimeout(resolve,40));
 }
 document.getElementById('play').disabled=false;
};
document.getElementById('stop').onclick=()=>{playing++;document.getElementById('play').disabled=false;};
for(const id of ['full','noAppearance','noScore','cut'])document.getElementById(id).onchange=saveViewChecks;
render();
