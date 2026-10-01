"""两个文本版本之间的最大保序等值配对（LCS 匹配）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LineMatch:
    """一个旧行在全部最大配对方案中的去向。

    targets：该旧行在任一最大方案中配到的新行下标集合（0 起始）；
    matched_in_all：该旧行是否在所有最大方案中都参与配对。
    """

    targets: frozenset[int]
    matched_in_all: bool


def analyze(old_lines: list[str], new_lines: list[str]) -> list[LineMatch]:
    """对每个旧行下标，计算它在所有最大配对方案中的配对情况。"""
    n = len(old_lines)
    m = len(new_lines)

    # pre[i][j] = LCS(old[:i], new[:j]) 的长度
    pre = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        oi = old_lines[i - 1]
        row = pre[i]
        prev = pre[i - 1]
        for j in range(1, m + 1):
            if oi == new_lines[j - 1]:
                row[j] = prev[j - 1] + 1
            else:
                row[j] = row[j - 1] if row[j - 1] >= prev[j] else prev[j]

    # suf[i][j] = LCS(old[i:], new[j:]) 的长度（i、j 为 0 起始下标）
    suf = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        oi = old_lines[i]
        row = suf[i]
        nxt = suf[i + 1]
        for j in range(m - 1, -1, -1):
            if oi == new_lines[j]:
                row[j] = nxt[j + 1] + 1
            else:
                row[j] = row[j + 1] if row[j + 1] >= nxt[j] else nxt[j]

    total = pre[n][m]
    result: list[LineMatch] = []
    for i in range(n):
        oi = old_lines[i]
        pre_i = pre[i]
        suf_next = suf[i + 1]
        targets: set[int] = set()
        for j in range(m):
            # (i, j) 出现在某个最大方案中，当且仅当
            # 前后两段仍能凑齐其余 total - 1 对。
            if oi == new_lines[j] and pre_i[j] + 1 + suf_next[j + 1] == total:
                targets.add(j)
        # 旧行 i 在某个最大方案中未配对，当且仅当去掉它之后
        # 仍能达到同样的最大配对数：max_k pre[i][k] + suf[i+1][k] == total。
        best_without = 0
        for k in range(m + 1):
            candidate = pre_i[k] + suf_next[k]
            if candidate > best_without:
                best_without = candidate
        result.append(
            LineMatch(
                targets=frozenset(targets),
                matched_in_all=best_without < total,
            )
        )
    return result
