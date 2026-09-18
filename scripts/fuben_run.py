#!/usr/bin/env python3
"""人生副本一键门禁（2026-09-19 扩展版）：

L1 design → L1.5 facts → L1.8 hype（爽点节奏）→ L2 draft → L2.5 review → L2.6 lint
→ L2.7 AI patterns（依赖锁校验）→ L2.8 质地（校准版）→ L2.9 颗粒度（测正文不测声明表）
→ L3.0 波形反收敛（连续三篇同签名 BLOCK）。

任何事实/时间线/指代闸失败都停止；通过后仍需按 fuben-review skill 做人工三方审核。
L2.8/L2.9/L3.0 为 2026-09-19 修复新增：旧七道闸测事实与结构，测不到「正文是否落在
具体细节上」（66–72 成稿全绿但静默失败的层）；波形闸防门禁被做成配额后的同质化收敛。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit("用法: python3 scripts/fuben_run.py 作品/NN_xxx/")

directory = sys.argv[1].rstrip("/")
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AI_PATTERNS = "skills/story-review/scripts/check-ai-patterns.js"


def verify_lock() -> str:
    """跨 skill 依赖锁：check-ai-patterns.js 必须存在于 skills/_manifest.json 且 sha256 一致。"""
    manifest_path = os.path.join(root, "skills", "_manifest.json")
    try:
        manifest = json.load(open(manifest_path, encoding="utf-8"))["locked"]
    except FileNotFoundError:
        raise SystemExit(f"[依赖锁] FAIL 缺 skills/_manifest.json——上游 skill 文件引用必须登记，禁止裸路径耦合")
    entry = manifest.get(AI_PATTERNS)
    if not entry:
        raise SystemExit(f"[依赖锁] FAIL manifest 未登记 {AI_PATTERNS}")
    target = os.path.join(root, AI_PATTERNS)
    if not os.path.exists(target):
        raise SystemExit(
            f"[依赖锁] FAIL {AI_PATTERNS} 不存在（上游 story-review 包残缺？）。重装 oh-story-claudecode 后复核 manifest。"
        )
    digest = hashlib.sha256(open(target, "rb").read()).hexdigest()
    if digest != entry["sha256"]:
        raise SystemExit(
            f"[依赖锁] FAIL {AI_PATTERNS} 内容已变（sha256 不一致）：上游更新过该脚本。"
            "先人工复核其 --check 输出的 [blocking] 语义没变，再按 skills/_manifest.json 说明 relock，不许静默放行。"
        )
    return target


steps = [
    ("L1 design", ["python3", "scripts/fuben_loop.py", "design", f"{directory}/设定.md"], "先补事实锁、状态台账、主线与情绪节拍表"),
    ("L1.5 facts", ["python3", "scripts/fuben_loop.py", "facts", directory], "先统一玩法、单价、频率、日期、数量；不要用润色掩盖矛盾"),
    ("L1.8 爽点节奏", ["python3", "scripts/fuben_hype.py", directory], "先补爽点表：位置 / 情绪值 / 正文锚点；峰值 25–48%，无爽点不许进正文"),
    ("L2 draft", ["python3", "scripts/fuben_loop.py", "draft", directory], "按 BAD 对应到具体节；不为凑行数增加对白或环境"),
    ("L2.5 review", ["python3", "scripts/fuben_loop.py", "review", directory], "检查转场触发、状态变化、呼应和结尾动作"),
    ("L2.6 lint", ["python3", "scripts/fuben_lint.py", directory, "--fix-list"], "压缩对白、补身份称呼、删术语和模板过渡句"),
    ("L2.7 AI-patterns", ["node", AI_PATTERNS, "--check", f"{directory}/正文.md"], "处理 blocking AI 模式；不改变事实和结局"),
    ("L2.8 质地", ["python3", "scripts/check_fuben_texture.py", f"{directory}/正文.md"], "对照 thresholds JSON 的样本来源补感官/数字/具名细节；阈值不许回降"),
    ("L2.9 颗粒度", ["python3", "scripts/fuben_granularity.py", f"{directory}/正文.md"], "测正文不测声明表：阿拉伯数字、密度、对白占比；汉字金额改回阿拉伯"),
    ("L3.0 波形反收敛", ["python3", "scripts/fuben_waveform.py", "--check", directory], "连续三篇同签名必须换骨架（开场/峰值/首大/谷底/收束 ≥2 维不同）"),
]

for name, command, hint in steps:
    if name == "L2.7 AI-patterns":
        verify_lock()  # 断链/改哈希在此直接 SystemExit，不静默降级
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    except FileNotFoundError as exc:
        print(f"[{name}] FAIL\n   找不到命令: {exc}")
        raise SystemExit(1)
    output = result.stdout + result.stderr
    is_ai = name == "L2.7 AI-patterns"
    failed = ("[blocking]" in output) if is_ai else result.returncode != 0
    print(f"[{name}]", "FAIL" if failed else "PASS")
    if failed:
        print("\n".join("   " + line for line in output.splitlines()[-40:]))
        print(f"   ↳ {hint}\n   停在 {name}。改完重跑本命令。")
        raise SystemExit(1)
    if is_ai and result.returncode != 0:
        print("   advisory only: 已通读，短行体不因 advisory 机械注水。")

print("\n全部机械闸 PASS（含 L2.8 质地 / L2.9 颗粒度 / L3.0 波形）。现在调用 fuben-review 做人工三方审核；审核前不要宣称成稿通过。")
