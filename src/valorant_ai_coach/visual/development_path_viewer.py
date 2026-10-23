"""Offline, explicitly private candidate-path viewer with optional source frames.

No web requests, upload endpoint, external JavaScript or Production integration.
The output embeds private times/coordinates/images: never commit or publish it.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any


def write_candidate_path_html(
    destination: Path, report: dict[str, Any], *, reference_png: bytes,
    reference_bbox: tuple[int, int, int, int], zones: list[dict[str, Any]],
    source_frames_jpeg: list[bytes | None] | None = None,
) -> None:
    """Embed frame i against report sample i. No time resampling or interpolation."""
    if report.get("qualification") != "development_only" or report.get("ownership") != "UNKNOWN":
        raise ValueError("Only explicitly unqualified UNKNOWN candidate paths can be exported")
    samples = report["samples"]
    if not samples:
        raise ValueError("At least one observation required")
    frames = source_frames_jpeg if source_frames_jpeg is not None else [None]*len(samples)
    if len(frames) != len(samples):
        raise ValueError("One source frame slot per observation required")
    if (len(reference_bbox) != 4 or reference_bbox[2] <= reference_bbox[0]
            or reference_bbox[3] <= reference_bbox[1]):
        raise ValueError("Positive reference bbox required")

    def uri(content: bytes, kind: str) -> str:
        return f"data:image/{kind};base64," + base64.b64encode(content).decode("ascii")

    payload = {"report": report, "bbox": reference_bbox, "zones": zones,
               "reference": uri(reference_png, "png"),
               "frames": [uri(frame, "jpeg") if frame else None for frame in frames]}
    # Prevent embedded metadata from closing the data script element.
    data = json.dumps(payload, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
    destination.write_text(_HTML.replace("__PAYLOAD__", data), encoding="utf-8")


_HTML = r'''<!doctype html>
<html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:;
style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>PRIVATE · Map候補の移動経路</title>
<style>
body{font:15px system-ui;margin:24px;background:#111827;color:#e5e7eb}
h1{font-size:24px}.note{color:#fbbf24}button,select{padding:8px;margin:3px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}canvas,img{width:100%;background:#030712}
#source{aspect-ratio:16/9;object-fit:contain}#map{max-height:65vh;object-fit:contain}
#seek{width:100%}pre{white-space:pre-wrap}
table{border-collapse:collapse;width:100%}td,th{padding:6px;border-bottom:1px solid #374151}
tr.active{background:#1f4660}.bar{display:flex;height:18px;margin:12px 0}.bar span{flex:1}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
</style>
<h1>Map候補の移動経路 <small>PRIVATE / 開発専用</small></h1>
<p class="note">本人所有は全件UNKNOWN。点は観測座標、破線は隣接観測の直線です。
観測間の実際の経路・連続滞在・停止・戦術的な良否は確定しません。</p>
<label>取得区間 <select id="acquisition"></select></label>
<button id="prev">前へ</button><button id="play">再生</button><button id="next">次へ</button>
<input id="seek" type="range" min="0" value="0" aria-label="観測を選ぶ">
<div id="coverage" class="bar" title="観測ごとの取得状態。区間間の時間を圧縮しています"></div>
<p id="status"></p><div class="grid"><div><img id="source" alt="同じ時刻の入力画像">
<p id="frameStatus"></p><pre id="detail"></pre></div><div>
<canvas id="map" width="1024" height="1024" aria-label="観測座標と途切れを示すMap"></canvas>
</div></div>
<p>再生は観測単位。区間を越えると停止します。欠落中は現在位置を表示せず、線を接続しません。
数値は公開参照画像のpxです。信頼性はスコアとUNKNOWN理由を確認してください。</p>
<pre id="summary"></pre>
<table><thead><tr><th>区間</th><th>観測点数</th><th>観測間の時間合計</th></tr></thead>
<tbody id="segments"></tbody></table>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
'use strict';
const D=JSON.parse(document.getElementById('data').textContent),R=D.report,S=R.samples;
const $=id=>document.getElementById(id), C=$('map'),ctx=C.getContext('2d');
const zoneName=id=>D.zones.find(z=>z.zone_id===id)?.zone_name||'UNKNOWN';
const motionName={moving_candidate:'移動候補',low_displacement_candidate:'低変位候補',
indeterminate:'判定保留'};
let index=0,timer=null;const image=new Image();
const context=s=>JSON.stringify([s.source_id,s.acquisition_id]);
const keys=[...new Set(S.map(context))];
keys.forEach((key,i)=>{const o=document.createElement('option');o.value=key;
o.textContent=JSON.parse(key).join(' / ');$('acquisition').append(o)});
S.forEach((s,i)=>{const b=document.createElement('span');
b.style.background=s.point_norm?'#38bdf8':'#6b7280';
b.title=`${s.time_sec.toFixed(3)}s · ${s.break_reason||'位置候補'}`;
b.onclick=()=>{stop();index=i;draw()};$('coverage').append(b)});
R.segments.forEach(g=>{const tr=document.createElement('tr');tr.dataset.segment=g.segment;
[g.segment,g.sample_indices.length,g.observed_span_sec.toFixed(3)+' s'].forEach(v=>{
const td=document.createElement('td');td.textContent=v;tr.append(td)});$('segments').append(tr)});
function xy(p){return [D.bbox[0]+p[0]*(D.bbox[2]-D.bbox[0]),
D.bbox[1]+p[1]*(D.bbox[3]-D.bbox[1])];}
function line(points,color,dash){ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=3;
ctx.setLineDash(dash);points.map(xy).forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();}
function draw(){const s=S[index];$('seek').value=index;$('acquisition').value=context(s);
ctx.clearRect(0,0,C.width,C.height);if(image.complete)ctx.drawImage(image,0,0,1024,1024);
D.zones.forEach(z=>line([...z.polygon_norm,z.polygon_norm[0]],'#a78bfa',[]));
R.edges.filter(e=>e.to_index<=index&&context(S[e.to_index])===context(s)).forEach(e=>
line([S[e.from_index].point_norm,S[e.to_index].point_norm],e.segment===s.segment?'#38bdf8':'#64748b',[5,6]));
S.slice(0,index+1).filter(p=>p.point_norm&&context(p)===context(s)).forEach(p=>{
ctx.beginPath();ctx.fillStyle=p.segment===s.segment?'#38bdf8':'#64748b';ctx.arc(...xy(p.point_norm),3,0,Math.PI*2);ctx.fill()});
if(s.point_norm){ctx.beginPath();ctx.setLineDash([]);ctx.strokeStyle='#fbbf24';ctx.lineWidth=3;
ctx.arc(...xy(s.point_norm),10,0,Math.PI*2);ctx.stroke()}
$('status').textContent=`${s.source_id} / ${s.acquisition_id} `+
`· 原動画 ${s.time_sec.toFixed(3)} s · 観測 ${index+1}/${S.length} `+
`· ${s.point_norm?'位置候補':'位置 UNKNOWN'} · Zone ${zoneName(s.zone_id)} `+
`· 候補領域 ${zoneName(s.region_candidate_id)}`;
if(D.frames[index]){$('source').src=D.frames[index];$('source').hidden=false}
else{$('source').removeAttribute('src');$('source').hidden=true}
$('frameStatus').textContent=D.frames[index]?
'同時刻の入力画像。参照との外観一致数は下欄に表示します。所有者は全件UNKNOWN。':
'この観測には入力画像が付属していません';
const edge=R.edges.find(e=>e.to_index===index);
const boundary=s.region_candidate_evidence;
const evidence=s.ownership_evidence;const reviewed=s.position_review;
const recorder=s.recorder_view_evidence;const viewReview=s.view_review;
const alias=recorder?.actor_alias_evidence;
const factors=recorder?.identity_factors;
const reviewedBoundary=reviewed?.reference_polygon_review;
const matches=s.marker_reference_evidence?.matches||[];
const selfMatches=matches.filter(m=>m.reference_category==='self_reference_appearance').length;
const controlMatches=matches.filter(m=>m.reference_category==='nonself_control_appearance').length;
$('detail').textContent=`本人所有: UNKNOWN / 経路区間: ${s.segment??'なし'}\n`+
`外観一致スコア: ${s.appearance_similarity?.toFixed(3)??'未測定'} `+
`/ 校正スコア: ${s.calibration_score?.toFixed(3)??'未測定'}（確率ではありません）\n`+
`途切れ・不明理由: ${s.break_reason??'なし'} / 画像照合: ${s.appearance_reason}\n`+
`運動の候補: ${edge?motionName[edge.motion]:'UNKNOWN'}\n`+
`隣接観測の変位: ${edge?edge.chord_reference_px.toFixed(2)+' px':'未測定'}\n`+
`本人参照の外観一致: ${selfMatches} / 非本人参照の外観一致: ${controlMatches}\n`+
`候補領域の境界: ${boundary?.boundary_assessment??'未測定'} / 境界まで `+
`${boundary?.boundary_clearance_reference_px?.toFixed(2)??'未測定'} px / 仮定誤差半径 `+
`${boundary?.assumed_error_radius_reference_px??'未指定'} px（精度保証ではありません）\n`+
`独立画面の根拠候補: ${evidence?.view_candidate??'未測定'} `+
`/ ${evidence?.reasons?.join(', ')??'なし'}\n`+
`録画者agentとの対応: ${recorder?.association??'未測定'} / 登録agent `+
`${recorder?.recorder_agent_id??'UNKNOWN'} / 現在の表示候補 `+
`${recorder?.visible_agent_candidate??'UNKNOWN'}（アカウント所有は未確定）\n`+
`明示名の対応: ${alias?.alias_association??'未測定'} / ${alias?.slot_kind??'未観測'}\n`+
`共有一人称HUDの観測: ${factors?.shared_first_person_hud_observed??'未分解'} / `+
`資格付き本人視点: ${factors?.qualified_live_recorder_view??false}\n`+
`本人確定に不足する根拠: ${factors?.missing_evidence?.join(', ')??'未測定'}\n`+
`人間が確認した現在視点: ${viewReview?.human_view_role??'未確認'}（この観測のみ）\n`+
`この観測のマーカー確認: ${reviewed?.human_reviewed_role??'未確認'} / ROI中心との差 `+
`${reviewed?.roi_center_difference_px?.toFixed(2)??'未測定'} px / 近似Map参照との差 `+
`${reviewed?.map_affine_reference_difference_px?.toFixed(2)??'未測定'} px`+
`（他の点へ適用しません）\n`+
`確認点の登録Polygon一致: ${reviewedBoundary?.membership_agrees??'未測定'} / `+
`注釈1座標の微小変動による境界変化: `+
`${reviewedBoundary?.membership_changes_under_single_coordinate_perturbation??'未測定'}`+
`（変化なしでも誤差保証にはなりません）`;
document.querySelectorAll('tr[data-segment]').forEach(tr=>tr.classList.toggle('active',Number(tr.dataset.segment)===s.segment));}
function stop(){clearTimeout(timer);timer=null;$('play').textContent='再生'}
function step(){if(index+1>=S.length||context(S[index+1])!==context(S[index])){stop();return}
const delay=Math.max(40,Math.min(2000,(S[index+1].time_sec-S[index].time_sec)*1000));
timer=setTimeout(()=>{index++;draw();step()},delay)}
$('seek').max=S.length-1;$('seek').oninput=()=>{stop();index=Number($('seek').value);draw()};
$('next').onclick=()=>{stop();index=Math.min(index+1,S.length-1);draw()};
$('prev').onclick=()=>{stop();index=Math.max(index-1,0);draw()};
$('play').onclick=()=>{if(timer){stop()}else{$('play').textContent='停止';step()}};
$('acquisition').onchange=()=>{stop();index=S.findIndex(s=>context(s)===$('acquisition').value);draw()};
const spans=o=>Object.entries(o||{}).map(([k,v])=>`${zoneName(k)}: ${v.toFixed(3)} s`).join(' / ');
$('summary').textContent=`位置UNKNOWN: ${R.position_unknown_observations}観測\n`+
`同じZoneが両端で観測された時間: ${spans(R.zone_observation_spans_sec)||'なし'}\n`+
`同じ候補領域が両端で観測された時間: `+
`${spans(R.region_candidate_observation_spans_sec)||'なし'}\n`+
`仮定誤差円が両端で領域内に収まる観測時間: `+
`${spans(R.region_interior_spans_under_assumption_sec)||'なし'}\n`+
`運動の候補別の観測時間: `+
Object.entries(R.motion_observation_spans_sec).map(([k,v])=>
`${motionName[k]} ${v.toFixed(3)} s`).join(' / ')+
`\n運動の判定窓: ${R.parameters.quiet_window_sec}s / 誤差の仮定: `+
`${R.parameters.position_uncertainty_px}px（感度分析用、精度保証ではありません）\n`+
`Zone変更が観測された区間: ${R.zone_change_brackets.length}\n`+
`座標比較済み: ${R.coordinate_review_coverage?.reviewed_position_observations??0}点 / `+
`未確認: ${R.coordinate_review_coverage?.unreviewed_position_observations??0}点 `+
`（全経路の座標精度は未測定）\n`+
`録画者agent対応の位置候補: ${R.recorder_view_support?.supported_position_observations??0}点 `+
`/ 両端対応の観測時間: `+
`${R.recorder_view_support?.both_endpoints_supported_span_sec?.toFixed(3)??'0'} s `+
`（自動本人所有の資格は未成立）\n`+
`人間確認の生存視点にある位置: `+
`${R.recorder_view_support?.human_self_live_position_observations??0}点 `+
`（表示した観測だけ。観測間の所有・経路は保証しません）\n`+
`人間ラベル別の候補: `+Object.entries(R.identity_outcomes?.groups||{}).map(([role,g])=>
`${role} ${g.observations}点 / agent対応${g.agent_support} / `+
`未確定の視点対応${g.view_support_candidate} / 非生存の位置候補${g.non_live_position_candidate??0}`
).join(' ; ')+`\n静止確認点の揺れ: `+((R.stationary_review_comparisons||[]).map(r=>
`確認${r.reviewed_observations}点・欠測${r.missing_positions}点 / `+(r.runs.map(run=>
run.spread_measured?`${run.position_observations}点、`+
`直径${run.diameter_reference_px.toFixed(2)}px `+
`RMS ${run.rms_about_mean_reference_px.toFixed(2)}px`:'単点のため未測定').join(' ; ')
||'位置欠測のため揺れ未測定')
).join(' ; ')||'未確認・未測定')+`（絶対誤差・連続静止の保証ではありません）`;
image.onload=draw;image.src=D.reference;draw();
</script></html>'''
