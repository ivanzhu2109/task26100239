"""上层直接调用的评审会话 API。

每个 ReviewSession 绑定一个 SQLite 数据库文件与一个固定路径的文本文件。
追加新轮时，每条批注从最近一次可靠锚点所在版本直接与新版本比较：
- 唯一定位：可靠锚点推进到新轮对应行；
- 待定位：保留原可靠锚点，后续轮次仍可恢复。
"""
from __future__ import annotations

from typing import List, Sequence

from .matching import locate_lines
from .models import AnnotationStatus, AnnotationView
from .store import Store


class ReviewSession:
    """跨轮批注定位会话。关闭后可用相同参数重新打开，行为与连续运行一致。"""

    def __init__(self, db_path: str, file_path: str) -> None:
        self._store = Store(db_path)
        self._review_id = self._store.get_or_create_review(file_path)

    def __enter__(self) -> "ReviewSession":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def current_round(self) -> int:
        """当前轮次号；尚无任何版本时为 0。"""
        return self._store.latest_round(self._review_id)

    def append_round(self, lines: Sequence[str]) -> int:
        """追加一轮版本（完整行内容，逐字比较），返回轮次号（从 1 开始）。"""
        new_lines = [str(line) for line in lines]
        round_no = self.current_round + 1
        annotations = self._store.list_annotations(self._review_id)
        # 按锚点所在版本分组，每个旧版本只做一次配对计算。
        located_by_round: dict[int, dict[int, int | None]] = {}
        for ann_id, _text, _created, anchor_round, anchor_line in annotations:
            if anchor_round not in located_by_round:
                old_lines = self._store.get_lines(self._review_id, anchor_round)
                located_by_round[anchor_round] = locate_lines(old_lines, new_lines)
            target = located_by_round[anchor_round][anchor_line - 1]
            if target is not None:
                self._store.update_anchor(ann_id, round_no, target + 1)
        self._store.append_round(self._review_id, round_no, new_lines)
        return round_no

    def add_annotation(self, line: int, text: str) -> int:
        """在当前轮的 line 行（1 起始）添加未解决批注，返回批注 id。"""
        round_no = self.current_round
        if round_no == 0:
            raise ValueError("cannot annotate before the first round is appended")
        line_count = len(self._store.get_lines(self._review_id, round_no))
        if not 1 <= line <= line_count:
            raise ValueError(f"line {line} out of range 1..{line_count}")
        return self._store.add_annotation(self._review_id, text, round_no, line)

    def annotations(self) -> List[AnnotationView]:
        """查看当前轮全部批注（含待定位批注），按创建顺序返回。"""
        round_no = self.current_round
        views: List[AnnotationView] = []
        for ann_id, text, _created, anchor_round, anchor_line in self._store.list_annotations(
            self._review_id
        ):
            located = anchor_round == round_no
            views.append(
                AnnotationView(
                    annotation_id=ann_id,
                    text=text,
                    status=AnnotationStatus.LOCATED if located else AnnotationStatus.PENDING,
                    current_line=anchor_line if located else None,
                    anchor_round=anchor_round,
                    anchor_line=anchor_line,
                )
            )
        return views

    def close(self) -> None:
        self._store.close()
