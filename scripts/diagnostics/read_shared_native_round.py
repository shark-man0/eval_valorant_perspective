"""Read sparse native DEVELOPMENT frames using a pinned HUD supplier checkout.

Run this script by absolute path with PYTHONPATH set to the pinned HUD checkout
and its src directory. It exports observations, never common game state or GT.
All profile/reference paths are explicit private arguments; no video discovery.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supplier", type=Path, required=True)
    parser.add_argument("--supplier-head", required=True)
    parser.add_argument("--acquisition", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--result-method", type=Path, required=True)
    parser.add_argument("--structural-bank", type=Path, required=True)
    parser.add_argument("--component-bindings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    actual_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=args.supplier, text=True, encoding="utf-8"
    ).strip()
    if actual_head != args.supplier_head:
        parser.error("Pinned HUD supplier head mismatch")
    if args.output.exists() or any((p / ".git").exists() for p in args.output.resolve().parents):
        parser.error("New PRIVATE output outside Git required")
    policy, acquired = load(args.policy), load(args.acquisition)
    if (
        acquired["policy_sha256"] != sha(args.policy)
        or acquired["version"] != "development_sparse_native_v1"
        or not acquired["source_bytes_verified_before_and_after"]
        or sha(Path(policy["manifest"])) != policy["manifest_sha256"]
        or sha(Path(policy["allocation"])) != policy["allocation_sha256"]
    ):
        parser.error("Frozen Source/acquisition policy mismatch")
    sources = {r["source_sha256"]: r for r in load(Path(policy["manifest"]))["records"]}
    for entry in acquired["frames"]:
        sample = entry["sample"]
        source = sources[sample["source_sha256"]]
        if (
            sample["source_sha256"] not in policy["allowed_source_sha256s"]
            or sample["source_sha256"] in policy.get("protected_source_sha256s", [])
            or source["video_id"] != sample["source_id"]
            or source["status"] != "accepted"
            or source["split"] != "DEVELOPMENT"
            or source["exposure"] != "DEVELOPMENT"
        ):
            parser.error("Protected or unaccepted source")
    modules = {
        key: importlib.import_module(name)
        for key, name in {
            "cv": "cv2",
            "layout": "valorant_ai_coach.hud.layout",
            "analyzers": "valorant_ai_coach.hud.analyzers",
            "templates": "valorant_ai_coach.hud.templates",
            "background": "scripts.diagnostics.score_border_background",
            "result": "scripts.diagnostics.diagnose_result_text",
            "structure": "scripts.diagnostics.diagnose_hud_transfer",
            "scope": "scripts.diagnostics.hud_scope_structure",
        }.items()
    }
    # A mixed ambient checkout must not silently become the supplier implementation.
    for module in modules.values():
        file = getattr(module, "__file__", None)
        if (
            module is not modules["cv"]
            and file
            and not Path(file).resolve().is_relative_to(args.supplier.resolve())
        ):
            parser.error("PYTHONPATH must select the pinned supplier checkout")
    cv = modules["cv"]
    cv.setNumThreads(1)
    layout = modules["layout"].HudLayout.load(args.layout)
    analyzer = modules["analyzers"].RealHudAnalyzer(args.layout, template_profile_path=args.profile)
    scores, score_binding = modules["background"].score_readers(
        args.profile, foreground="white200_rowcontrast_v1"
    )
    method = modules["result"].load_method(args.result_method)
    text = modules["templates"].TesseractTextReader(language="eng", psm=7)
    receipt = load(args.structural_bank)
    references = []
    root = args.structural_bank.parent / "structural_references"
    for item in receipt["references"]["top_match_bar"]:
        profile = modules["templates"].HudTemplateProfile(
            root / "not_exported.templates.json", item["profile"]
        )
        spec = item["profile"]["anchors"]["top_match_bar"]
        template = cv.imread(str(profile.resolve_asset(spec["template"])), 0)
        mask = cv.imread(str(profile.resolve_asset(spec["mask"])), 0)
        references.append((template, modules["scope"].outline_mask(template, mask)))
    bindings = load(args.component_bindings)["bindings"]
    if modules["scope"].reference_fingerprint(references) != bindings["references_sha256"]:
        parser.error("Frozen reference bytes mismatch")
    reader_files = {
        key: sha(Path(str(module.__file__))) for key, module in modules.items() if key != "cv"
    }
    reader_fp = digest(
        {
            "supplier": actual_head,
            "files": reader_files,
            "layout": sha(args.layout),
            "profile": sha(args.profile),
            "result_method": sha(args.result_method),
            "reference_bank": sha(args.structural_bank),
            "score_binding": score_binding,
        }
    )
    bindings = {**bindings, "reader_profile_sha256": reader_fp}
    records = []
    began = time.perf_counter()
    for index, entry in enumerate(acquired["frames"]):
        sample, path = entry["sample"], Path(entry["path"])
        image = cv.imread(str(path))
        if (
            sha(path) != sample["acquired_frame_sha256"]
            or image is None
            or hashlib.sha256(image.tobytes()).hexdigest() != sample["native_pixel_sha256"]
        ):
            raise ValueError("Native observation pixels changed")
        row = {
            "source_id": sample["source_id"],
            "source_sha256": sample["source_sha256"],
            "epoch": sample["native_epoch"],
            "tick": sample["native_pts_tick"],
            "time_base": sample["native_time_base"],
            "encoded_sha256": sample["acquired_frame_sha256"],
            "pixel_sha256": sample["native_pixel_sha256"],
            "geometry_consistent": False,
            "path": str(path),
        }
        for name, field in (
            ("ally_score", "ally_score"),
            ("enemy_score", "enemy_score"),
            ("round_timer", "timer"),
        ):
            a, b, c, d = layout.normalized_roi(name).pixel_bounds(image.shape[1], image.shape[0])
            reader = analyzer.readers[name] if name == "round_timer" else scores[name]
            value = reader.read(image, image[b:d, a:c])
            row[field] = {
                "value": value.value,
                "confidence": value.confidence,
                "sources": list(value.sources),
            }
        crop, region = modules["result"].text_region(image, layout, method)
        value = None if crop is None else text.read(image, crop)
        word = (
            None
            if value is None
            else modules["result"].accepted_result(value.value, value.confidence)
        )
        row["result"] = {
            "value": word,
            "confidence": 0 if value is None else value.confidence,
            "raw_text": None if value is None else value.value,
            "region": region,
        }
        row["buy_phase"] = analyzer.template_profile.detect_signals(image, layout, context={}).get(
            "buy_phase_template"
        )
        row["component_geometry"] = modules["scope"].component_geometry(
            row, image, layout, references, bindings
        )
        source = sources[sample["source_sha256"]]
        frame = {
            k: sample[k]
            for k in (
                "source_sha256",
                "acquisition_id",
                "native_epoch",
                "native_pts_tick",
                "native_time_base",
                "frame_size_px",
            )
        }
        frame.update(
            frame_sha256=sample["acquired_frame_sha256"],
            pixel_sha256=sample["native_pixel_sha256"],
            roi_xywh=[0, 0, *sample["frame_size_px"]],
            extraction_fingerprint=sha(args.acquisition),
            exposure_fingerprint=digest(
                {"purpose": "bounded_development_shared_timeline", "policy": sha(args.policy)}
            ),
            leakage_group_id=source["physical_match_id"],
            split="DEVELOPMENT_TRAIN",
            source_acceptance={
                "accepted": True,
                "manifest_sha256": policy["manifest_sha256"],
                "allocation_sha256": policy["allocation_sha256"],
                "trusted_manifest_sha256": policy["manifest_sha256"],
                "trusted_allocation_sha256": policy["allocation_sha256"],
            },
        )
        records.append(
            {
                "frame_contract": frame,
                "row": row,
                "reader_fingerprint": reader_fp,
                "profile_fingerprint": sha(args.profile),
            }
        )
        if (index + 1) % 20 == 0:
            print(
                json.dumps({"read": index + 1, "elapsed_sec": time.perf_counter() - began}),
                flush=True,
            )
    result = {
        "version": "hud_supplier_replay_input_v1",
        "owner_frames": [],
        "round_frames": records,
        "boundary_hints": [],
        "supplier_head": actual_head,
        "reader_fingerprint": reader_fp,
        "reader_file_sha256s": reader_files,
        "reader_cli_sha256": sha(Path(__file__)),
        "elapsed_sec": time.perf_counter() - began,
        "formal_outputs": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(
        os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8"
    ) as stream:
        json.dump(result, stream, allow_nan=False)
    print(
        json.dumps(
            {
                "observations": len(records),
                "elapsed_sec": result["elapsed_sec"],
                "formal_outputs": 0,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
