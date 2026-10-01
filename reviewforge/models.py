"""数据类型定义：批注状态与视图。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AnnotationStatus(Enum):
    """批注在当前轮的定位状态。"""

    LOCATED = "located"
    PENDING = "pending"


@dataclass(frozen=True)
class AnnotationView:
    """查看当前轮批注时返回的只读视图。

    line 仅在 status 为 LOCATED 时是当前轮行号（1 起始）；
    PENDING 时 line 为 None，只能展示 anchor_version/anchor_line 历史锚点。
    """

    annotation_id: int
    text: str
    status: AnnotationStatus
    line: int | None
    anchor_version: int
    anchor_line: int
