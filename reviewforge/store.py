"""SQLite 持久化层：版本与批注的存取。"""

from __future__ import annotations

import json
import sqlite3


_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
    version INTEGER PRIMARY KEY,
    lines TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    created_version INTEGER NOT NULL,
    anchor_version INTEGER NOT NULL,
    anchor_line INTEGER NOT NULL
);
"""


class Store:
    """封装单个评审数据库的读写。每个数据库只对应一个固定路径的文本文件。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("store is closed")
        return self._conn

    def get_file_path(self) -> str | None:
        row = self._require_conn().execute(
            "SELECT value FROM meta WHERE key = 'file_path'"
        ).fetchone()
        return None if row is None else row[0]

    def set_file_path(self, file_path: str) -> None:
        conn = self._require_conn()
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('file_path', ?)",
            (file_path,),
        )
        conn.commit()

    def current_version(self) -> int:
        row = self._require_conn().execute(
            "SELECT COALESCE(MAX(version), 0) FROM versions"
        ).fetchone()
        return int(row[0])

    def insert_version(self, lines: list[str]) -> int:
        conn = self._require_conn()
        version = self.current_version() + 1
        conn.execute(
            "INSERT INTO versions (version, lines) VALUES (?, ?)",
            (version, json.dumps(lines, ensure_ascii=False)),
        )
        return version

    def get_lines(self, version: int) -> list[str]:
        row = self._require_conn().execute(
            "SELECT lines FROM versions WHERE version = ?", (version,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown version: {version}")
        return list(json.loads(row[0]))

    def insert_annotation(self, text: str, version: int, line: int) -> int:
        conn = self._require_conn()
        cur = conn.execute(
            "INSERT INTO annotations (text, created_version, anchor_version, anchor_line)"
            " VALUES (?, ?, ?, ?)",
            (text, version, version, line),
        )
        return int(cur.lastrowid)

    def update_anchor(self, annotation_id: int, version: int, line: int) -> None:
        self._require_conn().execute(
            "UPDATE annotations SET anchor_version = ?, anchor_line = ? WHERE id = ?",
            (version, line, annotation_id),
        )

    def list_annotations(self) -> list[tuple[int, str, int, int]]:
        """返回 (id, text, anchor_version, anchor_line)，按创建顺序排列。"""
        rows = self._require_conn().execute(
            "SELECT id, text, anchor_version, anchor_line FROM annotations ORDER BY id"
        ).fetchall()
        return [(int(r[0]), str(r[1]), int(r[2]), int(r[3])) for r in rows]

    def commit(self) -> None:
        self._require_conn().commit()
