"""Non-video persisted-result features.

No label generation, video I/O or modification of canonical evaluation payloads.
"""

from __future__ import annotations

import csv
import html
import json
import math
import os
import re
import sqlite3
import tempfile
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from valorant_ai_coach.storage.repository import SQLiteRepository

_LABELS = ("good", "improve", "unscored")
_FEEDBACK = ("valid", "inappropriate", "pending")
_PRIVATE = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{8,}|(?:[A-Za-z]:[\\/]|/(?:home|users|mnt|tmp)/)[^\s,;'\"<>]+)"
)


def _redact(text: Any) -> str:
    return _PRIVATE.sub("[非公開]", str(text if text is not None else ""))


def _safe_cell(value: Any) -> str:
    text = _redact(value)
    # Spreadsheet formula injection, including whitespace/control-character prefixes.
    return "'" + text if text.lstrip("\ufeff\t\r\n ").startswith(("=", "+", "-", "@")) else text


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


class NonVideoFeatures:
    """SQLite read model and independent extension tables.

    Extension tables are migrated atomically without touching version 1 canonical
    evaluation tables or their schema marker. Foreign keys cascade on match removal.
    """

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository
        self.path = repository.path
        self._migrate()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self.repository._connect() as connection:
            yield connection

    def _migrate(self) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS non_video_migrations (
                version INTEGER PRIMARY KEY, installed_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS evaluation_feedback (
                evaluation_id TEXT PRIMARY KEY REFERENCES evaluations(evaluation_id)
                  ON DELETE CASCADE,
                match_id TEXT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
                verdict TEXT NOT NULL CHECK(verdict IN ('valid','inappropriate','pending')),
                memo TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS api_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                feature TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cache_hit INTEGER NOT NULL DEFAULT 0,
                repair_attempt INTEGER NOT NULL DEFAULT 0,
                retry_attempt INTEGER NOT NULL DEFAULT 0)""")
            db.execute("CREATE INDEX IF NOT EXISTS nv_usage_date ON api_usage_events(recorded_at)")
            db.execute(
                "CREATE INDEX IF NOT EXISTS nv_feedback_match ON evaluation_feedback(match_id)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS nv_evals_rule ON evaluations(primary_rule_id,label)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS nv_matches_date ON matches(created_at)")
            db.execute(
                "INSERT OR IGNORE INTO non_video_migrations VALUES(1, ?)",
                (datetime.now(UTC).isoformat(),),
            )

    def search(
        self,
        *,
        match_id: str = "",
        start: str = "",
        end: str = "",
        rule: str = "",
        category_rules: tuple[str, ...] = (),
        label: str = "",
        keyword: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Stable, paginated, fully parameterized filtering on persisted evaluations."""
        if label and label not in _LABELS:
            raise ValueError("未対応の評価ラベル")
        if not (1 <= limit <= 500 and offset >= 0):
            raise ValueError("ページング範囲が不正です")
        conditions: list[str] = []
        params: list[Any] = []
        if match_id:
            conditions.append("e.match_id=?")
            params.append(match_id)
        if start:
            conditions.append("m.created_at>=?")
            params.append(start)
        if end:
            conditions.append("m.created_at<?")
            params.append(end)
        if rule:
            conditions.append("e.primary_rule_id=?")
            params.append(rule)
        if category_rules:
            conditions.append(f"e.primary_rule_id IN ({','.join('?' for _ in category_rules)})")
            params.extend(category_rules)
        if label:
            conditions.append("e.label=?")
            params.append(label)
        if keyword:
            escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append("e.payload_json LIKE ? ESCAPE '\\'")
            params.append(f"%{escaped}%")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = (
            "SELECT e.evaluation_id,e.match_id,e.round_no,e.primary_rule_id,"
            "e.label,e.confidence,e.payload_json,m.created_at,m.status "
            "FROM evaluations e JOIN matches m ON m.match_id=e.match_id"
            + where +
            " ORDER BY m.created_at DESC,e.match_id,e.round_no,e.created_at,e.evaluation_id"
            " LIMIT ? OFFSET ?"
        )
        with self._connect() as db:
            rows = db.execute(sql, (*params, limit, offset)).fetchall()
        return [
            {
                **{key: value for key, value in dict(row).items() if key != "payload_json"},
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def summarize(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        labels = Counter(row["label"] for row in rows)
        rules = Counter(row["primary_rule_id"] for row in rows)
        matches = {row["match_id"] for row in rows}
        incomplete = {row["match_id"] for row in rows if row["status"] != "completed"}
        scored = labels["good"] + labels["improve"]
        return {
            "match_count": len(matches),
            "evaluable_match_count": len(matches - incomplete),
            "incomplete_match_count": len(incomplete),
            "counts": {label: labels[label] for label in _LABELS},
            "good_share_of_scored": labels["good"] / scored if scored else None,
            "by_rule": dict(sorted(rules.items())),
            "by_day": dict(sorted(Counter(
                str(row["created_at"])[:10] for row in rows
            ).items())),
        }

    def statistics(self, *, start: str = "", end: str = "", rule: str = "",
                   category_rules: tuple[str, ...] = ()) -> dict[str, Any]:
        """Aggregate in SQL: bounded memory even with thousands of saved evaluations."""
        predicates: list[str] = []
        params: list[Any] = []
        if start:
            predicates.append("m.created_at>=?")
            params.append(start)
        if end:
            predicates.append("m.created_at<?")
            params.append(end)
        if rule:
            predicates.append("e.primary_rule_id=?")
            params.append(rule)
        if category_rules:
            predicates.append(
                f"e.primary_rule_id IN ({','.join('?' for _ in category_rules)})"
            )
            params.extend(category_rules)
        base = (
            " FROM evaluations e JOIN matches m ON e.match_id=m.match_id"
            + (" WHERE " + " AND ".join(predicates) if predicates else "")
        )
        with self._connect() as db:
            count_rows = db.execute(
                "SELECT e.label,COUNT(*) as amount" + base +
                " GROUP BY e.label", params
            ).fetchall()
            rule_rows = db.execute(
                "SELECT e.primary_rule_id,COUNT(*) as amount" + base +
                " GROUP BY e.primary_rule_id", params
            ).fetchall()
            day_rows = db.execute(
                "SELECT substr(m.created_at,1,10) as day,COUNT(*) as amount" + base +
                " GROUP BY substr(m.created_at,1,10)", params
            ).fetchall()
            improve_base = base + (" AND " if predicates else " WHERE ") + "e.label='improve'"
            improve_rows = db.execute(
                "SELECT e.primary_rule_id,COUNT(*) as amount" + improve_base +
                " GROUP BY e.primary_rule_id", params
            ).fetchall()
            evaluated_rows = db.execute(
                "SELECT DISTINCT e.match_id,m.status" + base, params
            ).fetchall()
            matches = db.execute(
                "SELECT match_id,status FROM matches WHERE "
                "(?='' OR created_at>=?) AND (?='' OR created_at<?)",
                (start, start, end, end),
            ).fetchall()
        labels = {row["label"]: int(row["amount"]) for row in count_rows}
        good, improve = labels.get("good", 0), labels.get("improve", 0)
        scored = good + improve
        seen = {row["match_id"] for row in evaluated_rows}
        return {
            "match_count": len(matches),
            "evaluable_match_count": sum(
                row["status"] == "completed" for row in evaluated_rows
            ),
            "incomplete_match_count": sum(
                row["status"] != "completed" for row in matches
            ),
            "matches_without_evaluations": sum(
                row["match_id"] not in seen for row in matches
            ),
            "counts": {label: labels.get(label, 0) for label in _LABELS},
            "good_share_of_scored": good / scored if scored else None,
            "by_rule": dict(sorted(
                (row["primary_rule_id"], int(row["amount"])) for row in rule_rows
            )),
            "by_day": dict(sorted(
                (row["day"], int(row["amount"])) for row in day_rows
            )),
            "by_improve_rule": dict(sorted(
                (row["primary_rule_id"], int(row["amount"])) for row in improve_rows
            )),
        }

    def compare(self, left: str, right: str) -> dict[str, Any]:
        if left == right:
            raise ValueError("異なる2試合を選択してください")
        result: dict[str, Any] = {}
        for key in (left, right):
            match = self.repository.get_match(key)
            if match is None:
                raise KeyError(f"matchが存在しません: {key}")
            rows: list[dict[str, Any]] = []
            offset = 0
            while True:
                page = self.search(match_id=key, limit=500, offset=offset)
                rows.extend(page)
                if len(page) < 500:
                    break
                offset += len(page)
            values = self.summarize(rows)
            values["status"] = match["status"]
            values["match_id"] = key
            result[key] = values
        return result

    def report(
        self, match_id: str, rule_categories: Mapping[str, str] | None = None
    ) -> dict[str, Any]:
        result = self.repository.get_match_result(match_id)
        if result is None:
            raise KeyError(f"matchがありません: {match_id}")
        match = result["match"]
        allowed = (
            "evaluation_id", "round_no", "primary_rule_id", "related_rule_ids",
            "label", "confidence", "title", "situation", "reason", "improvement",
            "concept_tags", "fact_refs", "evidence", "evidence_range",
            "missing_information", "unscored_reason_code", "decision_source",
        )
        evaluations = [
            {
                **{key: self._clean_value(e.get(key)) for key in allowed},
                "category": self._clean_value(
                    (rule_categories or {}).get(str(e.get("primary_rule_id")), "Other")
                ),
            }
            for e in result["evaluations"]
        ]
        return {
            "export_format_version": 1,
            "match": {
                "match_id": match_id,
                "recorded_at": match["created_at"],
                "status": match["status"],
                "source_video_filename": _redact(
                    str(match["source_video_path"]).replace("\\", "/").rsplit("/", 1)[-1]
                ),
            },
            "counts": {label: result[label + "_count"] for label in _LABELS},
            "evaluations": evaluations,
        }

    @classmethod
    def _clean_value(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _redact(value)
        if isinstance(value, list):
            return [cls._clean_value(part) for part in value]
        if isinstance(value, dict):
            return {key: cls._clean_value(part) for key, part in value.items()}
        if isinstance(value, tuple):
            return [cls._clean_value(part) for part in value]
        return value

    def export_report(
        self, match_id: str, destination: Path, fmt: str,
        rule_categories: Mapping[str, str] | None = None,
    ) -> None:
        if fmt not in {"json", "csv", "html"}:
            raise ValueError("形式はjson/csv/htmlのみ")
        record = self.report(match_id, rule_categories)
        if fmt == "json":
            content = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        elif fmt == "csv":
            import io
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            fields = ("match_id", "round_no", "evaluation_id", "primary_rule_id",
                      "category", "label", "confidence", "reason", "improvement",
                      "evidence_range", "unscored_reason_code")
            writer.writerow(fields)
            for item in record["evaluations"]:
                writer.writerow([
                    _safe_cell(record["match"]["match_id"])
                    if field == "match_id" else
                    _safe_cell(json.dumps(item.get(field), ensure_ascii=False)
                               if isinstance(item.get(field), (dict, list))
                               else item.get(field) if item.get(field) is not None else "")
                    for field in fields
                ])
            content = stream.getvalue()
        else:
            fields = ("round_no", "primary_rule_id", "category", "title",
                      "label", "confidence", "reason", "improvement", "fact_refs", "evidence",
                      "evidence_range", "unscored_reason_code")
            trs = []
            for item in record["evaluations"]:
                cells = "".join(
                    "<td>" + html.escape(str(item.get(f) if item.get(f) is not None else "")) +
                    "</td>" for f in fields
                )
                trs.append("<tr>" + cells + "</tr>")
            content = (
                "<!doctype html><html lang='ja'><meta charset='utf-8'>"
                "<title>VALORANT AI Coach 評価</title><body>"
                "<h1>試合 " + html.escape(match_id) + "</h1>"
                "<p>GOOD: {good} / IMPROVE: {improve} / UNSCORED: {unscored}</p>"
                "<table border='1'><thead><tr>".format(**record["counts"])
                + "".join("<th>" + html.escape(f) + "</th>" for f in fields)
                + "</tr></thead><tbody>" + "".join(trs) + "</tbody></table></body></html>"
            )
        _atomic_write(Path(destination), content)

    def feedback(self, evaluation_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM evaluation_feedback WHERE evaluation_id=?", (evaluation_id,)
            ).fetchone()
        return dict(row) if row else None

    def save_feedback(self, evaluation_id: str, verdict: str, memo: str) -> None:
        if verdict not in _FEEDBACK or len(memo) > 4000:
            raise ValueError("フィードバックの値が不正です")
        now = datetime.now(UTC).isoformat()
        with self._connect() as db:
            # Determine identity only from canonical DB, never from user-controlled IDs.
            existing = db.execute(
                "SELECT match_id FROM evaluations WHERE evaluation_id=?", (evaluation_id,)
            ).fetchone()
            if not existing:
                raise KeyError("評価が存在しません")
            db.execute(
                """INSERT INTO evaluation_feedback
                   (evaluation_id,match_id,verdict,memo,created_at,updated_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(evaluation_id) DO UPDATE SET
                   verdict=excluded.verdict,memo=excluded.memo,
                   updated_at=excluded.updated_at""",
                (evaluation_id, existing["match_id"], verdict, memo, now, now),
            )

    def delete_feedback(self, evaluation_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM evaluation_feedback WHERE evaluation_id=?", (evaluation_id,))

    def record_usage(self, feature: str, model: str, status: str,
                     input_tokens: int | None = None, output_tokens: int | None = None,
                     cache_hit: bool = False, repair_attempt: int = 0,
                     retry_attempt: int = 0) -> None:
        def valid_token(value: int | None) -> bool:
            return value is None or (type(value) is int and 0 <= value <= 10**12)
        if not valid_token(input_tokens) or not valid_token(output_tokens):
            raise ValueError("token数が不正です")
        with self._connect() as db:
            db.execute(
                """INSERT INTO api_usage_events(
                  recorded_at,feature,model,status,input_tokens,output_tokens,
                  cache_hit,repair_attempt,retry_attempt) VALUES(?,?,?,?,?,?,?,?,?)""",
                (datetime.now(UTC).isoformat(), feature[:80], model[:100],
                 status[:40], input_tokens, output_tokens, int(cache_hit),
                 max(0, repair_attempt), max(0, retry_attempt)),
            )

    def usage(self, price_table: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        prices = price_table or {}
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM api_usage_events ORDER BY id DESC LIMIT 2000"
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["total_tokens"] = (
                item["input_tokens"] + item["output_tokens"]
                if item["input_tokens"] is not None and item["output_tokens"] is not None
                else None
            )
            price = prices.get(item["model"])
            item["estimated_cost"] = None
            if (isinstance(price, dict) and
                    item["input_tokens"] is not None and
                    item["output_tokens"] is not None):
                try:
                    amount = (item["input_tokens"] * float(price["input_per_million"]) +
                              item["output_tokens"] * float(price["output_per_million"])) / 1e6
                    if math.isfinite(amount) and amount >= 0:
                        item["estimated_cost"] = amount
                        item["currency"] = str(price.get("currency", "USD"))
                except (ValueError, TypeError, KeyError):
                    pass
            result.append(item)
        return result
