"""Loopback review of a frozen DEVELOPMENT packet with private human labels."""

from __future__ import annotations

import hashlib
import json
import math
import mimetypes
import os
import secrets
import shutil
import subprocess
from datetime import UTC, datetime
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlsplit

import cv2
import numpy as np

from valorant_ai_coach.video.native import decoded_source_ticks

from .evidence import digest, freeze_native_sample, native_time
from .replay import SourcePolicy, file_sha, read_json
from .viewer import byte_range

PACKET_VERSION = "development_timeline_review_packet_v1"
ANSWER_VERSION = "development_timeline_human_review_v1"
YES_NO = ["YES", "NO", "UNKNOWN"]
FIELDS: dict[str, tuple[str, list[str] | None]] = {
    "round_state": ("画像のRound状態", ["BUY", "ACTIVE", "ENDED", "INTERMISSION", "UNKNOWN"]),
    "life_state": ("画像の本人の生存状態", ["ALIVE", "DEAD", "DOWNED", "UNKNOWN"]),
    "camera_state": ("画像のカメラ", ["SELF", "SPECTATOR", "REMOTE", "UNKNOWN"]),
    "round_number": ("画像のRound番号", None),
    "round_starts_in_window": ("区間内のRound開始回数", ["0", "1", "2", "UNKNOWN"]),
    "round_ends_in_window": ("区間内のRound終了回数", ["0", "1", "2", "UNKNOWN"]),
    "death_in_window": ("区間内の本人死亡", YES_NO),
    "spectator_transition_in_window": ("区間内の観戦切替", ["ENTER", "EXIT", "BOTH", "NONE",
                                                           "UNKNOWN"]),
    "return_in_window": ("区間内の本人視点への復帰", YES_NO),
    "result_layout": ("画像の結果画面", ["CENTRAL_OVERLAY", "POSTMATCH_SCOREBOARD",
                                       "ROUND_RESULT", "NONE", "UNKNOWN"]),
    "result_word": ("画像の結果表示", ["VICTORY", "DEFEAT", "WON", "LOST", "NONE", "UNKNOWN"]),
    "match_end_in_window": ("区間内の試合終了", YES_NO),
    "source_round": ("対象イベントの前のRound番号", None),
    "destination_round": ("対象イベントの後のRound番号", None),
    "visibility": ("画像の判読状況", ["CLEAR", "OCCLUDED", "UNKNOWN"]),
    "round_start_display_second": ("開始が画面で分かった秒", None),
    "round_end_display_second": ("終了が画面で分かった秒", None),
}

HTML = """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>共通タイムラインのレビュー</title>
<style>
body{font:15px system-ui;margin:24px;background:#101820;color:#e8edf2}
main{display:grid;grid-template-columns:minmax(360px,1.2fr) minmax(340px,1fr);gap:24px}
img,video{width:100%;background:#000;max-height:55vh;object-fit:contain}
button,select,input{padding:7px;margin:4px;background:#263645;color:#fff;border:1px solid #718495}
label{display:block}label>input[type=checkbox]{margin-right:10px}
pre{white-space:pre-wrap;overflow-wrap:anywhere}details{margin:12px 0}
small,#status{color:#a8c6db}button:disabled{opacity:.55}
@media(max-width:780px){main{display:block}}
</style>
<h1>共通タイムラインのレビュー</h1>
<p id="progress" aria-live="polite"></p>
<button id="prev">前へ</button><button id="next">次へ</button>
<button id="pending">未回答へ</button>
<label>確認する場面 <select id="pick"></select></label>
<main><section>
<h2 id="scene"></h2><p id="window"></p>
<button id="still">確認画像</button><button id="clip">前後の元動画を再生</button>
<img id="frame" alt="確認する元フレーム"><video id="video" controls hidden></video>
<p id="mediaStatus" aria-live="polite"></p>
<details><summary>AIの推定と対象イベント</summary><pre id="prediction"></pre></details>
</section><section><h2>確認できた項目</h2>
<label>確認者 <input id="reviewer" maxlength="80" autocomplete="off"></label>
<div id="fields"></div><details><summary>その他の項目</summary><div id="extra"></div></details>
<label><input id="checked" type="checkbox">回答した項目を画像または元動画で確認しました</label>
<button id="save" disabled>保存して次へ</button><p id="status" aria-live="polite"></p>
</section></main>
<script>
const el=id=>document.getElementById(id);
const video=el('video'), picture=el('frame');
let overview, item, index=0, revision=0, verified=false;
async function api(route, options){
  const response=await fetch(route,options);
  if(!response.ok)throw Error(await response.text());
  return response.json();
}
function state(){
  el('progress').textContent=overview.reviewed+' / '+overview.items.length+'場面を確認済み';
  el('save').disabled=!verified;
}
function field(name, schema, existing){
  const label=document.createElement('label');
  label.textContent=schema[0]+' ';
  const input=document.createElement(schema[1]?'select':'input');
  input.id='label-'+name; input.dataset.field=name;
  if(schema[1]){
    input.add(new Option('未回答',''));
    for(const value of schema[1])input.add(new Option(value==='UNKNOWN'?'判別不能':value,value));
  }else input.placeholder=name.endsWith('_second')?'秒（任意）':'番号または UNKNOWN';
  input.value=existing??'';
  label.append(input);return label;
}
async function load(next){
  const request=++revision;
  verified=false;state();video.pause();video.hidden=true;picture.hidden=false;
  const selected=Math.max(0,Math.min(overview.items.length-1,next));
  const loaded=await api('api/item?n='+selected);
  if(request!==revision)return;
  index=selected;item=loaded;el('pick').value=String(index);el('checked').checked=false;
  el('scene').textContent=item.source_alias+' · '+item.source_video_time.toFixed(2)+'秒';
  el('window').textContent=item.context_start_seconds.toFixed(2)+'〜'+
    item.context_end_seconds.toFixed(2)+'秒の区間';
  el('prediction').textContent=JSON.stringify(item.prediction,null,2);
  el('fields').replaceChildren();el('extra').replaceChildren();
  for(const [key,schema] of Object.entries(item.fields))
    el(item.focus.includes(key)?'fields':'extra').append(field(key,schema,item.labels[key]));
  el('mediaStatus').textContent='元フレームを照合中';
  picture.onload=()=>{if(request===revision){verified=true;
    el('mediaStatus').textContent='元フレーム照合済み';state()}};
  picture.onerror=()=>{if(request===revision)el('mediaStatus').textContent=
    '元フレームを照合できません。次の場面へ進めます。'};
  picture.src='image?n='+index;
}
function displayError(error){el('status').textContent=error.message}
el('still').onclick=()=>{video.pause();video.hidden=true;picture.hidden=false};
el('clip').onclick=()=>{
  if(!item)return;
  picture.hidden=true;video.hidden=false;
  const begin=()=>{
    const offset=video.seekable.length?video.seekable.start(0):0;
    video.currentTime=offset+item.context_start_seconds;
    video.play().catch(displayError);
  };
  const src='video?n='+index;
  if(video.getAttribute('src')===src&&video.readyState>0)begin();
  else{video.onloadedmetadata=begin;video.src=src}
};
video.ontimeupdate=()=>{
  if(!item||video.hidden)return;
  const offset=video.seekable.length?video.seekable.start(0):0;
  if(video.currentTime-offset>=item.context_end_seconds)video.pause();
};
el('prev').onclick=()=>load(index-1).catch(displayError);
el('next').onclick=()=>load(index+1).catch(displayError);
el('pending').onclick=()=>load(overview.next_pending??index).catch(displayError);
el('pick').onchange=e=>load(Number(e.target.value)).catch(displayError);
el('save').onclick=async()=>{
  try{
    if(!el('checked').checked)throw Error('確認欄にチェックを入れてください');
    const reviewer=el('reviewer').value.trim();
    const labels=Object.fromEntries([...document.querySelectorAll('[data-field]')]
      .map(e=>[e.dataset.field,e.value.trim()]).filter(([,v])=>v));
    overview=await api('api/answer',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({review_id:item.review_id,reviewer,labels,confirmed:true})});
    sessionStorage.setItem('reviewer',reviewer);
    el('status').textContent='保存しました';
    await load(overview.next_pending??index);
  }catch(error){displayError(error)}
};
(async()=>{
  overview=await api('api/overview');
  el('reviewer').value=sessionStorage.getItem('reviewer')||'';
  overview.items.forEach((row,i)=>el('pick').add(new Option(row,i)));
  await load(overview.next_pending??0);
})().catch(displayError);
</script>"""


class ReviewSession:
    def __init__(self, packet_path: Path, answer_path: Path) -> None:
        packet = read_json(packet_path)
        if packet.get("version") != PACKET_VERSION or packet.get("formal_outputs") != 0:
            raise ValueError("Development review packet required")
        self.packet_sha = file_sha(packet_path)
        self.items: list[dict[str, Any]] = packet["items"]
        self.by_id = {row["review_id"]: row for row in self.items}
        if not self.items or len(self.by_id) != len(self.items):
            raise ValueError("Nonempty packet with unique review IDs required")
        self.sources = packet["sources"]
        self.policies = {
            key: SourcePolicy(read_json(Path(value["policy_path"])))
            for key, value in self.sources.items()
        }
        for row in self.items:
            key = row["source_sha256"]
            sample = row["sample"]
            if freeze_native_sample(sample) != sample or sample["source_sha256"] != key:
                raise ValueError("Exact native sample binding required")
            self.policies[key].admit(sample)
            if self.policies[key].allowed[key]["physical_match_id"] != row["physical_match_id"]:
                raise ValueError("Physical match binding mismatch")
            origin = Fraction(self.sources[key]["native_origin_seconds"])
            seconds = float(native_time(sample) - origin)
            if not (
                math.isclose(seconds, row["source_video_time"], abs_tol=1e-6)
                and 0 <= row["context_start_seconds"] <= seconds <= row["context_end_seconds"]
                and row["context_end_seconds"] - row["context_start_seconds"] <= 90
            ):
                raise ValueError("Review window does not bind the exact point")
        self.answer_path = answer_path.resolve()
        if any((parent / ".git").exists() for parent in self.answer_path.parents):
            raise ValueError("Review answers must be stored outside Git")
        self.answer_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        self.media_lock = Lock()
        self.verified_sources: dict[str, tuple[int, int]] = {}
        self.image_hashes: dict[str, str] = {}
        self.answers: dict[str, dict[str, Any]] = {}
        if self.answer_path.exists():
            with self.answer_path.open(encoding="utf-8") as stream:
                for line in stream:
                    row = json.loads(line)
                    if (
                        row["packet_sha256"] != self.packet_sha
                        or row["review_id"] not in self.by_id
                    ):
                        raise ValueError("Answers are bound to a different packet")
                    self.answers[row["review_id"]] = row

    def video_path(self, row: dict[str, Any]) -> Path:
        key = row["source_sha256"]
        path = Path(self.policies[key].allowed[key]["managed_path"])
        with self.media_lock:
            stat = path.stat()
            identity = stat.st_size, stat.st_mtime_ns
            if self.verified_sources.get(key) != identity:
                if file_sha(path) != key:
                    raise ValueError("Original recording changed")
                self.verified_sources[key] = identity
        return path

    def native_image(self, row: dict[str, Any]) -> bytes:
        source = self.video_path(row)
        sample = row["sample"]
        tick = sample["native_pts_tick"]
        base = Fraction(sample["native_time_base"])
        decoder = shutil.which("ffmpeg")
        if decoder is None:
            raise ValueError("FFmpeg is required for exact review images")
        result = subprocess.run(
            [decoder, "-hide_banner", "-loglevel", "info", "-threads", "1",
             "-noaccurate_seek", "-seek_timestamp", "1", "-ss",
             str(float(max(Fraction(0), tick * base - 2))), "-copyts", "-i", str(source),
             "-an", "-sn", "-dn", "-vf", f"select=eq(pts\\,{tick}),showinfo",
             "-frames:v", "1", "-fps_mode", "passthrough", "-threads", "1",
             "-c:v", "png", "-f", "image2pipe", "pipe:1"],
            capture_output=True, check=True, timeout=45,
        )
        pixels = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
        if (
            decoded_source_ticks(result.stderr.decode("utf-8", errors="replace"), base) != (tick,)
            or pixels is None
            or hashlib.sha256(pixels.tobytes()).hexdigest() != sample["native_pixel_sha256"]
        ):
            raise ValueError("Decoded review frame does not match the frozen native sample")
        with self.lock:
            self.image_hashes[row["review_id"]] = hashlib.sha256(result.stdout).hexdigest()
        return result.stdout

    def overview(self) -> dict[str, Any]:
        with self.lock:
            return {
                "items": [f"{r['source_alias']} · {r['source_video_time']:.2f}秒"
                          for r in self.items],
                "reviewed": len(self.answers),
                "next_pending": next((i for i, r in enumerate(self.items)
                                      if r["review_id"] not in self.answers), None),
            }

    def item(self, index: int) -> dict[str, Any]:
        row = self.items[index]
        event = row.get("target_event")
        fields = {
            k: FIELDS[k] for k in row["review_fields"]
            if k in FIELDS and (event or k not in {"source_round", "destination_round"})
        }
        focus = row.get(
            "focus_fields", ["round_state", "life_state", "camera_state", "round_number"]
        )
        estimates = row["current_prediction"]
        return {
            **{k: row[k] for k in ("review_id", "source_alias", "source_video_time",
                                  "context_start_seconds", "context_end_seconds")},
            "fields": fields,
            "focus": focus,
            "labels": self.answers.get(row["review_id"], {}).get("labels", {}),
            "prediction": {
                **{k: value["value"] for k, value in estimates.items()},
                "target_event": {k: event[k] for k in ("kind", "lower_timestamp",
                                                        "upper_timestamp")} if event else None,
                "events": [{k: e[k] for k in ("kind", "lower_timestamp", "upper_timestamp")}
                           for e in row["event_candidates"]],
            },
        }

    def save(self, payload: dict[str, Any]) -> None:
        row = self.by_id[payload["review_id"]]
        reviewer = payload.get("reviewer")
        labels = payload.get("labels")
        if (
            payload.get("confirmed") is not True
            or not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 80
            or not isinstance(labels, dict) or not labels
        ):
            raise ValueError("Explicit reviewer, confirmation and labels required")
        for key, value in labels.items():
            if key not in row["review_fields"] or key not in FIELDS or not isinstance(value, str):
                raise ValueError("Unexpected review field")
            allowed = FIELDS[key][1]
            if key in {"source_round", "destination_round"} and not row.get("target_event"):
                raise ValueError("Round membership requires a specified event")
            if allowed is not None and value not in allowed:
                raise ValueError("Unknown review option")
            if allowed is None and key.endswith("_second"):
                second = float(value)
                if not row["context_start_seconds"] <= second <= row["context_end_seconds"]:
                    raise ValueError("Display boundary outside the review window")
            elif allowed is None and value != "UNKNOWN" and (
                not value.isascii() or not value.isdecimal() or len(value) > 2
                or not 1 <= int(value) <= 99
            ):
                raise ValueError("Round number or UNKNOWN required")
        with self.lock:
            image_hash = self.image_hashes.get(row["review_id"])
            if image_hash is None:
                raise ValueError("Exact review image must be verified first")
            previous = self.answers.get(row["review_id"])
            record = {
                "version": ANSWER_VERSION, "origin": "human_local_review",
                "confirmation_status": "CONFIRMED_WITHIN_REVIEW_SCOPE",
                "packet_sha256": self.packet_sha, "review_id": row["review_id"],
                "sample": row["sample"], "image_sha256": image_hash, "reviewer": reviewer.strip(),
                "recorded_at": datetime.now(UTC).isoformat(), "labels": labels,
                "physical_match_id": row["physical_match_id"],
                "comparison_split": row["comparison_split"],
                "context_seconds": [row["context_start_seconds"], row["context_end_seconds"]],
                "target_event": row.get("target_event"), "label_scope": row["label_scope"],
                "supersedes": previous["answer_sha256"] if previous else None, "formal_outputs": 0,
            }
            record["answer_sha256"] = digest(record)
            with os.fdopen(os.open(self.answer_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600),
                           "a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            self.answers[row["review_id"]] = record


def make_review_server(
    packet_path: Path, answer_path: Path, *, port: int = 0
) -> ThreadingHTTPServer:
    session = ReviewSession(packet_path, answer_path)
    token = secrets.token_urlsafe(24)
    prefix = "/" + token + "/"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def payload(self, data: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def respond_json(self, value: dict[str, Any]) -> None:
            self.payload(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                         "application/json; charset=utf-8")

        def do_HEAD(self) -> None:
            self.do_GET()

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if not parsed.path.startswith(prefix):
                self.send_error(404)
                return
            try:
                route = parsed.path[len(prefix):]
                if route == "":
                    self.payload(HTML.encode("utf-8"), "text/html; charset=utf-8")
                elif route == "api/overview":
                    self.respond_json(session.overview())
                elif route in {"api/item", "image", "video"}:
                    index = int(parse_qs(parsed.query)["n"][0])
                    if not 0 <= index < len(session.items):
                        raise ValueError("Invalid review index")
                    row = session.items[index]
                    if route == "api/item":
                        self.respond_json(session.item(index))
                    elif route == "image":
                        self.payload(session.native_image(row), "image/png")
                    else:
                        self.media(session.video_path(row))
                else:
                    self.send_error(404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except (ValueError, KeyError, IndexError, OSError, subprocess.SubprocessError):
                self.send_error(400, "Review evidence unavailable")

        def do_POST(self) -> None:
            if self.path != prefix + "api/answer":
                self.send_error(404)
                return
            if self.headers.get("Origin") != f"http://127.0.0.1:{server.server_port}":
                self.send_error(403)
                return
            try:
                length = int(self.headers["Content-Length"])
                if (
                    not 0 < length <= 32_768
                    or self.headers.get_content_type() != "application/json"
                ):
                    raise ValueError("Bounded JSON required")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Object required")
                session.save(payload)
                self.respond_json(session.overview())
            except (ValueError, KeyError, TypeError, OSError):
                self.send_error(400, "Invalid review answer")

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
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "video/mp4")
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
                while remaining:
                    chunk = stream.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.viewer_url = f"http://127.0.0.1:{server.server_port}{prefix}"  # type: ignore[attr-defined]
    return server
