# GitHub 短视频 Agent：借了什么，接到了哪里

本轮只研究并改造 Agent 方法，**没有写新样稿、修稿件字数或制作新的机检报告**。目标是让 Agent 真正执行强开头、爽感兑现、伏笔与侧面推进，而不是多写几句“要好看”。

## 1. 从设计 Agent 借“候选竞争＋兑现路径”

来源：`dyzsasd/writing-loop`，固定版本 `56364527c8f7302a8d26e1675874a25303a6d28e`。

它的 `story-designer-agent` 在设计阶段比较不同反转、危机和尾钩方案，并保留弃案原因；`craft-rules.md` 要求用于揭示的线索先进入正文，不能只藏在人物设定里。[3](https://github.com/dyzsasd/writing-loop)

**本仓采用：**新题先内部比较不同驱动力的短开场，每个都要接得上正文中的兑现；没有后续可演的噱头淘汰。先想清兑现，再倒推可见线索。不是给用户扔多个完整稿，也不复制长剧的伏笔数量和跨集配额。

源码定位：
- [3](https://github.com/dyzsasd/writing-loop/blob/56364527c8f7302a8d26e1675874a25303a6d28e/skills/story-designer-agent/SKILL.md#L119-L127)：设计阶段的候选竞争。
- [3](https://github.com/dyzsasd/writing-loop/blob/56364527c8f7302a8d26e1675874a25303a6d28e/references/craft-rules.md#L30-L44)：伏笔先埋入正文与回收。

## 2. 从真实调用链借“不同问题退回不同阶段”

来源：`YingaoZhang/short_drama_agent`，固定版本 `c7688f3cacf84106a6909ff8de8106811fbcabdb`。本轮沿 `workflow.py → routing.py → lead_writer / quality_reviewer / revision_editor → llm_helpers` 读取相关调用与提示片段。

其流程将严重的主线问题退回世界构建，节奏/关键剧情问题退回主笔，轻微问题交给局部改稿；改稿后回审，不是所有问题都换词处理。[9](https://github.com/YingaoZhang/short_drama_agent)

**本仓采用：**切口与主线失效回策划；兑现被跳过、伏笔未落地、侧面成捧哏回主笔重写关键场；只有表达问题才局部润色。审读必须给具体原句和修订目标，主笔实际收到这些反馈。

源码定位：
- [9](https://github.com/YingaoZhang/short_drama_agent/blob/c7688f3cacf84106a6909ff8de8106811fbcabdb/backend/app/graph/workflow.py#L14-L45)：节点与回审边。
- [9](https://github.com/YingaoZhang/short_drama_agent/blob/c7688f3cacf84106a6909ff8de8106811fbcabdb/backend/app/graph/routing.py#L4-L22)：分层退回。
- [9](https://github.com/YingaoZhang/short_drama_agent/blob/c7688f3cacf84106a6909ff8de8106811fbcabdb/backend/app/graph/nodes/revision_editor.py#L33-L58)：局部改稿接收实际审查意见。

**没有原样搬这个 Demo。**它的审核节点存在工具快速分支及台词数量判断，模型辅助函数也有固定结果兜底；这些不能证明内容好看，本仓没有引入。借的是返工分工，不是其 PASS 或预置剧情。[9](https://github.com/YingaoZhang/short_drama_agent/blob/c7688f3cacf84106a6909ff8de8106811fbcabdb/backend/app/graph/nodes/quality_reviewer.py#L61-L130) [9](https://github.com/YingaoZhang/short_drama_agent/blob/c7688f3cacf84106a6909ff8de8106811fbcabdb/backend/app/graph/nodes/llm_helpers.py#L25-L65)

## 3. 从编剧手艺借“策略改变＋有后果的侧面反应”

来源：`zenstory-ai/drama-skills`，固定版本 `0e8929881bb59248618c4f402707c64723adc017`。重点读场景策略、主角主动性、反应后果、台词权力变化及去模板修订段，不声称完整审计了该项目。

这些段落要求阻力能迫使人物改变策略，转向改变下一动作；角色反应要影响选择和关系。旁人或道具不能恰好替主角完成最难的一步；去模板也不是替换几个常用词。[1](https://github.com/zenstory-ai/drama-skills)

**本仓采用：**把爽点写成连续交锋和局面转变；审读追问“他先前能做什么，现在为什么不能再做”。侧面反应放大主角行动的结果，不用全员震惊代替兑现，也不让配角包办主角的反击。

源码定位：
- [1](https://github.com/zenstory-ai/drama-skills/blob/0e8929881bb59248618c4f402707c64723adc017/skills/short-drama-write/references/script-craft.md#L104-L180)：有效阻力、换策与主角主动性。
- [1](https://github.com/zenstory-ai/drama-skills/blob/0e8929881bb59248618c4f402707c64723adc017/skills/short-drama-write/references/script-craft.md#L254-L264)：反应承载后果。
- [1](https://github.com/zenstory-ai/drama-skills/blob/0e8929881bb59248618c4f402707c64723adc017/skills/short-drama-write/references/dialogue-craft.md#L245-L263)：话语权的可见变化。
- [1](https://github.com/zenstory-ai/drama-skills/blob/0e8929881bb59248618c4f402707c64723adc017/skills/short-drama-review/references/anti-template-repair.md#L13-L62)：从因果、策略而非同义词处理模板感。

## 现在仓库里怎样执行

```text
当前请求是研究/改造Agent → 借鉴与接入，到此结束，不自行生成作品

当前请求是写稿
  → 主控：选择能接到兑现的开场
  → narrative-writer：展开关键戏，落伏笔与侧面后果
  → story-architect：创作审读，定位追看断点
  → 按问题退回策划 / 关键场重写 / 局部润色

人物反应薄弱时才让 character-designer 专项补强
```

已接入的位置：

- [人生副本 Agent 方法](../skills/story-short-write/references/genre-styles/人生副本_Agent方法.md)：实际分工、输入、返工目标。
- [主profile v13](../skills/story-short-write/references/genre-styles/人生副本实录.md) 与 [写作入口](../skills/story-short-write/SKILL.md)：指向并执行该流程，不是另放一篇无人读取的资料。
- [审核入口](../skills/fuben-review/SKILL.md)：按创作问题层级返工，明确独立审读与改稿分开。
- `story-setup/references/{templates,opencode,codex}/agents/` 中现有的 `story-architect`、`narrative-writer`、`character-designer`：已在副本提前分流内写入各自职责，不再只有“绕过小说规则”的说明；没有新增一个空壳 Agent 名称。
- [根路由](../AGENTS.md) 与 [调用方参考选择](../skills/story-setup/references/agent-references/agent-reference-profiles.md)：按任务动作分流，并传递对应方法片段。

采用的是重新表述、按人生副本适配的方法，没有导入外部代码或安装第三方运行平台。已经部署过的项目需通过原有 `story-setup` 同步模板；本轮没有擅自安装或启动宿主。模板接入不等于宿主已部署；本轮没有运行独立模型/观众实验，不宣称这些方法已证明流量提升。
