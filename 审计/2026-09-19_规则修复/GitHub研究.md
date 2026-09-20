# GitHub 实现研究：借原则，不借“必爆”背书

本轮按相关性与公开关注度筛选，星数只代表本次 GitHub API 快照，不是“顶级”认证或创作质量排名。应用、制作工具、叙事 Skill 和电商模板不能混为同一赛道。所有实际检查的文件已固定到 commit；没有安装或运行外部仓库代码，没有实测其流量效果。

## 主要对照

| 项目 / 快照星数 | 实际读到的实现 | 本次采用与不采用 |
|---|---|---|
| [HBAI-Ltd/Toonflow-app](https://github.com/HBAI-Ltd/Toonflow-app/blob/e03cf590eb0cab63534a4040db9acb4ec95b42a6/data/skills/script_agent_decision.md) · 15,786★<br>热门短剧应用，不等同于口播 Skill | 实际读了决策/剧本 Agent 指令，并检查 scriptAgent/index.ts 载入 prompt、工具与子 Agent 的调用。调度与执行分层，执行失败不得冒充完成；但初始化逐项追问和 3-15-45 节奏是它自己的制作策略。 | 采用阶段边界和失败显式化；不照搬固定钩子秒数、打脸公式、每集字数、必须分集。 |
| [eternityspring/shuohao-skills](https://github.com/eternityspring/shuohao-skills/blob/7ebef4f2f53159ee1eaaec2793271a114a8be8cc/skills/novel-script/SKILL.md) · 3,566★<br>高相关、受关注的短剧 Skill 集 | 读 novel-script/SKILL.md，并检查实际 validate/gateReport 与 selftest 源码：编剧与分镜分离，确定性检查有击穿用例；它仍有10道剧本门和句长/钩子位置限制。 | 采用脚本可测、职责分离、估时边界；不把短剧拍摄契约当成人生副本的通用文风。未运行其外部测试，不引用“154断言”作已验证结果。 |
| [zenstory-ai/drama-skills](https://github.com/zenstory-ai/drama-skills/blob/0e8929881bb59248618c4f402707c64723adc017/skills/short-drama-write/SKILL.md) · 2,063★<br>高相关、受关注的中文短剧 Skill 集 | 完整读取 short-drama-write 与 review 主入口，并读隔离生成评测提示。默认最小输入、按需知识、没有的叙事机关不强行补；审查与改稿分开，缺输入可 PROVISIONAL。 | 最直接采用其条件化写作思路、保留原文、定点修改及诚实自检；评测隔离方法用于待执行的直接提示词对照设计。 |
| [alchaincyf/huashu-skills](https://github.com/alchaincyf/huashu-skills/blob/49a55ba8a975ebda6bb55ea5ca4388942e3f6f18/huashu-douyin-script/SKILL.md) · 1,572★<br>相关抖音电商工作流，不是叙事口播效果榜 | 读取 huashu-douyin-script 主入口：真实竞品视频→视听拆解→公式确认→脚本/分镜→审校；输入偏产品、种草与投放，需要视频、登录和外部模型。 | 采用真实素材、视觉/口播分开、关键方向确认；不强迫人生副本套卖点/CTA/15秒广告，不假装本环境已下载分析视频。 |
| [A-cat-with-carrots/OnlyShot](https://github.com/A-cat-with-carrots/OnlyShot/blob/75c57f2fff6e2b3ab14004ce635a445e416c9b27/SKILL.md) · 282★<br>相关制作流程样本；规模较小 | 检查 SKILL 的阶段架构、用户确认与制作边界：创作→分镜图→出片；同时有严格自评分/黑名单与“必爆”式宣传。 | 只采用制作前确认和阶段分离；不采用自评50/60或零黑名单命中作为客观质量，也不把必爆当证据。 |
| [openai/skills](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.system/skill-creator/SKILL.md) · 27,474★<br>通用 Skill 设计参考，非中国短视频案例 | 读取 skill-creator 的精简、自由度、渐进加载原则：有多种可行写法的任务留较大自由度，易出错的机械操作用确定工具。 | 实际拆掉写作配额，把精确检查放在代码中；没有要求写作者每次读全部脚本、生产资料和历史规则。 |
| [RRR666888000/an-video-director](https://github.com/RRR666888000/an-video-director/blob/cb2fb1e7a530e80eb42f2ceaff4d93575c2f52d4/references/testing.md) · 0★<br>0星小样本，不称顶级 | 读取 Skill 以及 story-persona/testing 引用。按任务加载，自然内容不强制销售；版本、目的、观察窗口与来源分开，缺失值保留未知。 | 采用能力/数据边界；不可将它的理念或仓库存在当成已验证平台增长效果。 |
| [samjia12/skill-video-script](https://github.com/samjia12/skill-video-script/blob/ebbd7dd129349f411cae79793b2a805bf74a170a/src/video_script/generator.py) · 0★<br>0星小样本，不称顶级 | 读取 Skill 与实际 generator.py：默认离线模板，明确 template/llm 分支，缺配置或输出数量不符抛错误；固定三种带货风格。 | 借鉴错误显式化；不把三种固定带货模板变成口播创作强制产物。未执行远端代码。 |
| [1-SKILL/jiaoben](https://github.com/1-SKILL/jiaoben/blob/f4aae40fd9e19be6589e82bf186e2199d2580663/SKILL.md) · 2★<br>2星小样本/营销对照，不称顶级 | 读取 SKILL.md 与当前规则文件；包含强模板、商业升级引导与营销式效果说法。 | 不采纳效果承诺，不执行其远程安装/拉规则指令；不能用检索排名冒充权威。 |

## 与本次修复的对应

1. 写作入口先分流；副本不先读小说的付费点、12列大纲和去味清零表。主 profile 从467行降至45行，正文创作不要求新增设计表。
2. 规则分层：可证明的机械错误、语义候选、描述值、工具失败分开；脚本不以关键词代替评审。
3. 编剧、审稿、媒体制作、发布和数据归因分阶段。哈希证据只用于发布，不给创作另加一套沉重记录。
4. 保留软件红/绿/异常样本和整个库的动态覆盖；不只选10篇本来能过的作品。
5. 单 Agent 明说 solo；没有真正调用独立 reviewer、视频分析、TTS 或后台，就不写已完成。

## 不做的推断

- 不是“热门项目都少规则”：shuohao 和 Toonflow 也有很多限制，关键是是否适合任务，以及是否把制作契约错当剧作规律。
- 不是“用了它们的技巧所以一定更好”：本次只验证了本仓软件与文本兼容性。生成质量、听感和平台结果需要不同实验。
- 小项目只作为实现样本/反例，不能冒称顶级。星数可能随时间变化。

原始元数据、commit、各文件SHA及永久链接：`github_research.json`。少量定位摘录：`research_excerpts.json`。缓存目录只是阅读临时件，未作为生产依赖。
直接提示词对照计划：`evaluations/人生副本对照实验.md`（明确标为未执行）。
