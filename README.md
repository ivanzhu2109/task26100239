# ReviewForge Local：跨轮批注定位库

代码评审多轮修改时，把上一轮未解决的批注可靠地映射到新版本的行号。
版本与批注持久化在 SQLite 中，关闭重开数据库后行为与连续运行完全一致。

## 定位原则

- 每个评审只处理一个固定路径的文本文件；调用方提供完整行内容，逐字比较，不忽略空白；空文件是合法版本。
- 两个版本之间，只允许内容完全相等的旧行与新行配对；每行最多配对一次，配对保持两侧原有先后顺序。
- 只把配对总数达到最大值的方案视为合理解释，且所有最大方案地位相同。
- 仅当锚点旧行在**所有**合理解释中都参与配对、且始终对应**同一个**新行号时，批注才算已定位；
  只要存在某个解释中该行未配对，或存在两个不同目标行号，就标为待定位——绝不猜测位置。
- 待定位批注保留最近一次可靠锚点，后续轮次仍可恢复定位；查看结果中始终包含待定位批注，
  但只暴露历史锚点（`anchor_version` / `anchor_line`），不把历史行号当作当前行号。

## 安装与运行

纯标准库实现（Python 3.10+），无第三方依赖：

```bash
python3 -m pytest tests/   # 运行自动化测试
```

## 使用示例

```python
from reviewforge import AnnotationStatus, ReviewSession

# 创建评审：绑定数据库文件与被评审文件路径，首个版本为第 1 轮
s = ReviewSession.create("review.db", "src/main.py", ["x", "x"])

# 在当前轮某行（1 起始）添加未解决批注
a1 = s.add_annotation(1, "这里需要修改")
a2 = s.add_annotation(2, "这里也是")

# 追加一轮新版本，返回版本号
s.append_version(["x", "x", "x"])

# 查看当前轮全部批注（含待定位）
for v in s.annotations():
    if v.status is AnnotationStatus.LOCATED:
        print(f"批注 {v.annotation_id} 定位到当前第 {v.line} 行")
    else:
        print(f"批注 {v.annotation_id} 待定位，历史锚点："
              f"第 {v.anchor_version} 轮第 {v.anchor_line} 行")

s.close()

# 之后可重开数据库继续追加版本，结果与连续运行一致
s = ReviewSession.open("review.db")
s.append_version(["x", "x"])   # 两条批注分别恢复到第 1、2 行
s.close()
```

## API 一览

- `ReviewSession.create(db_path, file_path, lines)`：创建评审并写入第 1 轮版本；数据库已有评审时报错。
- `ReviewSession.open(db_path)`：重开已有评审数据库。
- `append_version(lines) -> int`：追加一轮版本并重新定位所有批注，返回版本号（1 起始）。
- `add_annotation(line, text) -> int`：在当前轮 `line` 行（1 起始）添加未解决批注，返回批注 id；行号越界抛 `ValueError`。
- `annotations() -> list[AnnotationView]`：查看当前轮全部批注。`AnnotationView` 字段：
  `annotation_id`、`text`、`status`（`LOCATED` / `PENDING`）、`line`（仅定位成功时为当前行号，否则为 `None`）、
  `anchor_version` / `anchor_line`（最近一次可靠锚点）。
- `close()`：关闭数据库连接。

## 代码结构

- `reviewforge/matching.py`：最大保序等值配对分析（LCS 动态规划 + 前后缀分解，
  对每个旧行给出所有最大方案中的目标行集合，以及它是否在所有方案中都参与配对）。
- `reviewforge/store.py`：SQLite 持久化（版本按 JSON 行列表存储，批注只存可靠锚点）。
- `reviewforge/core.py`：对外会话 API；追加版本时从每条批注的可靠锚点版本直接比到新版本，
  定位成功才推进锚点。
- `reviewforge/models.py`：`AnnotationStatus` 与 `AnnotationView` 类型定义。
- `tests/`：匹配算法与暴力枚举全部最大配对方案对拍（含随机与穷举），
  以及端到端场景（重复行、插入、删除、空版本、关闭重开一致性）。
