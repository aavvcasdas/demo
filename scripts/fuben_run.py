#!/usr/bin/env python3
"""人生副本一键门禁：design → facts → draft → review → lint → AI patterns。

任何事实/时间线/指代闸失败都停止；通过后仍需按 fuben-review skill 做人工三方审核。
"""
from __future__ import annotations

import os
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit("用法: python3 scripts/fuben_run.py 作品/NN_xxx/")

directory = sys.argv[1].rstrip("/")
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

steps = [
    ("L1 design", ["python3", "scripts/fuben_loop.py", "design", f"{directory}/设定.md"], "先补事实锁、状态台账、主线与八拍路线图"),
    ("L1.5 facts", ["python3", "scripts/fuben_loop.py", "facts", directory], "先统一玩法、单价、频率、日期、数量；不要用润色掩盖矛盾"),
    ("L2 draft", ["python3", "scripts/fuben_loop.py", "draft", directory], "按 BAD 对应到具体拍；不为凑行数增加对白或环境"),
    ("L2.5 review", ["python3", "scripts/fuben_loop.py", "review", directory], "检查转场触发、状态变化、呼应和结尾动作"),
    ("L2.6 lint", ["python3", "scripts/fuben_lint.py", directory, "--fix-list"], "压缩对白、补身份称呼、删术语和模板过渡句"),
    ("AI-patterns", ["node", "skills/story-review/scripts/check-ai-patterns.js", "--check", f"{directory}/正文.md"], "处理 blocking AI 模式；不改变事实和结局"),
]

for name, command, hint in steps:
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    except FileNotFoundError as exc:
        print(f"[{name}] FAIL\n   找不到命令: {exc}")
        raise SystemExit(1)
    output = result.stdout + result.stderr
    is_ai = name == "AI-patterns"
    failed = ("[blocking]" in output) if is_ai else result.returncode != 0
    print(f"[{name}]", "FAIL" if failed else "PASS")
    if failed:
        print("\n".join("   " + line for line in output.splitlines()[-40:]))
        print(f"   ↳ {hint}\n   停在 {name}。改完重跑本命令。")
        raise SystemExit(1)
    if is_ai and result.returncode != 0:
        print("   advisory only: 已通读，短行体不因 advisory 机械注水。")

print("\n全部机械闸 PASS。现在调用 fuben-review 做人工三方审核；审核前不要宣称成稿通过。")
