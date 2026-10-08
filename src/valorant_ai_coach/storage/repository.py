from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import suppress
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

LOGGER = logging.getLogger(__name__)


class RepositoryError(RuntimeError):
    pass


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(cast(Any, value))
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"JSONに変換できません: {type(value).__name__}")


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=_json_default)


def _decode(value: str | None, fallback: Any = None) -> Any:
    return json.loads(value) if value else fallback


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class SQLiteRepository:
    """SQLite persistence with versioned, transactional schema migrations."""

    schema_version = 1

    def __init__(self, path: Path, clips_dir: Path | None = None) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clips_dir = Path(clips_dir).expanduser().resolve() if clips_dir else None
        self._migrate()
        if os.name != "nt":
            with suppress(OSError):
                self.path.chmod(0o600)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _migrate(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            # sqlite3.executescript() commits before running its script.  That made an
            # interrupted first launch capable of leaving tables behind without the
            # migration marker.  Keep every DDL statement in one explicit transaction;
            # IF NOT EXISTS also repairs databases left by that older behaviour.
            statements = (
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS matches (
                        match_id TEXT PRIMARY KEY,
                        source_video_path TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        created_at TEXT NOT NULL,
                        metadata_json TEXT NOT NULL DEFAULT '{}'
                    )""",
                """CREATE TABLE IF NOT EXISTS round_packages (
                        match_id TEXT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
                        round_no INTEGER NOT NULL CHECK(round_no >= 1),
                        package_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(match_id, round_no)
                    )""",
                """CREATE TABLE IF NOT EXISTS evaluations (
                        evaluation_id TEXT PRIMARY KEY,
                        match_id TEXT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
                        round_no INTEGER,
                        primary_rule_id TEXT NOT NULL,
                        label TEXT NOT NULL CHECK(label IN ('good', 'improve', 'unscored')),
                        confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                        clip_id TEXT,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )""",
                """CREATE INDEX IF NOT EXISTS idx_evaluations_match_round
                    ON evaluations(match_id, round_no, created_at)""",
                """CREATE TABLE IF NOT EXISTS clips (
                        clip_id TEXT PRIMARY KEY,
                        evaluation_id TEXT NOT NULL
                            REFERENCES evaluations(evaluation_id) ON DELETE CASCADE,
                        file_path TEXT NOT NULL,
                        start_sec REAL NOT NULL CHECK(start_sec >= 0),
                        end_sec REAL NOT NULL CHECK(end_sec > start_sec),
                        duration_sec REAL NOT NULL CHECK(duration_sec > 0),
                        created_at TEXT NOT NULL
                    )""",
                """CREATE TABLE IF NOT EXISTS analysis_jobs (
                        match_id TEXT PRIMARY KEY REFERENCES matches(match_id) ON DELETE CASCADE,
                        status TEXT NOT NULL,
                        checkpoint_json TEXT NOT NULL DEFAULT '{}',
                        updated_at TEXT NOT NULL
                    )""",
            )
            connection.execute("BEGIN IMMEDIATE")
            try:
                for statement in statements:
                    connection.execute(statement)
                row = connection.execute(
                    "SELECT MAX(version) AS version FROM schema_migrations"
                ).fetchone()
                current = int(row["version"] or 0)
                if current > self.schema_version:
                    raise RepositoryError(
                        "データベースのschema versionが新しすぎます"
                    )
                if current < 1:
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES(1, ?)",
                        (_utc_now(),),
                    )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @staticmethod
    def _require_id(value: str, name: str) -> str:
        normalized = str(value).strip()
        if not normalized or len(normalized) > 200:
            raise ValueError(f"{name}は1〜200文字で指定してください")
        return normalized

    def create_match(
        self,
        match_id: str,
        source_video_path: str | Path,
        metadata: dict[str, Any] | None = None,
        status: str = "pending",
    ) -> dict[str, Any]:
        identifier = self._require_id(match_id, "match_id")
        source = str(Path(source_video_path).expanduser().resolve())
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO matches(
                       match_id, source_video_path, status, created_at, metadata_json
                   )
                   VALUES(?, ?, ?, ?, ?)
                   ON CONFLICT(match_id) DO UPDATE SET
                     source_video_path=excluded.source_video_path,
                     status=excluded.status,
                     metadata_json=excluded.metadata_json""",
                (identifier, source, str(status), now, _encode(metadata or {})),
            )
        result = self.get_match(identifier)
        assert result is not None
        return result

    def reset_match_analysis(self, match_id: str) -> None:
        """Atomically clear prior derived state while preserving the match identity."""
        identifier = self._require_id(match_id, "match_id")
        orphan_candidates: set[Path] = set()
        referenced_after_reset: set[Path] = set()
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM matches WHERE match_id=?", (identifier,)
            ).fetchone() is None:
                raise KeyError(f"matchがありません: {identifier}")
            orphan_candidates = {
                Path(row["file_path"]).expanduser().resolve()
                for row in connection.execute(
                    """SELECT c.file_path FROM clips AS c JOIN evaluations AS e
                       ON e.evaluation_id=c.evaluation_id WHERE e.match_id=?""",
                    (identifier,),
                ).fetchall()
            }
            connection.execute("DELETE FROM round_packages WHERE match_id=?", (identifier,))
            connection.execute("DELETE FROM evaluations WHERE match_id=?", (identifier,))
            connection.execute("DELETE FROM analysis_jobs WHERE match_id=?", (identifier,))
            referenced_after_reset = {
                Path(row["file_path"]).expanduser().resolve()
                for row in connection.execute("SELECT file_path FROM clips").fetchall()
            }
        if self.clips_dir is not None:
            # The database transaction is the logical reset.  Physical file cleanup
            # happens afterwards and must not turn a successful reset into an error.
            self._remove_unreferenced_clip_files(orphan_candidates, referenced_after_reset)

    def delete_match(self, match_id: str) -> None:
        """Delete one match transactionally, then best-effort its unshared clips.

        Frame/evidence files live under the pipeline's data directory and are removed
        by ``MatchAnalysisPipeline.delete_match``.  This repository method owns only
        DB rows and clip files rooted in ``clips_dir``.
        """

        identifier = self._require_id(match_id, "match_id")
        orphan_candidates: set[Path] = set()
        referenced_after_delete: set[Path] = set()
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM matches WHERE match_id=?", (identifier,)
            ).fetchone() is None:
                raise KeyError(f"matchがありません: {identifier}")
            orphan_candidates = {
                Path(row["file_path"]).expanduser().resolve()
                for row in connection.execute(
                    """SELECT c.file_path FROM clips AS c JOIN evaluations AS e
                       ON e.evaluation_id=c.evaluation_id WHERE e.match_id=?""",
                    (identifier,),
                ).fetchall()
            }
            connection.execute("DELETE FROM matches WHERE match_id=?", (identifier,))
            referenced_after_delete = {
                Path(row["file_path"]).expanduser().resolve()
                for row in connection.execute("SELECT file_path FROM clips").fetchall()
            }
        self._remove_unreferenced_clip_files(orphan_candidates, referenced_after_delete)

    def update_match_status(self, match_id: str, status: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE matches SET status = ? WHERE match_id = ?",
                (str(status), self._require_id(match_id, "match_id")),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"matchがありません: {match_id}")

    def save_round_package(self, package: dict[str, Any]) -> None:
        match_id = self._require_id(package.get("match_id", ""), "match_id")
        round_no = int(package.get("round_no", 0))
        if round_no < 1:
            raise ValueError("round_noは1以上で指定してください")
        source = package.get("source_video", {}).get("path", "")
        with self._connect() as connection:
            if (
                connection.execute("SELECT 1 FROM matches WHERE match_id=?", (match_id,)).fetchone()
                is None
            ):
                if not source:
                    raise KeyError(f"matchを先に作成してください: {match_id}")
                connection.execute(
                    """INSERT INTO matches(
                           match_id, source_video_path, status, created_at
                       ) VALUES(?, ?, ?, ?)""",
                    (match_id, str(source), "analyzing", _utc_now()),
                )
            connection.execute(
                """INSERT INTO round_packages(match_id, round_no, package_json, updated_at)
                   VALUES(?, ?, ?, ?)
                   ON CONFLICT(match_id, round_no) DO UPDATE SET
                     package_json=excluded.package_json, updated_at=excluded.updated_at""",
                (match_id, round_no, _encode(package), _utc_now()),
            )

    def save_analysis_result(self, payload: dict[str, Any]) -> None:
        match_id = self._require_id(payload.get("match_id", ""), "match_id")
        round_value = payload.get("round_no")
        round_no = int(round_value) if round_value is not None else None
        if round_no is not None and round_no < 1:
            raise ValueError("round_noは1以上で指定してください")
        evaluations = payload.get("evaluations", [])
        if not isinstance(evaluations, list):
            raise ValueError("evaluationsは配列で指定してください")
        prepared: list[tuple[str, str, str, float, Any, str]] = []
        seen_ids: set[str] = set()
        for item in evaluations:
            if not isinstance(item, dict):
                raise ValueError("evaluationはobjectで指定してください")
            evaluation_id = self._require_id(item.get("evaluation_id", ""), "evaluation_id")
            if evaluation_id in seen_ids:
                raise ValueError(f"evaluation_idが重複しています: {evaluation_id}")
            seen_ids.add(evaluation_id)
            rule_id = self._require_id(item.get("primary_rule_id", ""), "primary_rule_id")
            label = str(item.get("label", ""))
            confidence = float(item.get("confidence", 0.0))
            if label not in {"good", "improve", "unscored"}:
                raise ValueError(f"不正な評価ラベル: {label}")
            if not 0 <= confidence <= 1:
                raise ValueError(f"confidenceが範囲外です: {confidence}")
            raw_clip_id = item.get("clip_id")
            clip_id = (
                self._require_id(str(raw_clip_id), "clip_id")
                if raw_clip_id is not None
                else None
            )
            prepared.append((evaluation_id, rule_id, label, confidence, clip_id, _encode(item)))
        orphan_candidates: set[Path] = set()
        referenced_after_save: set[Path] = set()
        with self._connect() as connection:
            if (
                connection.execute("SELECT 1 FROM matches WHERE match_id=?", (match_id,)).fetchone()
                is None
            ):
                raise KeyError(f"matchを先に作成してください: {match_id}")
            if round_no is None:
                old_clip_rows = connection.execute(
                    """SELECT c.file_path FROM clips AS c JOIN evaluations AS e
                       ON e.evaluation_id=c.evaluation_id
                       WHERE e.match_id=? AND e.round_no IS NULL""",
                    (match_id,),
                ).fetchall()
            else:
                old_clip_rows = connection.execute(
                    """SELECT c.file_path FROM clips AS c JOIN evaluations AS e
                       ON e.evaluation_id=c.evaluation_id
                       WHERE e.match_id=? AND e.round_no=?""",
                    (match_id, round_no),
                ).fetchall()
            orphan_candidates = {
                Path(row["file_path"]).expanduser().resolve() for row in old_clip_rows
            }
            if prepared:
                placeholders = ",".join("?" for _ in prepared)
                conflicts = connection.execute(
                    f"""SELECT evaluation_id, match_id, round_no FROM evaluations
                        WHERE evaluation_id IN ({placeholders})""",  # noqa: S608
                    [item[0] for item in prepared],
                ).fetchall()
                cross_match = [row for row in conflicts if row["match_id"] != match_id]
                if cross_match:
                    ids = ", ".join(str(row["evaluation_id"]) for row in cross_match)
                    raise ValueError(f"別matchで使用済みのevaluation_idです: {ids}")
                cross_round = [row for row in conflicts if row["round_no"] != round_no]
                if cross_round:
                    ids = ", ".join(str(row["evaluation_id"]) for row in cross_round)
                    raise ValueError(f"別roundで使用済みのevaluation_idです: {ids}")
            for evaluation_id, rule_id, label, confidence, clip_id, encoded in prepared:
                connection.execute(
                    """INSERT INTO evaluations(
                           evaluation_id, match_id, round_no, primary_rule_id, label,
                           confidence, clip_id, payload_json, created_at
                       ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(evaluation_id) DO UPDATE SET
                         match_id=excluded.match_id, round_no=excluded.round_no,
                         primary_rule_id=excluded.primary_rule_id, label=excluded.label,
                         confidence=excluded.confidence, clip_id=excluded.clip_id,
                         payload_json=excluded.payload_json""",
                    (
                        evaluation_id,
                        match_id,
                        round_no,
                        rule_id,
                        label,
                        confidence,
                        clip_id,
                        encoded,
                        _utc_now(),
                    ),
                )
                if clip_id is None:
                    connection.execute(
                        "DELETE FROM clips WHERE evaluation_id=?", (evaluation_id,)
                    )
                else:
                    connection.execute(
                        "DELETE FROM clips WHERE evaluation_id=? AND clip_id!=?",
                        (evaluation_id, str(clip_id)),
                    )
            if prepared:
                placeholders = ",".join("?" for _ in prepared)
                round_clause = "round_no = ?" if round_no is not None else "round_no IS NULL"
                parameters: list[Any] = [match_id]
                if round_no is not None:
                    parameters.append(round_no)
                parameters.extend(item[0] for item in prepared)
                connection.execute(
                    f"""DELETE FROM evaluations WHERE match_id = ? AND {round_clause}
                           AND evaluation_id NOT IN ({placeholders})""",  # noqa: S608
                    parameters,
                )
            elif round_no is not None:
                connection.execute(
                    "DELETE FROM evaluations WHERE match_id = ? AND round_no = ?",
                    (match_id, round_no),
                )
            else:
                connection.execute(
                    "DELETE FROM evaluations WHERE match_id = ? AND round_no IS NULL",
                    (match_id,),
                )
            referenced_after_save = {
                Path(row["file_path"]).expanduser().resolve()
                for row in connection.execute("SELECT file_path FROM clips").fetchall()
            }
        self._remove_unreferenced_clip_files(orphan_candidates, referenced_after_save)

    def save_clip(
        self,
        clip_id: str,
        evaluation_id: str,
        file_path: str | Path,
        start_sec: float,
        end_sec: float,
        duration_sec: float,
    ) -> dict[str, Any]:
        identifier = self._require_id(clip_id, "clip_id")
        evaluation = self._require_id(evaluation_id, "evaluation_id")
        clip_path = Path(file_path).expanduser().resolve()
        if self.clips_dir is not None and not clip_path.is_relative_to(self.clips_dir):
            raise ValueError("クリップの保存先が許可されたディレクトリ外です")
        if not clip_path.is_file() or clip_path.stat().st_size <= 0:
            raise ValueError("保存するクリップファイルが存在しないか空です")
        start = float(start_sec)
        end = float(end_sec)
        duration = float(duration_sec)
        if start < 0 or end <= start or duration <= 0:
            raise ValueError("クリップの時間範囲が不正です")
        old_path: Path | None = None
        referenced_after_save: set[Path] = set()
        with self._connect() as connection:
            old_row = connection.execute(
                "SELECT evaluation_id, file_path FROM clips WHERE clip_id=?", (identifier,)
            ).fetchone()
            if old_row is not None:
                if old_row["evaluation_id"] != evaluation:
                    raise ValueError(
                        "別evaluationで使用済みのclip_idです: "
                        f"{identifier}"
                    )
                old_path = Path(old_row["file_path"]).expanduser().resolve()
            connection.execute(
                """INSERT INTO clips(clip_id, evaluation_id, file_path, start_sec, end_sec,
                                     duration_sec, created_at)
                   VALUES(?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(clip_id) DO UPDATE SET
                     evaluation_id=excluded.evaluation_id, file_path=excluded.file_path,
                     start_sec=excluded.start_sec, end_sec=excluded.end_sec,
                     duration_sec=excluded.duration_sec, created_at=excluded.created_at""",
                (identifier, evaluation, str(clip_path), start, end, duration, _utc_now()),
            )
            referenced_after_save = {
                Path(row["file_path"]).expanduser().resolve()
                for row in connection.execute("SELECT file_path FROM clips").fetchall()
            }
        if old_path is not None and old_path != clip_path:
            self._remove_unreferenced_clip_files({old_path}, referenced_after_save)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM clips WHERE clip_id=?", (identifier,)
            ).fetchone()
        assert row is not None
        return dict(row)

    def assert_clip_id_available(self, clip_id: str, evaluation_id: str) -> None:
        """Reject a clip ID owned by another evaluation before any writer touches it."""

        identifier = self._require_id(clip_id, "clip_id")
        evaluation = self._require_id(evaluation_id, "evaluation_id")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT evaluation_id FROM clips WHERE clip_id=?", (identifier,)
            ).fetchone()
        if row is not None and row["evaluation_id"] != evaluation:
            raise ValueError(f"別evaluationで使用済みのclip_idです: {identifier}")

    def _remove_unreferenced_clip_files(
        self, candidates: set[Path], referenced_paths: set[Path]
    ) -> None:
        if self.clips_dir is None:
            return
        for path in candidates:
            if (
                path not in referenced_paths
                and path.is_relative_to(self.clips_dir)
                and path.is_file()
            ):
                try:
                    path.unlink()
                except OSError as exc:
                    LOGGER.warning(
                        "Unreferenced clip cleanup failed after database commit: %s (%s)",
                        path,
                        exc,
                    )

    def get_match(self, match_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM matches WHERE match_id=?", (match_id,)
            ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["metadata"] = _decode(value.pop("metadata_json"), {})
        return value

    def list_matches(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM matches ORDER BY created_at DESC, match_id"
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            value["metadata"] = _decode(value.pop("metadata_json"), {})
            result.append(value)
        return result

    def list_evaluations(
        self, match_id: str, include_unscored: bool = True
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM evaluations WHERE match_id = ?"
        parameters: tuple[Any, ...] = (match_id,)
        if not include_unscored:
            sql += " AND label != 'unscored'"
        sql += " ORDER BY round_no, created_at, evaluation_id"
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            payload = _decode(value.pop("payload_json"), {})
            payload.setdefault("evaluation_id", value["evaluation_id"])
            payload.setdefault("match_id", value["match_id"])
            payload.setdefault("round_no", value["round_no"])
            payload["created_at"] = value["created_at"]
            result.append(payload)
        return result

    def list_round_evaluations(self, match_id: str, round_no: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM evaluations WHERE match_id=? AND round_no=?
                   ORDER BY created_at, evaluation_id""",
                (self._require_id(match_id, "match_id"), int(round_no)),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            value = dict(row)
            payload = _decode(value.pop("payload_json"), {})
            payload.setdefault("evaluation_id", value["evaluation_id"])
            result.append(payload)
        return result

    def list_round_packages(self, match_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT package_json FROM round_packages WHERE match_id=? ORDER BY round_no",
                (match_id,),
            ).fetchall()
        return [_decode(row["package_json"], {}) for row in rows]

    def get_round_package(self, match_id: str, round_no: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT package_json FROM round_packages WHERE match_id=? AND round_no=?",
                (self._require_id(match_id, "match_id"), int(round_no)),
            ).fetchone()
        return _decode(row["package_json"], {}) if row is not None else None

    def list_clips(self, match_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT c.* FROM clips AS c JOIN evaluations AS e
                   ON e.evaluation_id = c.evaluation_id WHERE e.match_id = ?
                   ORDER BY c.created_at, c.clip_id""",
                (match_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_clip(self, clip_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM clips WHERE clip_id=?",
                (self._require_id(clip_id, "clip_id"),),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_match_result(self, match_id: str) -> dict[str, Any] | None:
        match = self.get_match(match_id)
        if match is None:
            return None
        evaluations = self.list_evaluations(match_id)
        clips_by_id = {row["clip_id"]: row for row in self.list_clips(match_id)}
        for item in evaluations:
            clip_id = item.get("clip_id")
            item["clip"] = clips_by_id.get(clip_id) if clip_id else None
        return {
            "match": match,
            "evaluations": evaluations,
            "good_count": sum(item.get("label") == "good" for item in evaluations),
            "improve_count": sum(item.get("label") == "improve" for item in evaluations),
            "unscored_count": sum(item.get("label") == "unscored" for item in evaluations),
        }

    def save_job_checkpoint(self, match_id: str, status: str, checkpoint: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO analysis_jobs(match_id, status, checkpoint_json, updated_at)
                   VALUES(?, ?, ?, ?)
                   ON CONFLICT(match_id) DO UPDATE SET status=excluded.status,
                     checkpoint_json=excluded.checkpoint_json, updated_at=excluded.updated_at""",
                (match_id, str(status), _encode(checkpoint), _utc_now()),
            )

    def get_job_checkpoint(self, match_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM analysis_jobs WHERE match_id=?", (match_id,)
            ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["checkpoint"] = _decode(value.pop("checkpoint_json"), {})
        return value
