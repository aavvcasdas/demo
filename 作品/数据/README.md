# 数据入口 · schema v3

本目录取代两张旧 CSV 的活动写入。旧 `作品/_数据.csv`、`_数据_v2.csv` 保持字节不变；`legacy_raw/` 是按 SHA 命名的原始备份，`legacy_manifest.json` 记录来源。`legacy_quarantine.jsonl` 保存全部 30 条旧记录及原始列值，其中 13 条列宽错误；列宽正常也不等于语义/版本可靠。**本次没有把任何历史数值猜成已验证快照。**

## 新增一次真实观测

```bash
python3 scripts/fuben_data.py template > /tmp/snapshot.json
# 填写真实信息；text_sha256 可用 sha256sum 作品/NN_主题/正文.md 获取
python3 scripts/fuben_data.py record --input /tmp/snapshot.json
python3 scripts/fuben_data.py report
```

- 必需身份：作品 ID、正文版本/路径/SHA、成片版本/平台视频 ID。
- 时间：发布时间与观测时间均使用带时区 ISO 8601（例如 `2026-09-19T15:22:00+08:00`）。记录累计窗口及自然/付费/混合来源；不能默认为同龄样本。
- 来源：具名上报、截图或平台导出。截图/导出需工作区内文件与 SHA。提交来源仍不等于本工具独立验真。
- 观测：播放、点赞、评论、分享、收藏、涨粉、平均观看秒数、后台完播率、5秒留存。未知填 `null`，不能填零；比率用 `0..1`，不是百分号字符串。
- 派生：赞播比、平均观看占比、观察龄另列。`average_watch_seconds / duration_seconds` **不是 completion_rate**；重播时平均观看占比可超过1。
- 点赞允许撤回/校正，不设置“只能上升”；同一视频/版本/时间点不同数值会拒绝覆盖，须保留纠错证据后另立观测。

写入在本仓 POSIX 环境加锁、验证旧文件后原子替换；重复提交同一条幂等。旧 `fuben_loop.py record NN 点赞 [播放]` 已明确拒绝，因为它没有版本、时区与来源信息。报告不再对六条异龄旧记录计算“特征×点赞”并升级成创作定律。

迁移可复跑：`python3 scripts/fuben_data.py migrate` 默认只预览，显式 `--write` 才写备份/隔离文件。原 CSV 永不覆写。历史重新入库必须补足身份与来源后使用 v3 写入，不对错列进行概率猜测。
