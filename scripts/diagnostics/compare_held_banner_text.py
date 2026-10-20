"""Compare frozen matcher outputs to separately reviewed text; never qualify events."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def family(text: str) -> str:
    if text in {"unknown", "absent"}:
        return text
    if text == "WON" or text.startswith("WON "):
        return "WON"
    if text == "LOST" or text.startswith("LOST "):
        return "LOST"
    raise ValueError("explicit reviewed result text or abstention required")


def counts(expected: str, labels: list[str], measurements: list[dict]) -> dict:
    if expected not in {"WON", "LOST"} or len(labels) != len(measurements):
        raise ValueError("complete matching text inventory required")
    result = dict(positive_correct=0, positive_missing=0, negative_rejected=0,
                  negative_false_accept=0, unknown_unscored=0)
    for text, measurement in zip(labels, measurements, strict=True):
        score, threshold = measurement["score"], measurement["threshold"]
        if (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1
                or threshold != .90 or isinstance(threshold, bool)
                or not (measurement.get("presence") is True or measurement.get("presence") is None)
                or (measurement.get("presence") is True) != (score >= threshold)):
            raise ValueError("unchanged finite matcher score/floor required")
        label = family(text)
        if label == "unknown":
            result['unknown_unscored'] += 1
        elif label == expected:
            result['positive_correct' if measurement['presence'] else 'positive_missing'] += 1
        else:
            result['negative_false_accept' if measurement['presence'] else 'negative_rejected'] += 1
    return result


def compare(review_path: Path, labels_path: Path, measurement_path: Path,
            references_path: Path, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("new comparison receipt required")
    inputs = {p: sha256_file(p) for p in (
        review_path, labels_path, measurement_path, references_path, Path(__file__))}
    review, labels, measured, references = [json.loads(p.read_text(encoding="utf-8")) for p in (
        review_path, labels_path, measurement_path, references_path)]
    if (labels.get('kind') != 'human_held_banner_transcription_not_boundary_or_adoption'
            or labels.get('review_sha256') != inputs[review_path]
            or labels.get('measurement_sha256') != inputs[measurement_path]
            or labels.get('reference_transcription_sha256') != inputs[references_path]
            or not labels.get('trusted_reply_reference')
            or labels.get('production_adopted') is not False
            or measured.get('kind') != 'frozen_banner_measurement_not_qualification'
            or measured.get('candidates_reselected') is not False
            or len({r['frame_number'] for r in review['frames']}) != len(review['frames'])
            or not 1 <= len(review['frames']) <= 256
            or set(labels['transcriptions']) != {str(r['frame_number']) for r in review['frames']}
            or len({x['source_video_sha256'] for x in (review, labels, references)}
                   | {measured['source_sha256']}) != 1):
        raise ValueError('bound explicit human review and frozen measurement required')
    page = review_path.parent / 'index.html'
    if sha256_file(page) != review['review_html_sha256'] or (
            review['review_html_sha256'] != labels['review_html_sha256']):
        raise ValueError('review page changed')
    inputs[page] = sha256_file(page)
    indices, texts = [], []
    for row in review['frames']:
        index = row['held_index']
        if (type(index) is not int or not 0 <= index < len(measured['held_hashes'])
                or measured['held_hashes'][index] != row['source_image_sha256']):
            raise ValueError('held source image mismatch')
        path = review_path.parent / f"frame_{row['frame_number']:02d}.png"
        if sha256_file(path) != row['roi_sha256']:
            raise ValueError('review ROI changed')
        inputs[path] = sha256_file(path)
        indices.append(index)
        texts.append(labels['transcriptions'][str(row['frame_number'])])
    results = []
    for candidate in measured['candidates']:
        if len(candidate['held_measurements']) != len(measured['held_hashes']):
            raise ValueError('incomplete held measurements')
        expected = family(references['transcriptions'][candidate['candidate_id']])
        results.append({'candidate_id': candidate['candidate_id'], **counts(
            expected, texts, [candidate['held_measurements'][i] for i in indices])})
    if any(sha256_file(p) != h for p, h in inputs.items()):
        raise ValueError('comparison inputs changed')
    result = {'scope': 'reviewed_six_point_text_comparison_not_temporal_qualification',
              'reviewed_count': len(texts), 'candidates': results,
              'input_hashes': [inputs[p] for p in inputs],
              'candidate_reselection': False, 'events_generated': 0,
              'qualification_created': False, 'production_adopted': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('review', 'labels', 'measurement', 'references', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(args.review, args.labels, args.measurement,
                             args.references, args.output)))


if __name__ == '__main__':
    main()
