"""Tokenized localhost multi-match review and lazy original-video drill-down."""

from __future__ import annotations

import argparse
import json
import math
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .comparison import build_catalog, load_manifest
from .issue_review import context_window, issue_page, load_review_sidecars, presentation_catalog
from .viewer import make_server

HTML = r"""<!doctype html><html lang="ja"><meta charset="utf-8">
<title>試合横断タイムライン — 開発用</title><style>
body{
font:15px system-ui;
margin:24px;
background:#101820;
color:#e8edf2}

a{
color:#8ed1ff}
button,
input,
select{
padding:7px;
margin:4px;
background:#263645;
color:#fff}

table{
border-collapse:collapse;
width:100%;
font-size:13px}
td,
th{
padding:8px;
border:1px solid #415263;
text-align:left}

canvas{
width:100%;
height:108px;
cursor:crosshair;
background:#39434d}
.muted{
color:#bac7d3}

pre{
white-space:pre-wrap;
overflow-wrap:anywhere;
max-height:350px;
overflow:auto}
section{
margin:24px 0}

.error{
color:#ff9999}
.unknown{
color:#c5ced6}
small{
font-weight:normal}

</style><h1>試合横断タイムライン <small>開発用</small></h1>
<p class="muted">候補・推定を表示します。観測率は正解率ではありません。
異なる取得条件・観測密度は別の比較条件です。</p>

<p id="summary">入力を検証中…</p>

<label><input id="alternate" type="checkbox">比較用の別結果も表示</label>
<p>UNKNOWN：灰＝観測あり・未解決、濃灰＝未観測、紫＝競合。
各帯の順序は Round／本人／カメラ／HUD／Map／Zone。白線はイベント候補です。</p>

<table><thead><tr><th>物理試合・結果</th>
<th>全長／観測・推定</th>
<th>状態が得られた秒・UNKNOWN率</th>
<th>HUD候補</th>
<th>Map・Zone・イベント</th>
<th>構成</th>
</tr></thead><tbody id="matches"></tbody></table>
<div id="lanes"></div><section><h2>選択した結果の確認</h2>
<select id="result"></select>
<label>元動画の秒 <input id="time" type="number" min="0" value="0"></label>
<button id="open">元動画・native根拠を開く</button><p id="openStatus"></p>

<button id="context">前後・変更前後・native根拠を表示</button>
<pre id="contextDetail"></pre>
<details><summary>条件・認識器・集計</summary><pre id="detail"></pre></details></section>
<section><h2>自動抽出したレビュー候補</h2>
<p class="muted">未ラベル区間です。誤認識、死亡、欠落の発生を確定した一覧ではありません。</p>

<select id="kind"><option value="">全種類</option></select>
<select id="issueMatch"><option value="">全結果</option></select>
<p id="issueCount"></p>

<table><thead><tr><th>結果</th>
<th>候補種別</th>
<th>区間（秒）</th>
<th>根拠</th>
</tr></thead><tbody id="issues"></tbody></table>
<button id="more">次の100候補</button></section>
<section id="analysisPanel" hidden><h2>固定した基準結果の原因仮説・優先順位</h2>
<p>現在の主結果とは別に、固定した旧結果を分析します。誤認識の断定ではありません。
A8は秒内の表示曖昧性で、native情報は保持しています。</p>
<select id="cause"><option value="">全原因</option></select>
<button id="causeLoad">抽出</button><p id="causeCount"></p>
<table><tbody id="causeRows"></tbody></table>
<button id="causeMore">次の100件</button></section>
<section><h2>改善・不採用履歴</h2><pre id="history"></pre></section>
<p><a id="json">比較JSON</a>
 / <a id="csv">比較CSV</a></p>

<script>
const $=id=>document.getElementById(id),
base='/'+location.pathname.split('/')[1];
let catalog,
page=0;

const colors={
BUY:'#dcb74e',
ACTIVE:'#4dba94',
ENDED:'#dd7777',
INTERMISSION:'#91a2ba',
ALIVE:'#4dba94',
DEAD:'#dd7777',
DOWNED:'#cf8ddd',
SELF:'#4dba94',
SPECTATOR:'#e7a56f',
REMOTE:'#749ee8'}
;

const unknown={
not_observed:'#28333e',
observed_unresolved:'#73808b',
conflicting_candidates:'#a585c9'}
;

const label={
unknown_not_observed:'長い未観測',
unknown_observed_unresolved:'長い観測ありUNKNOWN',
unknown_conflicting_candidates:'競合UNKNOWN',
life_camera_tension:'本人・カメラの競合候補',
hud_available_state_unresolved:'HUDあり・状態未解決',
map_candidates_unassigned:'Map候補・本人未対応',
buy_run_review:'長いBUY推定',
continuity_uncertain:'継続根拠が未確定',
lifecycle_context_incomplete:'死亡・観戦・復帰の文脈不足',
lifecycle_return_not_linked:'復帰へのリンク未確認（録画末尾を含む）',
competing_state_hypotheses:'競合する状態仮説',
acquisition_or_configuration_changed:'取得・構成による状態差'}
;

const cell=(tr,
text)=>{
const td=document.createElement('td');
td.textContent=text;
tr.append(td);
return td}
;

function shown(){
return catalog.results.filter(r=>r.primary||$('alternate').checked)}

function select(id,
t=0){
$('result').value=id;
$('time').value=t;
const r=catalog.results.find(r=>r.id===id);
$('time').max=r.rows-1;
$('detail').textContent=JSON.stringify({
...r,
seconds:undefined,
review_intervals:undefined}
,
null,
2)}

function render(){
 $('matches').replaceChildren();
$('lanes').replaceChildren();

for(const r of shown()){
const tr=document.createElement('tr');
cell(tr,
r.source.physical_match_id+' / '+r.label+(r.primary?'〔主結果〕':'〔別条件〕'));

cell(tr,
r.rows+'秒行 / 観測 '
+r.observed_seconds
+' / 状態推定のみ '+r.inferred_only_seconds
+' / 未観測 '+r.unobserved_seconds);

cell(tr,
['round_state',
'life_state',
'camera_state'].map((d,
i)=>['Round',
'本人',
'Camera'][i]+': '+r.domains[d].available_seconds
+' / UNKNOWN '+(r.domains[d].unknown_fraction*100).toFixed(1)+'%')
.join('\n'));

cell(tr,
Object.entries(r.hud_candidate_seconds).map(([k,
v])=>k+': '+v).join(' / '));

cell(tr,
'Map '+r.map_candidate_seconds
+' / 本人 '+r.map_self_candidate_seconds
+' / 暫定 '+r.map_provisional_seconds
+' / Zone '+r.zone_candidate_seconds
+' / event '+r.event_candidate_seconds+'秒');

cell(tr,
r.generation_status+'\n条件 '+r.condition_identity.slice(0,
12)+'\n認識器・構成 '+r.recognizer_configuration_identity.slice(0,
12));
$('matches').append(tr);

const s=document.createElement('section'),
h=document.createElement('h3');
h.textContent=r.label+' — '+r.rows+'秒';
s.append(h);

const c=document.createElement('canvas');
c.width=1800;
c.height=108;
c.setAttribute('aria-label',
r.label+' 全長タイムライン');
s.append(c);
$('lanes').append(s);
const g=c.getContext('2d');

r.seconds.forEach((row,
i)=>{
['round_state',
'life_state',
'camera_state'].forEach((d,
j)=>{
g.fillStyle=colors[row[d]]||unknown[row.unknown_reasons[d]]||'#73808b';
g.fillRect(i*c.width/r.rows,
j*18,
Math.max(1,
c.width/r.rows),
17)}
);

['hud',
'map',
'zone'].forEach((k,
j)=>{
g.fillStyle=row[k]?'#65a9ce':'#28333e';
g.fillRect(i*c.width/r.rows,
(j+3)*18,
Math.max(1,
c.width/r.rows),
17)}
);
if(row.events){
g.fillStyle='#fff';
g.fillRect(i*c.width/r.rows,
0,
1,
5)}
}
);

c.onclick=e=>select(r.id,
Math.min(r.rows-1,
Math.floor((e.clientX-c.getBoundingClientRect().left)/c.clientWidth*r.rows)));
}

renderIssues()}

function renderIssues(){
let issues=shown().flatMap(r=>r.review_intervals.map(i=>({
...i,
result:r.id}
))).filter(i=>(!$('kind').value||i.kind===$('kind').value)&&(!$('issueMatch').value||i.result===$('issueMatch').value));
$('issues').replaceChildren();
$('issueCount').textContent=issues.length+'候補 / '+(page*100+1)+'件目から表示';

for(const i of issues.slice(page*100,
page*100+100)){
const tr=document.createElement('tr');
cell(tr,
i.result);
cell(tr,
(label[i.kind]||i.kind)+' / '+i.domain);
const td=cell(tr,
'');
const b=document.createElement('button');
b.textContent=i.start+'–'+i.end;
b.onclick=()=>select(i.result,
i.start);
td.append(b);
cell(tr,
(i.evidence_refs_count??i.evidence_refs?.length??0)+' native観測参照 / '
+(i.sample_refs_count??i.sample_refs?.length??0)+'点');
$('issues').append(tr)}
$('more').disabled=(page+1)*100>=issues.length}

let causePage=0;
async function causes(){
const query=new URLSearchParams({cause:$('cause').value,
id:$('issueMatch').value,page:String(causePage)});
const response=await fetch(base+'/api/issues?'+query);
if(!response.ok)throw Error('原因分類の読込み失敗');
const data=await response.json();
$('causeCount').textContent=data.total+'基準結果の原因候補 / 件数は複数分類。基準manifest SHA: '
+data.baseline_manifest_sha256;
$('causeRows').replaceChildren();
for(const row of data.records){
const tr=document.createElement('tr');
cell(tr,row.result_id+(row.representative?'〔代表〕':''));
cell(tr,row.causes.map(c=>c.code+' '+c.label).join(' / '));
cell(tr,'優先度 '+row.priority.score+' / '+row.start+'–'+row.end);
const td=cell(tr,'');const b=document.createElement('button');
b.textContent='前後・変更比較';
b.onclick=()=>{select(row.result_id,row.inspection_window.anchor);showContext()};
td.append(b);$('causeRows').append(tr)}
$('causeMore').disabled=(causePage+1)*100>=data.total}
async function showContext(){
$('contextDetail').textContent='native根拠と前後5秒を検証中…';
const response=await fetch(base+'/api/context?'+new URLSearchParams({
id:$('result').value,second:String(Math.floor(Number($('time').value)))}));
$('contextDetail').textContent=response.ok?
JSON.stringify(await response.json(),null,2):'比較の入力検証に失敗';}
$('context').onclick=showContext;
$('causeLoad').onclick=()=>{causePage=0;causes()};
$('causeMore').onclick=()=>{causePage++;causes()};
$('result').onchange=()=>select($('result').value);
$('alternate').onchange=render;
$('kind').onchange=$('issueMatch').onchange=()=>{
page=0;
renderIssues()}
;
$('more').onclick=()=>{
page++;
renderIssues()}
;

$('open').onclick=()=>{
const t=Number($('time').value),
r=catalog.results.find(x=>x.id===$('result').value);
if(!Number.isFinite(t)||t<0||t>=r.rows){
$('openStatus').textContent='範囲内の秒を選んでください';
return}
$('openStatus').textContent='元動画の登録・SHAを検証して開きます';
window.open(base+'/open?id='+encodeURIComponent(r.id)+'&second='+t,
'_blank',
'noopener')}
;

(async()=>{
const response=await fetch(base+'/api/catalog');
if(!response.ok)throw Error('比較の読込みに失敗');
catalog=await response.json();
$('summary').textContent=catalog.physical_matches+'物理試合 / 主結果 '
+catalog.primary_rows+'秒行 / '
+catalog.result_versions+'結果バージョン。正式Fact/Event 0。';

for(const r of catalog.results){
for(const id of ['result',
'issueMatch']){
const o=document.createElement('option');
o.value=r.id;
o.textContent=r.label;
$(id).append(o)}
}

for(const kind of [...new Set(catalog.results.flatMap(
r=>r.review_intervals.map(i=>i.kind)))].sort()){
const o=document.createElement('option');
o.value=kind;
o.textContent=label[kind]||kind;
$('kind').append(o)}

$('json').href=base+'/download.json';
$('csv').href=base+'/download.csv';
render();
select((catalog.results.find(r=>r.primary)||catalog.results[0]).id);
if(catalog.review_analysis_available){
$('analysisPanel').hidden=false;
for(let i=1;i<=10;i++){const o=document.createElement('option');
o.value='A'+i;o.textContent=o.value;$('cause').append(o)}
await causes()}
const history=await fetch(base+'/api/history');
$('history').textContent=JSON.stringify(await history.json(),null,2)}
)().catch(e=>{
$('summary').textContent=e.message;
$('summary').className='error'}
);

</script></html>"""


class ComparisonServer(ThreadingHTTPServer):
    """Own lazy child viewers so desktop close releases their sockets as well."""

    viewer_url: str

    def __init__(self, address: tuple[str, int], handler: Any) -> None:
        self.children: dict[str, ThreadingHTTPServer] = {}
        self.child_lock = threading.Lock()
        super().__init__(address, handler)

    def server_close(self) -> None:
        with self.child_lock:
            for child in self.children.values():
                child.shutdown()
                child.server_close()
            self.children.clear()
        super().server_close()


def make_comparison_server(manifest_path: Path, *, port: int = 0) -> ComparisonServer:
    entries = {e["id"]: e for e in load_manifest(manifest_path)}
    catalog = build_catalog(manifest_path)
    summaries = {r["id"]: r for r in catalog["results"]}
    review = load_review_sidecars(manifest_path, entries)
    presentation = presentation_catalog(catalog)
    presentation["review_analysis_available"] = review["analysis"] is not None
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def do_HEAD(self) -> None:
            self.do_GET()

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            prefix = "/" + token
            if not parsed.path.startswith(prefix + "/"):
                self.send_error(404)
                return
            route = parsed.path[len(prefix) :]
            try:
                if route == "/open":
                    query = parse_qs(parsed.query)
                    result_id = query["id"][0]
                    second = float(query["second"][0])
                    if not math.isfinite(second) or not 0 <= second < summaries[result_id]["rows"]:
                        raise ValueError("Second outside recording")
                    entry = entries[result_id]
                    from .comparison import load_result

                    # Recheck immutable bindings before handing an existing viewer a path.
                    load_result(entry)
                    with server.child_lock:
                        if result_id not in server.children:
                            child = make_server(Path(entry["bundle"]), Path(entry["policy"]))
                            threading.Thread(target=child.serve_forever, daemon=True).start()
                            server.children[result_id] = child
                        child = server.children[result_id]
                    self.send_response(302)
                    self.send_header("Location", child.viewer_url + f"?second={second}")  # type: ignore[attr-defined]
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return
                if route == "/":
                    payload, kind = HTML.encode("utf-8"), "text/html; charset=utf-8"
                elif route == "/api/issues":
                    query = parse_qs(parsed.query)
                    data = issue_page(
                        review,
                        cause=query.get("cause", [""])[0],
                        result_id=query.get("id", [""])[0],
                        page=int(query.get("page", ["0"])[0]),
                    )
                    payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
                    kind = "application/json; charset=utf-8"
                elif route == "/api/context":
                    query = parse_qs(parsed.query)
                    data = context_window(entries, query["id"][0], int(query["second"][0]))
                    payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
                    kind = "application/json; charset=utf-8"
                elif route == "/api/history":
                    payload = json.dumps(review["history"], ensure_ascii=False).encode("utf-8")
                    kind = "application/json; charset=utf-8"
                elif route in {"/api/catalog", "/download.json"}:
                    payload = json.dumps(
                        presentation if route == "/api/catalog" else catalog,
                        ensure_ascii=False,
                        allow_nan=False,
                    ).encode("utf-8")
                    kind = "application/json; charset=utf-8"
                elif route == "/download.csv":
                    import csv
                    import io

                    stream = io.StringIO(newline="")
                    writer = csv.writer(stream)
                    writer.writerow(
                        [
                            "result",
                            "physical_match",
                            "rows",
                            "observed",
                            "round_unknown",
                            "life_unknown",
                            "camera_unknown",
                            "conditions",
                        ]
                    )
                    for r in catalog["results"]:
                        writer.writerow(
                            [
                                r["id"],
                                r["source"]["physical_match_id"],
                                r["rows"],
                                r["observed_seconds"],
                                *[
                                    r["domains"][d]["unknown_seconds"]
                                    for d in ("round_state", "life_state", "camera_state")
                                ],
                                r["condition_identity"],
                            ]
                        )
                    payload, kind = stream.getvalue().encode("utf-8"), "text/csv; charset=utf-8"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)
            except (KeyError, ValueError, IndexError, OSError):
                self.send_error(400, "Invalid comparison query or changed input")
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ComparisonServer(("127.0.0.1", port), Handler)
    server.viewer_url = f"http://127.0.0.1:{server.server_port}/{token}/"
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    server = make_comparison_server(args.manifest, port=args.port)
    print(server.viewer_url, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
