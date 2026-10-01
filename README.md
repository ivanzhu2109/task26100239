# ReviewForge Local

跨轮批注定位库。代码评审多轮修改时，把上一轮未解决的批注可靠地映射到新版本的行号；
宁可提示“待定位”，也不把不确定的位置展示成确定结果。版本与批注持久化在 SQLite 中。

## 定位规则

- 每个评审绑定一个固定路径的文本文件；调用方提供每轮的完整行内容，逐字比较，不忽略空白；空文件是有效版本。
- 两个版本之间，内容完全相等的旧行与新行可配对；每行最多配对一次，配对保持两侧先后顺序。
- 只接受配对总数最大的方案，且所有最大方案地位相同。
- 一条批注只有在**所有**最优方案中都配对、且始终落到同一个新行号时才算已定位；
  否则标为待定位（保留历史锚点，后续轮次仍可恢复），绝不猜测位置。

## 使用

```python
from reviewforge import ReviewSession, AnnotationStatus

session = ReviewSession("review.db", "src/foo.py")   # 数据库路径 + 固定文件路径
session.append_round(["x", "x"])                     # 追加一轮，返回轮次号（从 1 开始）
ann_id = session.add_annotation(line=1, text="这里要改")  # 在当前轮某行加批注（1 起始）

session.append_round(["x", "x", "x"])                # 新一轮后自动重定位
for view in session.annotations():                   # 查看当前轮全部批注（含待定位）
    if view.status is AnnotationStatus.LOCATED:
        print(view.current_line)                     # 当前行号
    else:
        print("待定位，历史锚点:", view.anchor_round, view.anchor_line)

session.close()                                      # 关闭后可用同样参数重开，行为一致
```

`ReviewSession` 也支持 `with` 语句。`AnnotationView` 字段：

| 字段 | 含义 |
| --- | --- |
| `annotation_id` / `text` | 批注 id 与内容 |
| `status` | `LOCATED` 或 `PENDING` |
| `current_line` | 当前行号（1 起始），仅 `LOCATED` 时有值 |
| `anchor_round` / `anchor_line` | 最近一次可靠锚点（待定位时用于展示历史位置） |

## 运行测试

```bash
python3 -m pytest tests/ -q
```

测试包含：重复行批注的待定位与跨重开恢复、唯一行/重复行/插入/删除/空版本混合场景，
以及 `matching.locate_lines` 与暴力枚举全部最优配对的随机对照。

## 结构

- `reviewforge/matching.py` — 全部最优配对的定位判定（前后缀 DP）
- `reviewforge/store.py` — SQLite 持久化（reviews / rounds / annotations）
- `reviewforge/core.py` — `ReviewSession` 会话 API
- `reviewforge/models.py` — `AnnotationView` / `AnnotationStatus`
