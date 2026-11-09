"""Local-only development timeline viewer referencing the original recording."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import secrets
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .application import VERSION
from .replay import SourcePolicy, file_sha, read_json

HTML = r"""<!doctype html><html lang="ja"><meta charset="utf-8">
<title>共通タイムライン — 開発用</title><style>
body{font:15px system-ui;
margin:24px;
background:#101820;
color:#e8edf2}
main{display:grid;
grid-template-columns:minmax(360px,1fr) minmax(360px,1fr);
gap:20px}
video{width:100%;
background:#000}canvas{width:100%;
height:96px;
cursor:crosshair}
button,select,input{padding:8px;
margin:4px;
background:#263645;
color:#fff;
border:1px solid #6c7d8c}
input[type=range]{width:95%}pre{white-space:pre-wrap;
overflow-wrap:anywhere;
max-height:400px;
overflow:auto}
.muted{color:#bbc6d0}a{color:#86ccff}details{border-top:1px solid #415263;
padding:8px}
.error{color:#ff8f8f}@media(max-width:850px){main{display:block}}
</style><h1>共通タイムライン <small>開発用</small></h1>
<p class="muted">推定・候補を含みます。灰色はUNKNOWN。元の未編集録画を参照します。</p>
<p id="summary">読み込み中…</p><canvas id="chart" width="1600" height="96"></canvas>
<p class="muted">上段：Round／中段：本人／下段：カメラ。クリックで時刻選択。</p>
<label>Round候補 <select id="round"><option value="">全体</option></select></label>
<label>イベント候補 <select id="jump"><option value="">選択</option></select></label>
<label>時刻（秒）<input id="time" type="number" min="0" value="0"></label>
<button id="go">移動</button><button id="prev">前の秒</button><button id="next">次の秒</button>
<input id="slider" aria-label="試合の時刻" type="range" min="0" value="0">
<main><section><h2 id="state"></h2><p id="coverage"></p>
<video id="video" controls preload="metadata"></video>
<p id="playback" class="muted"></p>
<h3>表示中のHUD候補（本人への帰属は未確定）</h3><pre id="hud"></pre>
<h3>HUDの表示状況（ゲーム状態とは別の観測）</h3><pre id="visibility"></pre>
<h3>Map・Zone候補</h3><pre id="map"></pre>
</section><section><h2>イベント候補</h2><div id="events"></div>
<details><summary>状態・不確実性・native参照</summary><pre id="detail"></pre></details>
<details open><summary>根拠を選択</summary><select id="evidence"></select>
<pre id="raw"></pre></details>
<details><summary>下流レビューと評価エンジンへの受け渡し</summary>
<pre id="evaluation"></pre></details>
<p><a id="json">JSON出力</a> / <a id="csv">CSV出力</a></p>
</section></main><script>
const token=location.pathname.split('/')[1], base='/'+token;

const el=id=>document.getElementById(id);
let overview,selected=0,request=0,roundFilter='';

async function api(path){const r=await fetch(base+path);
if(!r.ok)throw Error(await r.text());
return r.json()}
const fmt=value=>JSON.stringify(value,null,2);

const colors={BUY:'#dcb74e',ACTIVE:'#4dba94',ENDED:'#dd7777',ALIVE:'#4dba94',
DEAD:'#dd7777',DOWNED:'#cf8ddd',SELF:'#4dba94',SPECTATOR:'#e7a56f',REMOTE:'#749ee8'};

function allowed(row){return !roundFilter || row.round_candidates.includes(Number(roundFilter))}
function draw(){const c=el('chart'),g=c.getContext('2d');
g.fillStyle='#39434d';
g.fillRect(0,0,c.width,c.height);

overview.seconds.forEach((r,i)=>{['round_state','life_state','camera_state'].forEach((d,j)=>{
g.fillStyle=allowed(r)?(colors[r[d]]||'#66717c'):'#27323c';

g.fillRect(i*c.width/overview.seconds.length,j*32,Math.max(1,c.width/overview.seconds.length),30)})});

g.fillStyle='#fff';
g.fillRect(selected*c.width/overview.seconds.length,0,2,96)}
async function evidence(seek=false){if(!el('evidence').value){el('raw').textContent='根拠なし';
return}
const row=await api('/api/evidence?id='+encodeURIComponent(el('evidence').value));
el('raw').textContent=fmt(row);
if(seek){const s=row.sample,parts=s.native_time_base.split('/').map(Number);
const second=s.native_pts_tick*parts[0]/(parts[1]||1)-overview.native_origin_seconds;
const v=el('video'),offset=v.seekable.length?v.seekable.start(0):0;
if(Number.isFinite(second)&&second>=0&&second<=Number(overview.duration_float_seconds))
v.currentTime=offset+second}}
async function select(second,seek=true){
second=Math.max(0,Math.min(overview.seconds.length-1,Math.floor(second)));

selected=second;
el('time').value=second;
el('slider').value=second;
draw();
const current=++request;

const row=await api('/api/second?n='+second);
if(current!==request)return;

if(seek){const v=el('video');
const offset=v.seekable.length?v.seekable.start(0):0;
v.currentTime=offset+second}
el('state').textContent=second+'秒  Round '+(row.round_number.value??'?')+
' / '+row.round_state.value+
' / '+row.life_state.value+' / '+row.camera_state.value;

el('coverage').textContent=(row.observation_present?'映像観測あり（サンプル点のみ）':'未観測')+
' — '+row.uncertainty;

const hudReasons={unconfigured_reader_or_roi:'読取器未設定',geometry_unsupported:'HUD配置未確認',
unread_or_unaccepted:'読取不能',reader_error:'読取器エラー'};
el('hud').textContent=Object.entries(row.hud_observations).map(([key,value])=>
key+': '+(value.candidates.length?Array.from(new Set(value.candidates.map(c=>
JSON.stringify(c.value)+(c.current_weapon_selection==='UNKNOWN'?'〔選択中の武器は未確定〕':'')+
(c.roi_geometry_qualification==='unqualified_fixed_profile'?'〔固定ROI・配置未資格〕':''))))
.join(' / ')+'（表示値の候補）':'UNKNOWN'+
((value.unavailable_reasons||[]).length?'（'+Array.from(new Set(value.unavailable_reasons.map(r=>
hudReasons[r.reason]||'読取不能'))).join(' / ')+'）':''))).join('\n');
const map=row.map_observations;
const visibility=row.hud_visibility_observations;
const visibilityNames={BUY_MENU:'購入メニュー候補',TRACKER:'Trackerウィンドウ候補'};
el('visibility').textContent=visibility?.analysis_present?
(visibility.candidates.length?Array.from(new Set(visibility.candidates.map(c=>
visibilityNames[c.kind]||c.kind))).join(' / '):'UNKNOWN（確認処理あり・対象表示を特定できず）')+
'\n生死・視点・Roundの根拠には使用しません':'NOT_ANALYSED（表示状況の観測なし）';
el('map').textContent='Map名: '+
(map.map_name_candidates.length?fmt(map.map_name_candidates):'UNKNOWN')+
'\n位置候補: '+map.position_candidates.length+' / 本人対応候補: '+
map.current_self_position_candidates.length+'\n研究用本人位置仮説（本人未確定）: '+
(map.provisional_recorder_position_hypotheses||[]).length+'\nZone候補: '+map.zone_candidates.length+
' '+Array.from(new Set(map.zone_candidates.map(c=>c.label_text||c.zone||'?'))).join(' / ')+
'\n座標候補（未対応は画像座標）: '+fmt(map.position_candidates.slice(0,12).map(c=>
c.map_position_norm||c.center_frame_px||'UNKNOWN'))+
'\n同appearance代替があるnative仮説: '+(map.correspondence_reviews||[]).filter(
r=>r.provisional_highlight_ambiguous).length+'（本人確定には使いません）'+
'\n移動候補: '+map.movement_candidates.length+'（未取得区間は移動と解釈しません）';

el('detail').textContent=fmt(row);
el('evidence').replaceChildren();

row.evidence_refs.forEach(id=>{const o=document.createElement('option');
o.value=id;
o.textContent=id;
el('evidence').append(o)});

await evidence();
el('events').replaceChildren();

for(const id of row.event_candidates){const event=await api('/api/event?id='+id);
const p=document.createElement('p');

p.textContent=event.kind+' 候補 ['+event.lower_timestamp.toFixed(3)+', '+
event.upper_timestamp.toFixed(3)+']秒';
el('events').append(p)}
if(!row.event_candidates.length)el('events').textContent='この秒に候補なし（イベント不在の証明ではありません）'}
el('go').onclick=()=>select(Number(el('time').value));
el('prev').onclick=()=>select(selected-1);

el('next').onclick=()=>select(selected+1);
el('slider').oninput=e=>select(Number(e.target.value));

el('chart').onclick=e=>select((e.clientX-e.target.getBoundingClientRect().left)/e.target.clientWidth*overview.seconds.length);

el('evidence').onchange=()=>evidence(true);
el('round').onchange=e=>{roundFilter=e.target.value;
draw();

const row=overview.seconds.find(allowed);
if(row)select(row.timestamp)};
el('jump').onchange=e=>{if(e.target.value!=='')select(Number(e.target.value))};

el('video').ontimeupdate=()=>{const v=el('video'),offset=v.seekable.length?v.seekable.start(0):0;

el('playback').textContent='元動画 再生位置 '+Math.max(0,v.currentTime-offset).toFixed(3)+'秒';

const n=Math.floor(v.currentTime-offset);
if(!v.seeking&&n!==selected)select(n,false)};

(async()=>{overview=await api('/api/overview');
el('summary').textContent=overview.seconds.length+
'秒行 / 映像観測 '+overview.observed_seconds+'秒 / 元動画 '+
overview.original_duration_float_seconds+'秒'+
(overview.coverage_scope==='PILOT_ONLY'?'（pilot出力）':'');

el('slider').max=overview.seconds.length-1;
el('time').max=overview.seconds.length-1;

overview.round_candidates.forEach(n=>{const o=document.createElement('option');
o.value=n;
o.textContent='Round '+n+'（候補を含む）';
el('round').append(o)});

el('video').src=base+'/video';
overview.event_candidates.forEach(event=>{const option=document.createElement('option');
option.value=Math.floor(event.upper_timestamp);
option.textContent=event.kind+' ['+event.lower_timestamp.toFixed(2)+', '+
event.upper_timestamp.toFixed(2)+']秒';el('jump').append(option)});
el('json').href=base+'/download.json';
el('csv').href=base+'/download.csv';

el('evaluation').textContent=fmt(await api('/api/evaluation'));
const requested=Number(new URLSearchParams(location.search).get('second')||0);
const initial=Number.isFinite(requested)?
Math.max(0,Math.min(overview.seconds.length-1,requested)):0;
el('video').addEventListener('loadedmetadata',()=>select(initial,true),{once:true});
await select(initial,false);

})().catch(e=>{el('summary').textContent=e.message;
el('summary').className='error'});

</script></html>"""


def byte_range(header: str | None, size: int) -> tuple[int, int, int]:
    if header is None:
        return 0, size - 1, 200
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
    if not match or not any(match.groups()):
        raise ValueError("Single byte range required")
    left, right = match.groups()
    if not left:
        suffix = int(right)
        if suffix <= 0:
            raise ValueError("Positive suffix required")
        return max(0, size - suffix), size - 1, 206
    start = int(left)
    end = min(int(right), size - 1) if right else size - 1
    if not 0 <= start <= end < size:
        raise ValueError("Range outside original recording")
    return start, end, 206


def recording_view_metadata(bundle: dict[str, Any]) -> dict[str, Any]:
    """Keep the selected timeline window separate from original recording length."""
    duration = Fraction(bundle["recording"]["duration_seconds"])
    original = Fraction(bundle.get("original_recording_duration_seconds", str(duration)))
    if duration <= 0 or original < duration:
        raise ValueError("Original recording cannot be shorter than the analysed window")
    return {
        "duration_seconds": str(duration),
        "duration_float_seconds": float(duration),
        "original_duration_float_seconds": float(original),
        "coverage_scope": bundle.get("coverage_scope", "UNSPECIFIED"),
    }


def make_server(bundle_path: Path, policy_path: Path, *, port: int = 0) -> ThreadingHTTPServer:
    bundle = read_json(bundle_path)
    if bundle.get("version") != VERSION or bundle.get("formal_outputs") != 0:
        raise ValueError("Development application bundle required")
    completion = read_json(bundle_path.parent / "completion_PRIVATE.json")
    if file_sha(bundle_path) != completion["output_sha256s"][bundle_path.name]:
        raise ValueError("Bundle digest mismatch")
    policy = SourcePolicy(read_json(policy_path))
    source = policy.allowed[bundle["source"]["source_sha256"]]
    video = Path(source["managed_path"])
    if file_sha(video) != source["source_sha256"]:
        raise ValueError("Original registered recording changed")
    token = secrets.token_urlsafe(24)
    seconds = bundle["seconds"]
    overview = {
        **recording_view_metadata(bundle),
        "native_origin_seconds": float(Fraction(bundle["recording"]["native_origin_seconds"])),
        "observed_seconds": sum(r["observation_present"] for r in seconds),
        "round_candidates": sorted({n for r in seconds for n in r["round_number"]["candidates"]}),
        "event_candidates": [
            {k: event[k] for k in ("kind", "lower_timestamp", "upper_timestamp")}
            for event in bundle["events"].values()
        ],
        "seconds": [
            {
                "timestamp": r["timestamp"],
                "round_candidates": r["round_number"]["candidates"],
                **{d: r[d]["value"] for d in ("round_state", "life_state", "camera_state")},
            }
            for r in seconds
        ],
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass  # No private URL, timestamps or Source paths in access logs.

        def do_HEAD(self) -> None:
            self.do_GET()

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            prefix = "/" + token
            if not parsed.path.startswith(prefix + "/"):
                self.send_error(404)
                return
            route = parsed.path[len(prefix) :]
            query = parse_qs(parsed.query)
            try:
                if route == "/video":
                    self.media(video)
                    return
                if route in {"/download.json", "/download.csv"}:
                    path = (
                        bundle_path
                        if route.endswith("json")
                        else (bundle_path.parent / "timeline_1s_PRIVATE.csv")
                    )
                    self.media(path)
                    return
                data: Any
                if route == "/":
                    payload, content_type = HTML.encode("utf-8"), "text/html; charset=utf-8"
                else:
                    if route == "/api/overview":
                        data = overview
                    elif route == "/api/second":
                        second = int(query["n"][0])
                        if not 0 <= second < len(seconds):
                            raise ValueError("Second outside recording")
                        data = seconds[second]
                    elif route == "/api/evidence":
                        data = bundle["observations"][query["id"][0]]
                    elif route == "/api/event":
                        data = bundle["events"][query["id"][0]]
                    elif route == "/api/evaluation":
                        data = read_json(bundle_path.parent / "evaluation_PRIVATE.json")
                    else:
                        self.send_error(404)
                        return
                    payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
                    content_type = "application/json; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)
            except (ValueError, KeyError, IndexError):
                self.send_error(400, "Invalid timeline query")
            except (BrokenPipeError, ConnectionResetError):
                pass

        def media(self, path: Path) -> None:
            size = path.stat().st_size
            try:
                start, end, status = byte_range(self.headers.get("Range"), size)
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(status)
            self.send_header(
                "Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            )
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Cache-Control", "no-store")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if self.command == "HEAD":
                return
            with path.open("rb") as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    block = stream.read(min(1024 * 1024, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.viewer_url = f"http://127.0.0.1:{server.server_port}/{token}/"  # type: ignore[attr-defined]
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    server = make_server(args.bundle, args.policy, port=args.port)
    print(server.viewer_url, flush=True)  # type: ignore[attr-defined]
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
