"""数据类型定义。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AnnotationStatus(str, Enum):
    LOCATED = "located"
    PENDING = "pending"


@dataclass(frozen=True)
class AnnotationView:
    """查看当前轮批注时返回的只读视图。

    current_line 仅在 status 为 LOCATED 时有值（1 起始行号）；
    PENDING 时只能展示历史锚点 anchor_round / anchor_line。
    """

    annotation_id: int
    text: str
    status: AnnotationStatus
    current_line: Optional[int]
    anchor_round: int
    anchor_line: int
