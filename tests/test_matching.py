"""matching.analyze 的测试：与暴力枚举全部最大配对独立对拍。"""

from __future__ import annotations

import itertools
import random

from reviewforge.matching import LineMatch, analyze


def brute_force_analyze(old_lines: list[str], new_lines: list[str]) -> list[LineMatch]:
    """独立实现：枚举全部保序等值配对，只保留配对数最大的方案。"""
    n, m = len(old_lines), len(new_lines)
    best_size = -1
    best: list[list[tuple[int, int]]] = []

    def walk(i: int, j: int, pairs: list[tuple[int, int]]) -> None:
        nonlocal best_size, best
        if i == n or j == m:
            if len(pairs) > best_size:
                best_size = len(pairs)
                best = [list(pairs)]
            elif len(pairs) == best_size:
                best.append(list(pairs))
            return
        # 上界剪枝：剩余旧行全部配上也无法超过当前最优时停止
        if len(pairs) + (n - i) < best_size:
            return
        if old_lines[i] == new_lines[j]:
            walk(i + 1, j + 1, pairs + [(i, j)])
        walk(i + 1, j, pairs)
        walk(i, j + 1, pairs)

    walk(0, 0, [])
    targets: list[set[int]] = [set() for _ in range(n)]
    matched_count = [0] * n
    for pairs in best:
        seen = set()
        for i, j in pairs:
            targets[i].add(j)
            seen.add(i)
        for i in seen:
            matched_count[i] += 1
    return [
        LineMatch(
            targets=frozenset(targets[i]),
            matched_in_all=matched_count[i] == len(best),
        )
        for i in range(n)
    ]


def targets_of(old_lines, new_lines):
    return [m.targets for m in analyze(old_lines, new_lines)]


def test_identical_versions_map_one_to_one():
    assert targets_of(["a", "b", "c"], ["a", "b", "c"]) == [{0}, {1}, {2}]


def test_repeated_lines_have_multiple_targets():
    assert targets_of(["x", "x"], ["x", "x", "x"]) == [{0, 1}, {1, 2}]


def test_deleted_line_has_no_target():
    # 旧行 "b" 在所有最大方案中都被删除
    assert targets_of(["a", "b"], ["a"]) == [{0}, set()]


def test_line_deleted_in_some_but_not_all_solutions():
    # old=[a,b], new=[b,a]：LCS=1，最大方案为 {(a,a)} 或 {(b,b)}。
    # 两行各自在另一个方案中都被删除：targets 唯一但 matched_in_all=False。
    result = analyze(["a", "b"], ["b", "a"])
    assert result[0] == LineMatch(targets=frozenset({1}), matched_in_all=False)
    assert result[1] == LineMatch(targets=frozenset({0}), matched_in_all=False)


def test_line_matched_in_all_solutions():
    result = analyze(["a", "b", "a"], ["a", "a"])
    assert result[0] == LineMatch(targets=frozenset({0}), matched_in_all=True)
    assert result[1] == LineMatch(targets=frozenset(), matched_in_all=False)
    assert result[2] == LineMatch(targets=frozenset({1}), matched_in_all=True)


def test_empty_versions():
    assert analyze([], []) == []
    assert analyze([], ["a", "b"]) == []
    assert targets_of(["a", "b"], []) == [set(), set()]


def test_whitespace_is_significant():
    assert targets_of([" x"], ["x"]) == [set()]
    assert targets_of(["x "], ["x"]) == [set()]


def test_fuzz_against_brute_force():
    rng = random.Random(20261002)
    alphabet = ["a", "b", "c", ""]
    for _ in range(400):
        old = [rng.choice(alphabet) for _ in range(rng.randint(0, 6))]
        new = [rng.choice(alphabet) for _ in range(rng.randint(0, 6))]
        assert analyze(old, new) == brute_force_analyze(old, new), (old, new)


def test_fuzz_structured_edits_against_brute_force():
    """模拟真实编辑：以旧版本为基础做插入/删除/保留，再与暴力结果对拍。"""
    rng = random.Random(7)
    alphabet = ["u1", "u2", "dup", "dup", "x"]
    for _ in range(300):
        old = [rng.choice(alphabet) for _ in range(rng.randint(0, 5))]
        new: list[str] = []
        for line in old:
            if rng.random() < 0.7:
                new.append(line)  # 保留
            if rng.random() < 0.25:
                new.append(rng.choice(alphabet))  # 在旁边插入
        if rng.random() < 0.3:
            new.append(rng.choice(alphabet))
        assert analyze(old, new) == brute_force_analyze(old, new), (old, new)


def test_all_subsets_small_alphabet():
    """穷举小字母表下所有短版本对，全面与暴力实现对拍。"""
    alphabet = ["a", "b"]
    pools = [["".join(p) for p in itertools.product(alphabet, repeat=n)] for n in range(5)]
    for n in range(5):
        for m in range(5):
            for old in pools[n]:
                for new in pools[m]:
                    old_lines = list(old)
                    new_lines = list(new)
                    assert analyze(old_lines, new_lines) == brute_force_analyze(
                        old_lines, new_lines
                    ), (old_lines, new_lines)
