#!/usr/bin/env python3
"""自调度 loop：design → draft → review → lint → (ask) fuben-review。
用法: python3 scripts/fuben_run.py 作品/NN_xxx/
每闸 FAIL 就停，打印「该改哪一拍 / 哪一行」的清单，作者改完重跑；全 PASS 时提示向用户提问是否三方审核（铁律 B）。"""
import subprocess, sys, os, re
d = sys.argv[1].rstrip('/')
def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True); return p.returncode, p.stdout + p.stderr
steps = [
 ('L1 design', f'python3 scripts/fuben_loop.py design {d}/设定.md', '先改 设定.md（主线四行 / 信息差 / 换手 / 埋伏 / 三物证）'),
 ('L2 draft',  f'python3 scripts/fuben_loop.py draft {d}/', '按 BAD 行回对应拍改正文；对白>3% 先跑 lint --fix-list'),
 ('L2.5 review', f'python3 scripts/fuben_loop.py review {d}/', '结果前置 / 升级点 / 换手回收 / 反杀 ≥40 行 / 末动作'),
 ('L2.6 lint',  f'python3 scripts/fuben_lint.py {d}/ --fix-list', '说话行压转述 / 她他换人名 / 删术语 / 清单段每条 ≤7'),
 ('AI-patterns', f'node skills/story-review/scripts/check-ai-patterns.js --check {d}/正文.md', ''),
]
for name, cmd, hint in steps:
    rc, out = run(cmd)
    bad = [l for l in out.splitlines() if l.startswith('BAD') or 'blocking' in l and '0 blocking' not in l or l.startswith('L') and '→' in l]
    if name == 'AI-patterns':
        status = 'FAIL' if re.search(r'\[blocking\]', out) else 'PASS'
    else:
        status = 'PASS' if rc == 0 and not any(l.startswith('BAD') for l in out.splitlines()) and 'FAIL' not in out else 'FAIL'
    print(f'[{name}] {status}')
    if status == 'FAIL':
        print('\n'.join('   ' + l for l in bad[:25]))
        print(f'   ↳ {hint}\n   停在 {name}。改完重跑本命令。'); sys.exit(1)
print('\n全部机械闸 PASS。铁律 B：现在向用户提问「是否调用 fuben-review 三方审核？」（现在审 / 我先看稿）。不得自行开审。')
