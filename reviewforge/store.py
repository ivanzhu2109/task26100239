"""SQLite 持久化层。

三张表：
- reviews(file_path)：每个评审绑定一个固定路径的文本文件；
- rounds(review_id, round_no, lines_json)：每轮完整行内容，JSON 数组原样保存；
- annotations(id, review_id, text, created_round, anchor_round, anchor_line)：
  可靠锚点随成功定位推进，待定位时保持不变。
"""
from __future__ import annotations

import json
import sqlite3
from typing import List, Optional, Sequence, Tuple

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS rounds (
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    round_no INTEGER NOT NULL,
    lines_json TEXT NOT NULL,
    PRIMARY KEY (review_id, round_no)
);
CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    text TEXT NOT NULL,
    created_round INTEGER NOT NULL,
    anchor_round INTEGER NOT NULL,
    anchor_line INTEGER NOT NULL
);
"""


class Store:
    """封装 reviews / rounds / annotations 三张表的读写。"""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get_or_create_review(self, file_path: str) -> int:
        row = self._conn.execute(
            "SELECT id FROM reviews WHERE file_path = ?", (file_path,)
        ).fetchone()
        if row is not None:
            return row[0]
        cur = self._conn.execute(
            "INSERT INTO reviews (file_path) VALUES (?)", (file_path,)
        )
        self._conn.commit()
        return cur.lastrowid

    def latest_round(self, review_id: int) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(round_no), 0) FROM rounds WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        return row[0]

    def append_round(self, review_id: int, round_no: int, lines: Sequence[str]) -> None:
        self._conn.execute(
            "INSERT INTO rounds (review_id, round_no, lines_json) VALUES (?, ?, ?)",
            (review_id, round_no, json.dumps(list(lines), ensure_ascii=False)),
        )
        self._conn.commit()

    def get_lines(self, review_id: int, round_no: int) -> List[str]:
        row = self._conn.execute(
            "SELECT lines_json FROM rounds WHERE review_id = ? AND round_no = ?",
            (review_id, round_no),
        ).fetchone()
        if row is None:
            raise KeyError(f"round {round_no} not found for review {review_id}")
        return json.loads(row[0])

    def add_annotation(
        self, review_id: int, text: str, created_round: int, anchor_line: int
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO annotations (review_id, text, created_round, anchor_round, anchor_line)"
            " VALUES (?, ?, ?, ?, ?)",
            (review_id, text, created_round, created_round, anchor_line),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_anchor(self, annotation_id: int, anchor_round: int, anchor_line: int) -> None:
        self._conn.execute(
            "UPDATE annotations SET anchor_round = ?, anchor_line = ? WHERE id = ?",
            (anchor_round, anchor_line, annotation_id),
        )
        self._conn.commit()

    def list_annotations(self, review_id: int) -> List[Tuple[int, str, int, int, int]]:
        """返回 (id, text, created_round, anchor_round, anchor_line) 列表。"""
        return self._conn.execute(
            "SELECT id, text, created_round, anchor_round, anchor_line"
            " FROM annotations WHERE review_id = ? ORDER BY id",
            (review_id,),
        ).fetchall()
