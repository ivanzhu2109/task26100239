"""matching.locate_lines 与暴力枚举全部最优配对的独立计算对照。"""
from __future__ import annotations

import itertools
import random

from reviewforge.matching import locate_lines


def brute_force_locate(old_lines, new_lines):
    """枚举所有保序配对，仅保留配对数最大的方案，逐旧行判定。"""
    n, m = len(old_lines), len(new_lines)
    best_count = -1
    best_matchings = []

    def walk(i, j, pairs):
        nonlocal best_count, best_matchings
        if len(pairs) + (n - i) < best_count:
            return
        if i == n:
            if len(pairs) > best_count:
                best_count = len(pairs)
                best_matchings = [list(pairs)]
            elif len(pairs) == best_count:
                best_matchings.append(list(pairs))
            return
        # 旧行 i 不参与配对
        walk(i + 1, j, pairs)
        # 旧行 i 与某个相等的新行配对
        for k in range(j, m):
            if old_lines[i] == new_lines[k]:
                pairs.append((i, k))
                walk(i + 1, k + 1, pairs)
                pairs.pop()

    walk(0, 0, [])
    result = {}
    for i in range(n):
        targets = set()
        skipped = False
        for matching in best_matchings:
            hit = [k for a, k in matching if a == i]
            if hit:
                targets.add(hit[0])
            else:
                skipped = True
        result[i] = None if skipped or len(targets) != 1 else targets.pop()
    return result


def test_basic_cases():
    assert locate_lines(["x", "x"], ["x", "x", "x"]) == {0: None, 1: None}
    assert locate_lines(["x", "x", "x"], ["x", "x"]) == {0: None, 1: None, 2: None}
    assert locate_lines([], []) == {}
    assert locate_lines([], ["a", "b"]) == {}
    assert locate_lines(["a", "b"], []) == {0: None, 1: None}
    assert locate_lines(["a"], ["a"]) == {0: 0}
    assert locate_lines(["a", "b"], ["b", "a"]) == {0: None, 1: None}


def test_partially_deleted_duplicate_line():
    # 旧行 1（"x"）在某个最优解释中被删除，另一个解释中配对到 2，必须待定位。
    old = ["a", "x", "b"]
    new = ["a", "x", "x", "b"]
    assert locate_lines(old, new) == {0: 0, 1: None, 2: 3}


def test_randomized_against_brute_force():
    rng = random.Random(20261002)
    alphabet = ["", "x", "y", " ", "ab"]
    for _ in range(400):
        old = [rng.choice(alphabet) for _ in range(rng.randint(0, 7))]
        new = [rng.choice(alphabet) for _ in range(rng.randint(0, 7))]
        assert locate_lines(old, new) == brute_force_locate(old, new), (old, new)


def test_randomized_with_edits_against_brute_force():
    # 以旧版本为基础做插入/删除/改写，模拟真实轮次演进。
    rng = random.Random(7)
    alphabet = ["x", "y", "z"]
    for _ in range(400):
        old = [rng.choice(alphabet) for _ in range(rng.randint(0, 7))]
        new = list(old)
        for _ in range(rng.randint(0, 4)):
            op = rng.choice(["ins", "del", "set"])
            if op == "ins":
                new.insert(rng.randint(0, len(new)), rng.choice(alphabet))
            elif op == "del" and new:
                new.pop(rng.randrange(len(new)))
            elif op == "set" and new:
                new[rng.randrange(len(new))] = rng.choice(alphabet)
        assert locate_lines(old, new) == brute_force_locate(old, new), (old, new)
