"""ReviewSession 的端到端测试：跨轮定位、待定位恢复、关闭重开一致性。"""

from __future__ import annotations

import pytest

from reviewforge import AnnotationStatus, ReviewSession
from reviewforge.matching import analyze


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "review.db")


def status_of(session):
    return {v.annotation_id: (v.status, v.line) for v in session.annotations()}


def test_required_scenario_two_x_lines_with_reopen(db_path):
    """旧版两行 x 各一条批注；变三行 x 都待定位；恢复两行 x 各自回到原行。"""
    s = ReviewSession.create(db_path, "f.txt", ["x", "x"])
    a1 = s.add_annotation(1, "第一条")
    a2 = s.add_annotation(2, "第二条")
    assert status_of(s) == {
        a1: (AnnotationStatus.LOCATED, 1),
        a2: (AnnotationStatus.LOCATED, 2),
    }
    s.append_version(["x", "x", "x"])
    assert status_of(s) == {
        a1: (AnnotationStatus.PENDING, None),
        a2: (AnnotationStatus.PENDING, None),
    }
    # 待定位批注仍出现在结果中，且只暴露历史锚点
    views = {v.annotation_id: v for v in s.annotations()}
    assert (views[a1].anchor_version, views[a1].anchor_line) == (1, 1)
    assert (views[a2].anchor_version, views[a2].anchor_line) == (1, 2)
    s.close()
    # 中途关闭重开数据库，再恢复为两行 x
    s = ReviewSession.open(db_path)
    assert status_of(s) == {
        a1: (AnnotationStatus.PENDING, None),
        a2: (AnnotationStatus.PENDING, None),
    }
    s.append_version(["x", "x"])
    assert status_of(s) == {
        a1: (AnnotationStatus.LOCATED, 1),
        a2: (AnnotationStatus.LOCATED, 2),
    }
    s.close()


def test_reopen_does_not_change_results(db_path):
    """同样的操作序列，连续运行与中途逐步重开的结果必须一致。"""
    versions = [["a", "b"], ["b", "a", "b"], ["a", "b"], ["a", "b", "a", "b"], ["b"]]

    def run(path, reopen_every_step):
        s = ReviewSession.create(path, "f.txt", versions[0])
        aid = s.add_annotation(2, "跟踪 b")
        snapshots = [status_of(s)[aid]]
        for lines in versions[1:]:
            if reopen_every_step:
                s.close()
                s = ReviewSession.open(path)
            s.append_version(lines)
            snapshots.append(status_of(s)[aid])
        s.close()
        return snapshots

    continuous = run(db_path, reopen_every_step=False)
    reopened = run(db_path + ".2", reopen_every_step=True)
    assert continuous == reopened


def test_mixed_edits_match_independent_computation(db_path):
    """短文件混合唯一行、重复行、插入、删除、空版本。"""
    s = ReviewSession.create(db_path, "f.txt", ["keep", "dup", "dup", "tail"])
    anns = [
        s.add_annotation(1, "唯一行"),
        s.add_annotation(2, "重复行一"),
        s.add_annotation(3, "重复行二"),
        s.add_annotation(4, "将被删除"),
    ]
    versions = [
        ["ins", "keep", "dup", "dup", "dup"],  # 首部插入 + 重复行增员，tail 删除
        ["keep", "dup", "dup", "dup"],  # 再删首行
        [],  # 空版本：全部待定位
        ["keep", "dup", "dup"],  # 从空版本恢复
        ["keep", "dup", "dup", "tail"],  # tail 原文重现
    ]
    for lines in versions:
        s.append_version(lines)
        current = {v.annotation_id: v for v in s.annotations()}
        for aid in anns:
            view = current[aid]
            # 独立重算：从该批注当前可靠锚点所在版本直接比到最新版本
            old_lines = _lines_of(s, view.anchor_version)
            match = analyze(old_lines, lines)[view.anchor_line - 1]
            if match.matched_in_all and len(match.targets) == 1:
                assert view.status is AnnotationStatus.LOCATED
                assert view.line == next(iter(match.targets)) + 1
            else:
                assert view.status is AnnotationStatus.PENDING
                assert view.line is None
        # 不变式：已定位当且仅当可靠锚点落在当前轮
        for v in current.values():
            located = v.status is AnnotationStatus.LOCATED
            assert located == (v.anchor_version == _current_version(s))
    s.close()


def test_line_deleted_in_some_solutions_stays_pending(db_path):
    """锚点旧行在部分合理解释中被删除时必须待定位。"""
    s = ReviewSession.create(db_path, "f.txt", ["a", "b"])
    s.add_annotation(2, "b 行")
    # new=[b,a]：LCS=1，最大方案要么配 a 要么配 b。
    # b 虽在一种方案中唯一对应新行1，但在另一方案中被删除 -> 待定位。
    s.append_version(["b", "a"])
    view = s.annotations()[0]
    assert view.status is AnnotationStatus.PENDING
    # 恢复 [a, b]：唯一解释，回到第2行
    s.append_version(["a", "b"])
    view = s.annotations()[0]
    assert (view.status, view.line) == (AnnotationStatus.LOCATED, 2)
    s.close()


def test_ambiguous_repeated_line_stays_pending(db_path):
    """锚点行在多个合理解释中对应不同新行号时必须待定位。"""
    s = ReviewSession.create(db_path, "f.txt", ["a", "b"])
    s.add_annotation(2, "b 行")
    # new=[a,b,a,b]：b 可配新行2或新行4 -> 待定位
    s.append_version(["a", "b", "a", "b"])
    assert s.annotations()[0].status is AnnotationStatus.PENDING
    # 恢复 [a,b]：回到第2行
    s.append_version(["a", "b"])
    view = s.annotations()[0]
    assert (view.status, view.line) == (AnnotationStatus.LOCATED, 2)
    s.close()


def test_empty_file_is_valid_version(db_path):
    s = ReviewSession.create(db_path, "empty.txt", [])
    assert s.annotations() == []
    s.append_version(["hello"])
    s.add_annotation(1, "在恢复出的行上")
    s.append_version([])
    view = s.annotations()[0]
    assert view.status is AnnotationStatus.PENDING
    assert (view.anchor_version, view.anchor_line) == (2, 1)
    s.close()


def test_annotation_line_validation(db_path):
    s = ReviewSession.create(db_path, "f.txt", ["only"])
    with pytest.raises(ValueError):
        s.add_annotation(0, "越界")
    with pytest.raises(ValueError):
        s.add_annotation(2, "越界")
    s.close()
    empty = ReviewSession.create(db_path + ".e", "e.txt", [])
    with pytest.raises(ValueError):
        empty.add_annotation(1, "空文件没有可批注行")
    empty.close()


def test_whitespace_sensitive_and_exact_text(db_path):
    s = ReviewSession.create(db_path, "f.txt", [" x", "x "])
    a1 = s.add_annotation(1, "前导空格")
    a2 = s.add_annotation(2, "尾随空格")
    # 逐字比较：" x" 与 "x " 不相等。交换后 LCS=1，
    # 每行都在某个最优解释中被删除 -> 双双待定位。
    s.append_version(["x ", " x"])
    views = {v.annotation_id: v for v in s.annotations()}
    assert (views[a1].status, views[a1].line) == (AnnotationStatus.PENDING, None)
    assert (views[a2].status, views[a2].line) == (AnnotationStatus.PENDING, None)
    # 保持原顺序并整体后移：唯一解释，分别定位到第 2、3 行
    s.append_version(["prefix", " x", "x "])
    views = {v.annotation_id: v for v in s.annotations()}
    assert (views[a1].status, views[a1].line) == (AnnotationStatus.LOCATED, 2)
    assert (views[a2].status, views[a2].line) == (AnnotationStatus.LOCATED, 3)
    s.close()


def test_create_rejects_existing_database(db_path):
    s = ReviewSession.create(db_path, "f.txt", ["a"])
    s.close()
    with pytest.raises(ValueError):
        ReviewSession.create(db_path, "f.txt", ["a"])


def test_open_rejects_non_reviewforge_db(tmp_path):
    import sqlite3

    bad = str(tmp_path / "plain.db")
    conn = sqlite3.connect(bad)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.close()
    with pytest.raises(ValueError):
        ReviewSession.open(bad)


def _current_version(session):
    return session._store.current_version()


def _lines_of(session, version):
    return session._store.get_lines(version)
