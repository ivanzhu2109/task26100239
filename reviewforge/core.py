"""对外 API：追加版本、添加批注、查看批注。"""

from __future__ import annotations

from .matching import analyze
from .models import AnnotationStatus, AnnotationView
from .store import Store


class ReviewSession:
    """一个评审会话，绑定一个 SQLite 数据库与一个固定文件路径。"""

    def __init__(self, store: Store) -> None:
        self._store = store

    @classmethod
    def create(cls, db_path: str, file_path: str, lines: list[str]) -> "ReviewSession":
        """创建新评审，以 lines 作为第 1 轮版本。空文件（[]）合法。"""
        store = Store(db_path)
        try:
            if store.get_file_path() is not None:
                raise ValueError(f"数据库已存在评审：{db_path}")
            _check_lines(lines)
            store.set_file_path(file_path)
            store.insert_version(list(lines))
            store.commit()
        except Exception:
            store.close()
            raise
        return cls(store)

    @classmethod
    def open(cls, db_path: str) -> "ReviewSession":
        """重开已有评审数据库，行为必须与连续运行一致。"""
        store = Store(db_path)
        try:
            if store.get_file_path() is None:
                raise ValueError(f"不是 ReviewForge 数据库：{db_path}")
        except Exception:
            store.close()
            raise
        return cls(store)

    def close(self) -> None:
        self._store.close()

    def append_version(self, lines: list[str]) -> int:
        """追加一轮新版本，返回版本号（1 起始）。"""
        _check_lines(lines)
        store = self._store
        new_lines = list(lines)
        new_version = store.insert_version(new_lines)
        for ann_id, _text, anchor_version, anchor_line in store.list_annotations():
            old_lines = store.get_lines(anchor_version)
            match = analyze(old_lines, new_lines)[anchor_line - 1]
            if match.matched_in_all and len(match.targets) == 1:
                # 所有最大方案都配到同一个新行：定位成功，推进可靠锚点。
                store.update_anchor(ann_id, new_version, next(iter(match.targets)) + 1)
            # 否则保留原可靠锚点，后续轮次仍可恢复定位。
        store.commit()
        return new_version

    def add_annotation(self, line: int, text: str) -> int:
        """在当前轮的 line 行（1 起始）添加未解决批注，返回批注 id。"""
        store = self._store
        version = store.current_version()
        line_count = len(store.get_lines(version))
        if not 1 <= line <= line_count:
            raise ValueError(
                f"行号越界：第 {line} 行（当前轮共 {line_count} 行）"
            )
        ann_id = store.insert_annotation(text, version, line)
        store.commit()
        return ann_id

    def annotations(self) -> list[AnnotationView]:
        """查看当前轮全部批注（含待定位批注）。"""
        store = self._store
        current = store.current_version()
        views: list[AnnotationView] = []
        for ann_id, text, anchor_version, anchor_line in store.list_annotations():
            located = anchor_version == current
            views.append(
                AnnotationView(
                    annotation_id=ann_id,
                    text=text,
                    status=AnnotationStatus.LOCATED if located else AnnotationStatus.PENDING,
                    line=anchor_line if located else None,
                    anchor_version=anchor_version,
                    anchor_line=anchor_line,
                )
            )
        return views


def _check_lines(lines: list[str]) -> None:
    if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
        raise TypeError("lines 必须是 str 列表")
