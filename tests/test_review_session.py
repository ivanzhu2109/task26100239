"""ReviewSession 端到端场景：多轮演进、待定位恢复、关闭重开一致性。"""
from __future__ import annotations

import pytest

from reviewforge import AnnotationStatus, ReviewSession


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "review.db")


def by_id(session):
    return {v.annotation_id: v for v in session.annotations()}


def test_duplicate_lines_pending_then_recover_across_reopen(db_path):
    s = ReviewSession(db_path, "f.txt")
    s.append_round(["x", "x"])
    a1 = s.add_annotation(1, "on first x")
    a2 = s.add_annotation(2, "on second x")
    views = by_id(s)
    assert views[a1].status is AnnotationStatus.LOCATED and views[a1].current_line == 1
    assert views[a2].status is AnnotationStatus.LOCATED and views[a2].current_line == 2

    # 变成三行 x：两条批注都待定位，且仍出现在查看结果中。
    s.append_round(["x", "x", "x"])
    views = by_id(s)
    for v in views.values():
        assert v.status is AnnotationStatus.PENDING
        assert v.current_line is None
    assert views[a1].anchor_round == 1 and views[a1].anchor_line == 1
    assert views[a2].anchor_round == 1 and views[a2].anchor_line == 2

    # 中途关闭重开数据库，再恢复为两行 x。
    s.close()
    s = ReviewSession(db_path, "f.txt")
    s.append_round(["x", "x"])
    views = by_id(s)
    assert views[a1].status is AnnotationStatus.LOCATED and views[a1].current_line == 1
    assert views[a2].status is AnnotationStatus.LOCATED and views[a2].current_line == 2
    s.close()


def test_continuous_run_matches_reopen_run(db_path, tmp_path):
    other = str(tmp_path / "continuous.db")
    rounds = [["a", "x", "x", "b"], ["a", "x", "x", "x", "b"], ["a", "x", "b"], []]

    continuous = ReviewSession(other, "f.txt")
    reopened = ReviewSession(db_path, "f.txt")
    ann_ids = []
    for i, lines in enumerate(rounds):
        continuous.append_round(lines)
        reopened.append_round(lines)
        if i == 0:
            ann_ids = [
                continuous.add_annotation(2, "x1"),
                continuous.add_annotation(3, "x2"),
                continuous.add_annotation(4, "b"),
            ]
            for line, text in [(2, "x1"), (3, "x2"), (4, "b")]:
                reopened.add_annotation(line, text)
        if i == 2:  # 关闭重开一次，之后继续追加空版本
            reopened.close()
            reopened = ReviewSession(db_path, "f.txt")
        assert [(v.status, v.current_line) for v in continuous.annotations()] == [
            (v.status, v.current_line) for v in reopened.annotations()
        ]
    continuous.close()
    reopened.close()


def test_mixed_unique_duplicate_insert_delete_and_empty(db_path):
    s = ReviewSession(db_path, "f.txt")
    s.append_round(["head", "x", "x", "tail"])
    h = s.add_annotation(1, "head")
    x1 = s.add_annotation(2, "x1")
    x2 = s.add_annotation(3, "x2")
    t = s.add_annotation(4, "tail")

    # 插入一行 x 并删除 head：head 待定位，tail 定位到第 4 行，两条 x 待定位。
    s.append_round(["x", "x", "x", "tail"])
    views = by_id(s)
    assert views[h].status is AnnotationStatus.PENDING
    assert views[x1].status is AnnotationStatus.PENDING
    assert views[x2].status is AnnotationStatus.PENDING
    assert views[t].status is AnnotationStatus.LOCATED and views[t].current_line == 4

    # 空版本：唯一行也失去目标，全部待定位。
    s.append_round([])
    assert all(v.status is AnnotationStatus.PENDING for v in s.annotations())

    # head 恢复且 x 只剩一行：x1/x2 都争同一行，仍待定位；head/tail 定位。
    s.append_round(["head", "x", "tail"])
    views = by_id(s)
    assert views[h].status is AnnotationStatus.LOCATED and views[h].current_line == 1
    assert views[t].status is AnnotationStatus.LOCATED and views[t].current_line == 3
    assert views[x1].status is AnnotationStatus.PENDING
    assert views[x2].status is AnnotationStatus.PENDING
    s.close()


def test_pending_annotation_recovers_from_original_anchor(db_path):
    s = ReviewSession(db_path, "f.txt")
    s.append_round(["only"])
    a = s.add_annotation(1, "note")
    s.append_round([])  # 待定位，锚点停留在第 1 轮
    s.append_round(["pad", "only"])  # 从第 1 轮直接比较，定位到第 2 行
    view = by_id(s)[a]
    assert view.status is AnnotationStatus.LOCATED and view.current_line == 2
    assert view.anchor_round == 3 and view.anchor_line == 2
    s.close()


def test_annotation_validation(db_path):
    s = ReviewSession(db_path, "f.txt")
    with pytest.raises(ValueError):
        s.add_annotation(1, "no round yet")
    s.append_round(["a", "b"])
    with pytest.raises(ValueError):
        s.add_annotation(0, "bad")
    with pytest.raises(ValueError):
        s.add_annotation(3, "bad")
    s.close()


def test_exact_line_content_comparison(db_path):
    s = ReviewSession(db_path, "f.txt")
    s.append_round(["x", "x "])  # 行尾空白不同即为不同行
    a = s.add_annotation(1, "plain x")
    b = s.add_annotation(2, "x with space")
    s.append_round(["x", "x ", "tail"])
    views = by_id(s)
    # 逐字比较："x" 只配对新行 1，"x " 只配对新行 2，均唯一定位。
    assert views[a].status is AnnotationStatus.LOCATED and views[a].current_line == 1
    assert views[b].status is AnnotationStatus.LOCATED and views[b].current_line == 2
    s.close()
