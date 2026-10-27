"""Private five-choice review; candidate centers are never human-center GT.

This loopback UI stores user-entered semantic categories only. Building or
serving it is not evidence that a human performed any reviews.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .development_learning_dataset import FrameRecord, SourceAcceptance, Split, _is_sha256
from .development_marker_features import _digest, _private_model_output

CATEGORIES = ("PLAYER", "DEATH_MARKER", "UI", "BACKGROUND", "UNKNOWN")
VISIBILITY = ("PREDICTION_BLIND", "PREDICTION_EXPOSED")


def _png(content: bytes) -> None:
    if (
        not isinstance(content, bytes)
        or not 33 <= len(content) <= 2 * 1024**2
        or not content.startswith(b"\x89PNG\r\n\x1a\n")
        or content[12:16] != b"IHDR"
    ):
        raise ValueError("Bounded local PNG asset required")
    width, height = struct.unpack(">II", content[16:24])
    if not 5 <= min(width, height) <= max(width, height) <= 1024:
        raise ValueError("Bounded PNG review dimensions required")


def _frame(raw: dict[str, Any]) -> FrameRecord:
    value = dict(raw)
    value["source_acceptance"] = SourceAcceptance(**value["source_acceptance"])
    value["split"] = Split(value["split"])
    value["frame_size_px"] = tuple(value["frame_size_px"])
    value["roi_xywh"] = tuple(value["roi_xywh"])
    result = FrameRecord(**value)
    result.validate()
    return result


def build_manifest(
    selection: dict[str, Any],
    images: dict[str, bytes],
    *,
    visibility: str = "PREDICTION_BLIND",
    synthetic: bool = False,
) -> dict[str, Any]:
    """Bind local PNG review assets to an unchanged, not-yet-reviewed queue."""
    if (
        type(synthetic) is not bool
        or visibility not in VISIBILITY
        or selection.get("mode") != "PROPOSED_REVIEW"
        or selection.get("ownership") != "UNKNOWN"
        or selection.get("formal_outputs") != 0
        or not 1 <= len(selection.get("selected", [])) <= 10
    ):
        raise ValueError("Bounded unqualified proposed-review selection required")
    # The selector fingerprints the full result before adding this one field.
    unbound = dict(selection)
    fingerprint = unbound.pop("selection_fingerprint", None)
    if fingerprint != _digest(unbound):
        raise ValueError("Review selection fingerprint mismatch")
    items = []
    for row in selection["selected"]:
        candidate = row["candidate"]
        frame = _frame(candidate["frame"])
        key = row["item_id"]
        if (
            candidate["annotation_status"] != "UNREVIEWED"
            or key not in images
            or not _is_sha256(key)
            or _digest(candidate) != key
            or frame.split not in {Split.SSL_TRAIN, Split.DEVELOPMENT_TRAIN}
        ):
            raise ValueError("Do not request already answered or evaluation observations")
        content = images[key]
        _png(content)
        items.append(
            {
                "item_id": key,
                "candidate": candidate,
                "channel": row["channel"],
                "png_sha256": hashlib.sha256(content).hexdigest(),
                "image_data_url": "data:image/png;base64,"
                + base64.b64encode(content).decode("ascii"),
            }
        )
    if len({item["item_id"] for item in items}) != len(items):
        raise ValueError("One review operation per selected item required")
    manifest = {
        "version": 1,
        "selection_fingerprint": fingerprint,
        "visibility": visibility,
        "dataset_kind": "SYNTHETIC_TEST" if synthetic else "DEVELOPMENT",
        "items": items,
        "center_verified": False,
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
    }
    manifest["manifest_fingerprint"] = _digest(manifest)
    return manifest


class SemanticReviewStore:
    """Append revisions; server supplies every source/ROI field automatically."""

    def __init__(self, manifest: dict[str, Any], output: Path) -> None:
        original = dict(manifest)
        fingerprint = original.pop("manifest_fingerprint", None)
        if (
            manifest.get("version") != 1
            or fingerprint != _digest(original)
            or manifest.get("visibility") not in VISIBILITY
            or manifest.get("dataset_kind") not in {"DEVELOPMENT", "SYNTHETIC_TEST"}
            or manifest.get("ownership") != "UNKNOWN"
            or manifest.get("formal_outputs") != 0
            or manifest.get("center_verified") is not False
            or not 1 <= len(manifest.get("items", [])) <= 10
        ):
            raise ValueError("Immutable private review manifest required")
        _private_model_output(output / "response.json")
        self.manifest = manifest
        self.items = {item["item_id"]: item for item in manifest["items"]}
        if len(self.items) != len(manifest["items"]):
            raise ValueError("Unique review IDs required")
        for item in self.items.values():
            frame = _frame(item["candidate"]["frame"])
            if (
                frame.split not in {Split.SSL_TRAIN, Split.DEVELOPMENT_TRAIN}
                or item["candidate"]["annotation_status"] != "UNREVIEWED"
                or not _is_sha256(item["item_id"])
                or _digest(item["candidate"]) != item["item_id"]
            ):
                raise ValueError("Only original unreviewed train-role crops permitted")
            if (
                not isinstance(item["image_data_url"], str)
                or not item["image_data_url"].startswith("data:image/png;base64,")
                or len(item["image_data_url"]) > 3 * 1024**2
            ):
                raise ValueError("Bounded local PNG data required")
            content = base64.b64decode(item["image_data_url"].split(",", 1)[1], validate=True)
            _png(content)
            if (
                not content.startswith(b"\x89PNG\r\n\x1a\n")
                or hashlib.sha256(content).hexdigest() != item["png_sha256"]
            ):
                raise ValueError("Review image bytes changed")
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.Lock()

    def _latest(self, item_id: str) -> Path:
        return self.output / f"review_{item_id}_latest.json"

    def _read_latest(self, key: str) -> dict[str, Any] | None:
        path = self._latest(key)
        if not path.is_file():
            return None
        if path.stat().st_size > 128 * 1024:
            raise ValueError("Bounded saved review required")
        content = path.read_bytes()
        row: dict[str, Any] = json.loads(content.decode("utf-8"))
        if not isinstance(row, dict):
            raise ValueError("Saved review object required")
        original = dict(row)
        digest = original.pop("response_sha256", None)
        if (
            digest != _digest(original)
            or row.get("item_id") != key
            or row.get("manifest_fingerprint") != self.manifest["manifest_fingerprint"]
            or row.get("semantic_label") not in CATEGORIES
            or row.get("label_origin")
            != (
                "synthetic_test"
                if self.manifest["dataset_kind"] == "SYNTHETIC_TEST"
                else "human_confirmed"
            )
            or row.get("human_center_verified") is not False
            or _digest(row.get("frame")) != _digest(self.items[key]["candidate"]["frame"])
            or type(row.get("revision")) is not int
            or not 1 <= row["revision"] <= 1024
        ):
            raise ValueError("Saved review binding or digest changed")
        revision = self.output / f"review_{key}_rev{row['revision']:04d}.json"
        if not revision.is_file() or revision.read_bytes() != content:
            raise ValueError("Saved immutable revision mismatch")
        return row

    def saved(self) -> dict[str, str]:
        result = {}
        for key in self.items:
            row = self._read_latest(key)
            if row is not None:
                result[key] = row["semantic_label"]
        return result

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        if (
            not isinstance(payload, dict)
            or set(payload) != {"manifest_fingerprint", "item_id", "label"}
            or payload["manifest_fingerprint"] != self.manifest["manifest_fingerprint"]
            or payload["item_id"] not in self.items
            or payload["label"] not in CATEGORIES
        ):
            raise ValueError("Exact manifest/item binding and one semantic category required")
        key = payload["item_id"]
        item = self.items[key]
        with self.lock:
            path = self._latest(key)
            previous = self._read_latest(key)
            if previous and previous["semantic_label"] == payload["label"]:
                return {
                    "saved": True,
                    "revision": previous["revision"],
                    "response_sha256": previous["response_sha256"],
                    "saved_count": len(self.saved()),
                }
            # An interrupted latest-file commit may leave a valid orphan revision.
            revisions = list(self.output.glob(f"review_{key}_rev*.json"))
            if len(revisions) >= 1024:
                raise ValueError("Bounded revision budget exhausted")
            next_revision = max((int(p.stem.rsplit("rev", 1)[1]) for p in revisions), default=0) + 1
            row = {
                "manifest_fingerprint": self.manifest["manifest_fingerprint"],
                "item_id": key,
                "semantic_label": payload["label"],
                "label_origin": (
                    "synthetic_test"
                    if self.manifest["dataset_kind"] == "SYNTHETIC_TEST"
                    else "human_confirmed"
                ),
                "dataset_kind": self.manifest["dataset_kind"],
                "review_visibility": self.manifest["visibility"],
                "queue_channel": item["channel"],
                "frame": item["candidate"]["frame"],
                "patch_sha256": item["candidate"]["patch_sha256"],
                "revision": next_revision,
                "supersedes_sha256": previous["response_sha256"] if previous else None,
                "recorded_at": datetime.now(UTC).isoformat(),
                "human_center_verified": False,
                "position_accuracy": "UNMEASURED",
                "scope": "semantic crop review only, not a human-center or ownership label",
                "ownership": "UNKNOWN",
                "formal_outputs": 0,
            }
            row["response_sha256"] = _digest(row)
            content = json.dumps(row, ensure_ascii=False, indent=2).encode("utf-8")
            revision = self.output / f"review_{key}_rev{row['revision']:04d}.json"
            with revision.open("xb") as stream:
                stream.write(content)
            temporary = self.output / f".{key}_{secrets.token_hex(8)}.tmp"
            try:
                with temporary.open("xb") as stream:
                    stream.write(content)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            return {
                "saved": True,
                "revision": row["revision"],
                "response_sha256": row["response_sha256"],
                "saved_count": len(self.saved()),
            }


def render_review(manifest: dict[str, Any], token: str, saved: dict[str, str]) -> str:
    """Blind pages omit predictions/reasons/channels from their serialized data."""
    exposed = manifest["visibility"] == "PREDICTION_EXPOSED"
    items = [
        {
            "item_id": item["item_id"],
            "image": item["image_data_url"],
            **({"predictions": item["candidate"]["teacher_labels"]} if exposed else {}),
        }
        for item in manifest["items"]
    ]
    data = json.dumps(
        {
            "items": items,
            "fingerprint": manifest["manifest_fingerprint"],
            "token": token,
            "saved": saved,
        },
        ensure_ascii=True,
    ).replace("<", "\\u003c")
    return HTML.replace("__DATA__", data).replace("__MODE__", manifest["visibility"])


def make_review_server(store: SemanticReviewStore, port: int = 0) -> ThreadingHTTPServer:
    """Loopback only, explicit host/origin/token, bounded request body, no files API."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Loopback port required")
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, body: bytes, kind: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; img-src data:; "
                "script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                "connect-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def _host(self) -> str:
            address = self.server.server_address
            if not isinstance(address, tuple):
                raise ValueError("Loopback internet socket required")
            return f"127.0.0.1:{address[1]}"

        def do_GET(self) -> None:
            if self.path != "/" or self.headers.get("Host") != self._host():
                self._reply(404, b"{}")
                return
            body = render_review(store.manifest, token, store.saved()).encode("utf-8")
            self._reply(200, body, "text/html")

        def do_POST(self) -> None:
            if (
                self.path != "/submit"
                or self.headers.get("Host") != self._host()
                or self.headers.get("Origin") != "http://" + self._host()
                or not hmac.compare_digest(self.headers.get("X-Review-Token", ""), token)
            ):
                self._reply(403, b"{}")
                return
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if not 0 < n <= 65536 or self.headers.get_content_type() != "application/json":
                    raise ValueError("Bounded JSON review required")
                result = store.save(json.loads(self.rfile.read(n).decode("utf-8")))
                self._reply(200, json.dumps(result).encode("utf-8"))
            except (ValueError, OSError, KeyError, TypeError):
                self._reply(400, b'{"saved":false}')

        def log_message(self, format: str, *args: Any) -> None:
            return

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


HTML = r"""<!doctype html><html lang="ja"><meta charset="utf-8">
<title>PRIVATE semantic review</title><style>
body{background:#171d25;color:#eee;font:16px system-ui;margin:24px;max-width:1000px}
section{border:1px solid #536274;padding:16px;margin:16px 0}
img{width:280px;image-rendering:pixelated}
button{font:inherit;padding:10px;margin:5px}output{display:block;margin:8px}.saved{color:#8f8}
</style><h1>PRIVATE — マーカー分類</h1><p>__MODE__。各領域を1回選ぶと自動保存します。
中心の再クリックは不要です。候補中心の正確さ・本人所有は確認対象ではありません。</p>
<main id="items"></main><script>
const data=__DATA__;
const names={PLAYER:'通常PLAYER',DEATH_MARKER:'死亡の×',UI:'UI',
 BACKGROUND:'背景',UNKNOWN:'判断不能'};
if(!data.token){let p=document.createElement('p');
 p.textContent='閲覧用プレビューです。分類は送信されません。';
 document.querySelector('#items').append(p);}
for(const [i,item] of data.items.entries()){
 const s=document.createElement('section'),h=document.createElement('h2');
 const img=document.createElement('img'),out=document.createElement('output');
 h.textContent='領域 '+(i+1);img.src=item.image;s.append(h,img);
 if(item.predictions){let p=document.createElement('p');
  p.textContent='機械の候補: '+item.predictions.join(' / ');s.append(p);}
 const writeSaved=label=>{out.textContent='保存済み: '+names[label];out.className='saved';};
 if(data.saved[item.item_id])writeSaved(data.saved[item.item_id]);
 let busy=false;const buttons=[];
 for(const [label,name] of Object.entries(names)){
  let b=document.createElement('button');b.type='button';b.textContent=name;buttons.push(b);
  b.disabled=!data.token;
  b.onclick=async()=>{if(busy||!data.token)return;busy=true;buttons.forEach(x=>x.disabled=true);
   out.textContent='保存中…';out.className='';
   try{let r=await fetch('/submit',{method:'POST',
    headers:{'Content-Type':'application/json','X-Review-Token':data.token},
    body:JSON.stringify({manifest_fingerprint:data.fingerprint,item_id:item.item_id,label})});
    let result=await r.json();if(!r.ok||!result.saved)throw Error('not saved');writeSaved(label);
   }catch(e){out.textContent='保存を確認できません。同じ分類を押して再試行してください。';}
   finally{busy=false;buttons.forEach(x=>x.disabled=false);}};
  s.append(b);
 }
 s.append(out);document.querySelector('#items').append(s);
}
</script></html>"""


def main() -> None:
    """Serve one previously prepared private manifest; no source video access."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--port", type=int, default=49377)
    args = parser.parse_args()
    _private_model_output(args.manifest)
    if not args.manifest.is_file() or args.manifest.stat().st_size > 24 * 1024**2:
        raise ValueError("Bounded private review manifest required")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    store = SemanticReviewStore(manifest, args.responses)
    server = make_review_server(store, args.port)
    print(f"Private semantic review: http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
