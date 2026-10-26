function emptySimpleAnswers() {
  return {appearance:'UNKNOWN',score:'UNKNOWN',disappearance:'UNKNOWN',beforeScore:[null,null],afterScore:[null,null]};
}
function simpleResponse(packet, template, answers, reviewState, chronology) {
  const response = structuredClone(template);
  response.ui_protocol='simple_pair_review_v2_wait_decode';
  response.simple_answers=structuredClone(answers);
  response.reported_chronology=structuredClone(chronology);
  response.review_chronology_is_self_reported=true;
  response.case_notes={};
  response.native_images_decoded={};
  const nativeViews=packet.cases.map(c=>c.views.find(v=>v.all_native_images));
  for (const [ci,c] of packet.cases.entries()) {
    const view=nativeViews[ci], a=response.cases[ci], state=reviewState[c.id];
    if (!view) throw Error('A Native review view is required');
    const before=view.frame_ids[0], after=view.frame_ids.at(-1), points={};
    function point(id) {return points[id]??=( {id,frame_id:id,reviewed:true,result_state:'UNKNOWN',score:null});}
    function states(left,right) {point(before).result_state=left;point(after).result_state=right;}
    function bracket(kind) {a.boundaries.push({id:kind,kind,before,after});}
    a.points=[];a.boundaries=[];a.interval_claims=[];
    const choice=ci===0?answers.appearance:answers.disappearance;
    if (choice!=='UNKNOWN' && (!state.decodedFrames.has(before)||!state.decodedFrames.has(after))) throw Error('Answer requires both decoded original images');
    if (ci===0 && choice==='NEW') {states('ABSENT','PRESENT');bracket('RESULT_APPEARANCE');}
    else if (ci!==0 && choice==='GONE') {states('PRESENT','ABSENT');bracket('RESULT_DISAPPEARANCE');}
    else if (choice==='BOTH') states('PRESENT','PRESENT');
    else if (choice==='NEITHER') states('ABSENT','ABSENT');
    if (ci===0) {
      const entered=answers.beforeScore.some(x=>x!==null)||answers.afterScore.some(x=>x!==null);
      if (entered && answers.score!=='UNKNOWN') {
        if (!state.decodedFrames.has(before)||!state.decodedFrames.has(after)) throw Error('Score requires both decoded original images');
        for (const pair of [answers.beforeScore,answers.afterScore]) if (!pair.every(x=>x===null||(Number.isInteger(x)&&x>=0&&x<=99))) throw Error('Use actual digits or unknown');
        point(before).score=structuredClone(answers.beforeScore);point(after).score=structuredClone(answers.afterScore);
      }
      const complete=entered&&[...answers.beforeScore,...answers.afterScore].every(x=>x!==null);
      const equal=JSON.stringify(answers.beforeScore)===JSON.stringify(answers.afterScore);
      if (answers.score==='CHANGED') {
        if (!complete||equal) throw Error('A Score-change claim needs two explicitly read, different pairs');
        bracket('SCORE_CHANGE');
      }
      if (answers.score==='SAME' && (!complete||!equal)) throw Error('A same-Score answer needs two explicitly read, equal pairs');
    }
    a.points=Object.values(points);
    const full=Boolean(state.attestedFull)&&canAttestFullNative(state,view);
    a.scopes=[{id:view.id,start:before,end:after,coverage:full?'FULL':(a.points.length?'PARTIAL':'UNKNOWN'),full_interval_reviewed:full}];
    for (const kind of ['RESULT_APPEARANCE','RESULT_DISAPPEARANCE','RESULT_COMPLETE','SCORE_CHANGE']) {
      let occurred='UNKNOWN';
      if (full && kind==='RESULT_APPEARANCE' && state.explicitNoAppearance===true) occurred='NO';
      if (full && kind==='SCORE_CHANGE' && state.explicitNoScoreChange===true) occurred='NO';
      a.interval_claims.push({kind,scope_id:view.id,occurred});
    }
    response.case_notes[c.id]={source_discontinuity:state.cutSuspected?'SUSPECTED':'UNKNOWN',notes:''};
    response.native_images_decoded[c.id]=[...state.decodedFrames];
  }
  return response;
}
