"""Download VALORANT reference images into a private, hash-indexed cache.

Run on a machine that can reach valorant-api.com (standard library only):

    python3 scripts/knowledge/fetch_reference_assets.py --out ~/Desktop/valorant_knowledge_cache

The cache is private: never commit it. The printed digest covers every
``url sha256`` pair, so two independent downloads of the same game version can
be compared without exchanging the images. ``--expected-digest`` makes the run
fail when the content differs from a pinned snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import ssl
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://valorant-api.com/v1/"
MEDIA = "https://media.valorant-api.com/"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "valorant-ai-coach-knowledge/1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return bytes(response.read())
    except (ssl.SSLError, urllib.error.URLError) as error:
        # Some macOS Python builds ship without CA certificates; curl uses the system store.
        if shutil.which("curl") is None:
            raise
        if isinstance(error, urllib.error.HTTPError):
            raise
        return subprocess.run(
            ["curl", "-sSfL", "--max-time", "60", url], check=True, capture_output=True
        ).stdout


def api(path: str) -> object:
    return json.loads(fetch(API + path).decode("utf-8"))["data"]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_") or "item"


def selection() -> tuple[dict[str, object], list[tuple[str, str, str, str]]]:
    version = api("version")
    agents = api("agents?isPlayableCharacter=true")
    weapons = api("weapons")
    maps = api("maps")
    items: list[tuple[str, str, str, str]] = []
    for agent in agents:  # type: ignore[union-attr]
        base = f"agents/{agent['uuid']}/"
        for variant in ("displayicon", "killfeedportrait", "minimapportrait"):
            items.append(("agent", agent["displayName"], variant, base + variant + ".png"))
        for ability in agent["abilities"]:
            if ability.get("displayIcon"):
                path = f"{base}abilities/{ability['slot'].lower()}/displayicon.png"
                items.append(("ability", agent["displayName"], ability["slot"], path))
    for weapon in weapons:  # type: ignore[union-attr]
        base = f"weapons/{weapon['uuid']}/"
        if weapon.get("displayIcon"):
            items.append(("weapon", weapon["displayName"], "displayicon", base + "displayicon.png"))
        if weapon.get("killStreamIcon"):
            path = base + "killstreamicon.png"
            items.append(("weapon", weapon["displayName"], "killstreamicon", path))
    for game_map in maps:  # type: ignore[union-attr]
        if game_map.get("tacticalDescription"):
            path = f"maps/{game_map['uuid']}/displayicon.png"
            items.append(("map", game_map["displayName"], "displayicon", path))
    return version, items  # type: ignore[return-value]


def digest(entries: list[dict[str, object]]) -> str:
    lines = sorted(f"{entry['url']} {entry['sha256']}" for entry in entries)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-digest")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    out = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    version, items = selection()

    def download(item: tuple[str, str, str, str]) -> dict[str, object]:
        kind, subject, variant, path = item
        data = fetch(MEDIA + path)
        relative = Path(kind) / slug(subject) / f"{slug(variant)}.png"
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {
            "kind": kind,
            "subject": subject,
            "variant": variant,
            "url": MEDIA + path,
            "path": relative.as_posix(),
            "length": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        entries = list(pool.map(download, items))
    content_digest = digest(entries)
    index = {
        "format": "valorant_reference_cache_v1",
        "game_version": version["version"],  # type: ignore[index]
        "branch": version["branch"],  # type: ignore[index]
        "source": "valorant_api_media",
        "content_digest": content_digest,
        "files": entries,
    }
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), "utf-8")
    print(f"files={len(entries)} bytes={sum(int(e['length']) for e in entries)}")  # type: ignore[call-overload]
    print(f"game_version={index['game_version']} content_digest={content_digest}")
    if args.expected_digest and args.expected_digest != content_digest:
        print("ERROR: content digest differs from the pinned snapshot", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
