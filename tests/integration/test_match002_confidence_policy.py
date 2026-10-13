import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from test_fixture_validation import reseal, valid_pack
from test_pack_stage_assembly import PACK, setup

from scripts.e2e.assemble_pack_stage import main
from scripts.e2e.match002_confidence_evaluator_v1 import POLICY_VERSION, typed_confidence_failures
from scripts.e2e.validate_fixture import native_policy_schema_hash, validate

ROOT = Path(__file__).resolve().parents[2]


def original():
    spec = importlib.util.spec_from_file_location("original_confidence_policy", PACK /
                                                "tests/reference_evaluator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("value", [{}, {"ally_alive": 0}, {"weapon": 1,
                                                                  "score_ally": .9}])
def test_typed_maps_preserved_and_original_verdict_unchanged(value):
    base = original()
    schema = json.loads((ROOT / "schemas/round_package_schema_v2.json").read_text(encoding="utf-8"))
    trace = {"snapshots": [{"source_confidence": value}]}
    before = copy.deepcopy(trace)
    assert base._finite_confidence_failures(trace) == ["confidence:snapshots:0:source_confidence"]
    assert typed_confidence_failures(trace, base, schema) == []
    assert trace == before
    assert base._finite_confidence_failures(trace) == ["confidence:snapshots:0:source_confidence"]


@pytest.mark.parametrize("value", [.9, None, [], {"unknown": .9}, {"weapon": True},
                                  {"weapon": "0.9"}, {"weapon": -1}, {"weapon": 1.01},
                                  {"weapon": float("nan")}, {"weapon": float("inf")}])
def test_invalid_native_maps_rejected(value):
    schema = json.loads((ROOT / "schemas/round_package_schema_v2.json").read_text(encoding="utf-8"))
    assert typed_confidence_failures({"snapshots": [{"source_confidence": value}]},
                                     original(), schema) == [
                                         "confidence:snapshots:0:source_confidence"]


@pytest.mark.parametrize("value", [True, "0.9", -1, 1.1, float("nan"), float("inf"), {}])
def test_other_confidence_checks_remain_strict(value):
    schema = json.loads((ROOT / "schemas/round_package_schema_v2.json").read_text(encoding="utf-8"))
    trace = {"snapshots": [{"source_confidence": {}, "confidence": value}],
             "events": [{"source_confidence": value}]}
    assert typed_confidence_failures(trace, original(), schema) == [
        "confidence:events:0:source_confidence", "confidence:snapshots:0:confidence"]


def test_versioned_pack_adapter_is_hash_bound_and_keeps_all_other_verdicts(tmp_path, monkeypatch):
    # The synthetic fixture carries match_002 ID, not real source evidence.
    pack = valid_pack(tmp_path, monkeypatch)
    timeline, source, _ = (tmp_path / name for name in ("timeline", "source", "pack"))
    data = json.loads((timeline / "timeline_ground_truth_v3.json").read_text(encoding="utf-8"))
    data["fixture_id"] = "match_002"
    (timeline / "timeline_ground_truth_v3.json").write_text(json.dumps(data))
    output = tmp_path / "versioned"
    monkeypatch.setattr(sys, "argv", ["stage", "--timeline-stage", str(timeline),
                                     "--source-stage", str(source), "--canonical-pack", str(PACK),
                                     "--output", str(output),
                                     "--confidence-policy", POLICY_VERSION])
    main()
    assert validate(output, PACK)["formal_pack_completed"] is False
    assert (output / "tests/reference_evaluator_v3_base.py").read_bytes() == (
        PACK / "tests/reference_evaluator.py").read_bytes()
    spec = importlib.util.spec_from_file_location("policy_pack", output /
                                                "tests/reference_evaluator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assertions = json.loads((output / "tests/generated/e2e_assertions_v3.json").read_text(
        encoding="utf-8"))
    trace = {"snapshots": [{"source_confidence": {"weapon": .9}}]}
    old = original().evaluate(assertions, trace)
    assert module.evaluate(assertions, trace) == [
        failure for failure in old if failure != "confidence:snapshots:0:source_confidence"]
    (output / "tests/reference_evaluator.py").write_text("# tampered")
    reseal(output)
    with pytest.raises(ValueError, match="unauthorized confidence policy"):
        validate(output, PACK)
    assert validate(pack, PACK)["formal_pack_completed"] is False


def test_policy_cannot_be_used_for_match001(tmp_path, monkeypatch):
    timeline, _, _ = setup(tmp_path, monkeypatch)
    data = json.loads((timeline / "timeline_ground_truth_v3.json").read_text(encoding="utf-8"))
    data["fixture_id"] = "match_001"
    (timeline / "timeline_ground_truth_v3.json").write_text(json.dumps(data))
    monkeypatch.setattr(sys, "argv", sys.argv + ["--confidence-policy", POLICY_VERSION])
    with pytest.raises(ValueError, match="restricted to match_002"):
        main()


def test_additive_schema_compatibility_does_not_relax_dictionary_contract(tmp_path):
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    path = schema_dir / "round_package_schema_v2.json"
    path.write_bytes((ROOT / "schemas/round_package_schema_v2.json").read_bytes())
    assert len(native_policy_schema_hash(tmp_path, ROOT)) == 64
    data = json.loads(path.read_text(encoding="utf-8"))
    data["$defs"]["snapshot_source_confidence"]["additionalProperties"] = True
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="changed native dictionary Schema"):
        native_policy_schema_hash(tmp_path, ROOT)
