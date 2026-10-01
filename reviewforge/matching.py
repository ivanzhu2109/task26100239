"""两个文本行版本之间的全部最优配对计算。

配对规则：内容完全相等的旧行与新行才能配对；每行最多参与一次；
配对保持两侧原有先后顺序（即公共子序列式的匹配）。
只有配对总数达到最大值的方案才是合理解释。

对每个旧行，只有它在所有合理解释中都参与配对、且始终对应同一个
新行号时，才算已定位；否则为待定位（返回 None）。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence


def _prefix_dp(old_lines: Sequence[str], new_lines: Sequence[str]) -> List[List[int]]:
    """p[i][j] = old[:i] 与 new[:j] 之间的最大配对数。"""
    n, m = len(old_lines), len(new_lines)
    p = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        row, prev = p[i], p[i - 1]
        oi = old_lines[i - 1]
        for j in range(1, m + 1):
            best = row[j - 1] if row[j - 1] >= prev[j] else prev[j]
            if oi == new_lines[j - 1]:
                cand = prev[j - 1] + 1
                if cand > best:
                    best = cand
            row[j] = best
    return p


def locate_lines(old_lines: Sequence[str], new_lines: Sequence[str]) -> Dict[int, Optional[int]]:
    """对每个旧行下标（0 起始）给出定位结果。

    返回 {old_index: new_index 或 None}：
    - new_index：该旧行在所有最优配对中都配对到同一个新行；
    - None：存在某个最优配对中该旧行未配对，或不同最优配对中目标行不同。
    """
    n, m = len(old_lines), len(new_lines)
    p = _prefix_dp(old_lines, new_lines)
    # s[i][j] = old[i:] 与 new[j:] 之间的最大配对数（即反转后的前缀 DP）。
    s = _prefix_dp(old_lines[::-1], new_lines[::-1])
    total = p[n][m]

    def suffix(i: int, j: int) -> int:
        return s[n - i][m - j]

    result: Dict[int, Optional[int]] = {}
    for i in range(n):
        # 是否存在不配对旧行 i 的最优方案：
        # 在某个新行切分点 j 处，old[:i] 与 new[:j]、old[i+1:] 与 new[j:] 各自最优。
        can_skip = any(p[i][j] + suffix(i + 1, j) == total for j in range(m + 1))
        targets = set()
        if old_lines and new_lines:
            for j in range(m):
                if old_lines[i] == new_lines[j] and p[i][j] + 1 + suffix(i + 1, j + 1) == total:
                    targets.add(j)
        if can_skip or len(targets) != 1:
            result[i] = None
        else:
            result[i] = targets.pop()
    return result
