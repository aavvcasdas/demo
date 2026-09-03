# 《剧本人生》系列短篇拆书库

抖音「剧本人生」系列（第二人称沉浸式人生副本短片）ASR 字幕合集的分篇与拆书成果。拆书遵循 [oh-story-claudecode](https://github.com/zenstory-ai/oh-story-claudecode) 的 `story-short-analyze` 管道。

## 目录

| 路径 | 内容 |
|------|------|
| `uploads/8月16日.txt` | 源字幕合集（12434 行，约 11.6 万字） |
| `分篇/` | 按开场白切分出的 39 篇独立短篇（`索引.md` / `_index.json` 为索引） |
| `拆文库/{序号}_{标题}/` | 深拆产物：`原文/`、`情节节点.md`、`拆文报告.md`、`写作手法.md`、`_meta.json` |
| `拆文库/00_*.md` | 系列总拆书与全篇速拆卡（生成中） |
| `scripts/` | `split_episodes.py` 分篇脚本、`pos.py` 关键句定位工具 |
| `skills/` | 已部署的 oh-story skills 副本（generic 模式） |
| `AGENTS.md` | skills 的 Agent 入口说明 |

## 深拆进度

- 已完成：01 无辣不欢的一生 · 02 外卖员的一生 · 03 雇佣兵的一生 · 04 中10亿彩票的人生 · 05 县城精神小伙的沉沦之路 · 06 职高生毕业后的残酷现实
- 进行中：系列总拆书、39 篇速拆卡
- 后续轮次：07 起按序号继续深拆
