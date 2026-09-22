# 连续性锁（第三把锁）验收报告

- 日期：2026-09-22
- 任务：按交接文档把「表→脚本实测→闸门 BLOCK」从数字推广到题眼/器物/人物/时间，切断打补丁式返工。
- 实测管线：79 号已用新管线全链重生成（方向3 扎心向，用户选定），见 `作品/79_把游戏当命的宅男/` 与其 `_运行/*_v2`。

## 一、改动文件清单

| 文件 | 改动 |
|---|---|
| `scripts/fuben_entity.py` 【新，主体】 | 连续性锁 10 项检查 + `--ledger` 实测台账（详见下节） |
| `scripts/fuben_setting_years.py` | D1 汉字数主张 `spoken_char_claims`（PAT_CHAR_CLAIM 前缀、仨俩解析、系词剥离、续段守卫、误算语境降 REVIEW）；SKIP_HEAD 加 实体台账/题眼锚/故事合同 |
| `scripts/fuben_engine.py` | `literal_checks` 尾部挂 SPOKEN_CHARACTER_COUNT（certain 且非 reference→BLOCK）；`inspect_path` 默认组件加 'entity'（读同目录 设定.md 调 check_text，disposition 查 policy） |
| `scripts/fuben_policy.json` | v2.1.0：`continuity_disposition` 全表（SPOKEN=BLOCK；THEME/DRIFT/ORPHAN/SPAN/PRONOUN/SEQUENCE/LEDGER_STALE=REVIEW；SCENE/UNRECOVERED/LEDGER_MISSING=NOTE） |
| `scripts/fuben_consistency.py` | docstring 注明实体漂移自 2026-09 起由 fuben_entity 承接，复用其否定句处理口径 |
| `skills/fuben-review/SKILL.md` | v6.0.0：新增 §2.5 读通专项九问（每问必须引原句）；新交付硬门：缺 `## 实体台账` 或 `## 题眼锚` → BLOCK；台账禁目测，必须 `--ledger` |
| `skills/story-short-write/SKILL.md` | 修 Phase2 路由矛盾：人生副本不进普通 Phase 2/3/4（事实锁/台账/Reference Gate/付费点不适用），只用专用三件套（题眼锚+故事合同 / 实体台账 / 读通专项+机检） |
| `skills/story-short-write/references/genre-styles/人生副本实录.md` | v14：新增 §连续性锁（交付物/硬指标/返工硬规则/8 行故事合同/回归基线） |
| `skills/story-short-write/references/genre-styles/人生副本_Agent方法.md` | §0.5 题眼先行（题眼锚四件套；题眼变更=方向变更）；§2 写前 8 行故事合同；返工表后加返工硬规则 |
| `arena.runtime.json` | v1.3.0：01 出口题眼锚门、新增 01.5_方向选择记录、02 故事合同前置、04 返工硬规则、05 含连续性锁、final_artifacts 加设定.md |
| `AGENTS.md` | 三把锁分工段（事实锁/爽感/连续性锁）+ `--ledger` 命令 |
| `docs/Arena运行时.md` | 阶段表更新（01 题眼锚、01.5、02 合同、03 九问、04 硬规则、05 连续性锁） |
| `tests/test_fuben_entity.py` 【新】 | 17 项单测：红样必中、绿样零 finding、D1 基线、_measure 子串去重（79 号实测触发的 bug 反例）、锚声明、台账往返 |
| `作品/_regression/80a…红样/正文.md` 【新】 | 交接文档附录红样原文（64 行） |
| `作品/_regression/80b…绿样/` 【新】 | 正文（最小修法 1148 字）+设定.md（题眼锚/事实锁/实体台账/因果台账/故事合同） |

## 二、脚本要点（fuben_entity.py）

- `units_of` 文本模型（空行分节、行号/位置百分比）。
- `theme_anchor`：题眼类 vs 事件压力类。声明锚（设定.md `## 题眼锚` 核心词+同类词）全灵敏并类；自动模式只判口号型标题（主义/时代/全网/浪潮…），须 ≥3 处跨 ≥2 单元才立论。
- `entity_state_drift`：容器归属排除被 RELOCATE 消费的位置、距离 ≤14、代词回指「它」开头行。
- `orphan_nouns`：后 75% 单现+吃上下文+`_has_positive` 否定豁免+台账声明豁免。
- `span_conflicts`：缺席语境词 ±1 行、500 字符窗、比值 ≥1.5 或差 ≥7 天。
- `scene_state_null`：滚动昼夜上下文+钟点+散场光态。
- `pronoun_unresolved`：200 字窗+400 字同代词链衰减+全篇 ≥6 次=贯穿线豁免。
- `sequence_source`：立论取末个非「以为」句；第 N 件事施力者 vs 朋友类/竞争类。
- `unrecovered_details`：精确到分仅一次，行首时间戳豁免。
- `ledger_issues`：台账次数/首现末现 ±3% 对账（`_measure` 子串去重：别名含本体只数子串方——79 号实测触发的重复计数 bug，已修+负例测试）。
- `measured_table`（`--ledger`）：脚本实测输出，作者粘贴回设定.md，禁止目测。

## 三、fuben-review v6 新 BLOCK 项

1. 新稿交付审缺 `## 实体台账` → BLOCK（老稿复审不追溯补表，读通专项照跑）。
2. 新稿交付审缺 `## 题眼锚` → BLOCK。
3. 连续性 S2 交付前必修或在审核报告写明保留理由，不许静默放行。
4. 机检层：SPOKEN_CHARACTER_COUNT certain → BLOCK（engine 接线）。

## 四、红样 finding 清单（`fuben_run 作品/_regression/80a_大耍起时代_红样/正文.md --profile full`，exit 1）

| 级别 | code | 位置 | 内容 |
|---|---|---|---|
| S1/BLOCK | SPOKEN_CHARACTER_COUNT | L64 | 「人生就两字」说 2 实为 4（练完再耍） |
| S2 | THEME_ANCHOR_MISMATCH | L1 | 标题「大耍起时代」，正文耍 10 处 vs 吃 47 处 |
| S2 | ENTITY_STATE_DRIFT | L43→44 | 蟹柳碗里→锅里，无搬运动作 |
| S2 | ORPHAN_NOUN | L52 | 「吃口鱼」全篇唯一，83.8% 位置 |
| S2 | SPAN_CONFLICT | L35 vs L51 | 两周 vs 一个月 |
| S2 | PRONOUN_UNRESOLVED | L50 | 「他还是没忍住嘀咕」无具名先行 |
| S2 | SEQUENCE_SOURCE_MISMATCH | L7 vs L27 | 立论"最难的是朋友"，第三件事施力者变博主/评论区 |
| S3 | SCENE_STATE_NULL | L22 | 晚九点四十进场，散场"窗外全黑了" |
| S3 | UNRECOVERED_DETAIL | L8 | 八点零七分后再无回收 |

≥5 处 S2 + 1 处 S1 达标（S2×6+S3×2）。

## 五、绿样通过结果

- `fuben_run 作品/_regression/80b_大吃起时代_绿样/ --profile full` → **MECHANICAL: PASS，零 finding**（含题眼锚声明校验+台账对账）。
- 最小修法清单：大吃起时代标题/毛肚哥稳定称呼/蟹柳统一锅里/吃口蟹柳/都两周了/全亮/毛肚哥截图嘲/回了姑娘四个字-练完再吃/删八点零七分/充碳自嘲/教练现编老话自嘲。
- 台账对账闸正反验证：次数 9≠14 报 LEDGER_STALE；14=14 过（2026-09-22 `_measure` 去重修复后统一为新口径：毛肚哥 7、教练 5、姑娘 2，绿样复测仍 PASS）。

## 六、全库影响面（test_gates --works，53/53 过）

- SPOKEN_CHARACTER_COUNT：5 BLOCK（58b"备注四个字 别谢了"3字、62"回了四个字"6字、70"是你写的五个字"4字、71"回了两个字"3字、80"人生就两字"4字——均真错）+1 REVIEW（75 边界含糊）。
- 连续性 REVIEW 常态噪音：PRONOUN 16 条（均为低频配角，符合"配角 ≥2 次须稳定称呼"）+ THEME/ORPHAN/SPAN/SCENE/SEQUENCE 各 1（仅 80 号旧稿）。不设豁免目录，老稿真实问题如实暴露。
- 79 号重生成稿：PASS_WITH_REVIEW（仅 2 处已裁决句式候选），连续性锁零 finding。

## 七、剩余风险

1. THEME_CLASSES 词表以吃/耍/练/学为主，词表外题材自动模式不判（防误报），依赖设定.md 声明锚兜底——新题材写作时 profile 的题眼锚声明是硬交付物。
2. pronoun_unresolved 的贯穿线豁免（≥6 次）对"高频但中途换人"的极端写法不敏感，靠读通专项第 5 问人审兜底。
3. `--ledger` 计数是子串口径（"大姐"含"东北大姐"），别名设计须避免同段歧义；已用单测锁住去重行为。
4. 老稿（58b/62/70/71/75/80）的 SPOKEN/连续性 finding 是真实历史问题，本轮只拦不改稿；修复需走各自作品的返工流程。

## 回归基线命令

```bash
python3 scripts/fuben_run.py 作品/_regression/80a_大耍起时代_红样/正文.md --profile full   # 必须 FAIL
python3 scripts/fuben_run.py 作品/_regression/80b_大吃起时代_绿样/ --profile full            # 必须 PASS
python3 scripts/fuben_entity.py 作品/NN_主题/ --ledger                                       # 台账实测回填
python3 tests/test_fuben_entity.py                                                           # 17/17 过
python3 scripts/test_gates.py --works --corpus                                               # 全库
```
