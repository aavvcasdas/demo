---
trigger: always_on
---

# oh-story writing project rules

## 人生副本优先分流（本仓扩展）

人生副本 / 剧本人生 / 第二人称体验类口播先走 `story-short-write` 的轻量 profile；审稿走 `fuben-review`。这个分支不执行后文普通小说的细纲、付费点、追踪、去味配额与必读表，也不要求部署独立 Agent 才能写。只有实际可调用时才委派，solo 不冒称独立审核。
新建口播项目若已启用小说 hooks，且尚无可识别的正文/设定，在**作品目录**放 `.fuben.json`：`{"schema_version":1,"profile":"fuben"}`，避免首次写入被当普通小说；不要标到混合书库根。未启用 hooks 的直接创作不要求这个文件。普通小说分支保持原合同。

This workspace uses the oh-story web-fiction skill pack. Discover skills from
`.agents/skills/`; read the selected skill's `SKILL.md` before executing it and
load its references only when that skill instructs you to do so.

## Routing

- Long-form writing or continuation: `story-long-write`
- Short-form writing: `story-short-write`
- Long/short deconstruction: `story-long-analyze` / `story-short-analyze`
- Long/short market scan: `story-long-scan` / `story-short-scan`
- Remove AI-writing patterns: `story-deslop`
- Adversarial review: `story-review`
- Import an existing story: `story-import`
- Cover generation: `story-cover`
- Ambiguous story intent: `story`
- Project deployment/update: `story-setup`
- Reuse an authenticated Chrome session: `browser-cdp`

## Writing guardrails

- Keep every story artifact, temporary drafting segment, tracking transaction,
  and generated project directory inside the current workspace. Never create or
  continue an oh-story book under `~/.gemini/`, Antigravity's `scratch/`, or any
  other directory outside the workspace unless the user explicitly names that
  external destination.
- Before writing novel prose, long-form projects require the matching
  `大纲/细纲_第N章*.md`; short-form projects require `小节大纲.md`.
- Treat `追踪/_tracking-state.json` as the structured source of truth. Do not
  hand-edit its derived Markdown views.
- After prose is written, resolve every deterministic finding injected by the
  oh-story Antigravity hooks before continuing to another chapter.
- Prefer the seven deployed custom agents in `.agents/agents/` for specialist
  work. Call `invoke_subagent` with the agent's `TypeName`; if the runtime cannot
  start them, use the skill's documented solo/direct fallback instead of
  failing the workflow.

## Context recovery

At the start of a new conversation, and whenever context appears compacted or
story state is uncertain, locate the active book and read `追踪/上下文.md` before
continuing. The Antigravity external hook API has no PreCompact/PostCompact
event, so this rule is the mandatory recovery path after compaction.
