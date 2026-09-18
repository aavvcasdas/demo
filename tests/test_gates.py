#!/usr/bin/env python3
"""门禁脚本单元测试（pr C · P2：门禁自己不能没有测试网）。

覆盖：
1. 校准阈值 JSON 结构与数值 sanity（每项带样本来源）；
2. 词表外置 JSON 可解析、三表非空；
3. 质地闸双标准回归（重跑校准器逻辑的关键断层：39 篇通过率 ≥80% 且 66–72 全部拦截）——
   用全仓真实文件跑，防阈值被悄悄回降；
4. 颗粒度传感器判别力（构造微型文本：数字重金属风 vs 全汉字漂移风）；
5. _audit_scope.json 契约审计范围感知（在临时目录构造 拆文库 树，短/长两篇验证）；
6. 依赖锁 manifest 与 check-ai-patterns.js 的 sha256 一致（上游被改时必须红）。

运行：python3 -m pytest tests/ -q   或   python3 tests/test_gates.py（无 pytest 时的独立跑法）
"""
import hashlib
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import check_fuben_texture as tex  # noqa: E402
import fuben_granularity as gran  # noqa: E402

TH_PATH = os.path.join(ROOT, "scripts", "fuben_texture_thresholds.json")
WL_PATH = os.path.join(ROOT, "scripts", "fuben_wordlists.json")


def test_thresholds_schema_and_sources():
    data = json.load(open(TH_PATH, encoding="utf-8"))
    th = data["thresholds"]
    for key in ("word_count", "sens_per_kk", "digits_total", "digit_density_per_kk",
                "arabic_ratio", "price_count", "brand_count", "dialogue_pct", "meme_count", "opener_hit"):
        assert key in th, f"阈值缺 {key}"
    assert th["word_count"]["min"] >= 1000 and th["word_count"]["max"] <= 6000
    assert 0.3 <= th["arabic_ratio"]["min"] <= 1.0
    assert th["dialogue_pct"]["max"] <= 5.0  # 39 篇 max=2.0，上限不许超过 5（防回降通胀）
    src = data.get("样本来源", {})
    for key in ("word_count", "sens_per_kk", "digit_density_per_kk", "arabic_ratio", "dialogue_pct"):
        assert key in src and re.search(r"\d", src[key]), f"阈值 {key} 缺样本来源数字"


def test_wordlists_externalized():
    lists = json.load(open(WL_PATH, encoding="utf-8"))["lists"]
    for key in ("sens", "brand", "meme", "han_price"):
        assert lists[key]["pattern"], f"词表 {key} 为空"
        assert lists[key]["来源"], f"词表 {key} 缺来源说明"


def test_calibration_acceptance_regression():
    """39 篇原稿复合通过率 ≥80% 且 66–72 全部被拦（任一失败即红，防阈值被回降）。"""
    import glob
    fails_ok = fails_bad = 0
    for f in glob.glob(os.path.join(ROOT, "分篇", "*.txt")):
        bad, _ = tex.evaluate(f)
        fails_ok += bad < 2
    total = len(glob.glob(os.path.join(ROOT, "分篇", "*.txt")))
    assert total >= 39, f"分篇样本不足 39：{total}"
    assert fails_ok / total >= 0.80, f"原稿通过率 {fails_ok}/{total} <80%"
    for f in glob.glob(os.path.join(ROOT, "作品", "6[6-9]_*", "正文.md")) + \
             glob.glob(os.path.join(ROOT, "作品", "7[0-2]_*", "正文.md")):
        if "71_" in f:  # 71 已按同方重写为合规稿，属实验件豁免
            continue
        bad, _ = tex.evaluate(f)
        fails_bad += bad >= 2
        assert bad >= 2, f"已知失败批次 {os.path.basename(os.path.dirname(f))} 竟通过质地闸（bad={bad}）"
    assert fails_bad >= 8, "66–72 拦截数异常"


def test_granularity_discriminates():
    with tempfile.TemporaryDirectory() as td:
        good = os.path.join(td, "good.md")
        drift = os.path.join(td, "drift.md")
        open(good, "w", encoding="utf-8").write("打卡机跳到8点59分57秒\n新卡套一股塑料味\n金额1280元按12口报\n白醋7块5一瓶\n" * 8)
        open(drift, "w", encoding='utf-8').write("那天夜里很晚了\n他说你是不是故意的\n她说没有的事\n他问你话呢\n" * 8)
        assert gran.evaluate(good)[0] == 0, "数字基因正常的稿子应 PASS"
        assert gran.evaluate(drift)[0] >= 3, "全汉字漂移+高对白稿应 FAIL"


def test_audit_scope_awareness(tmp_path=None):
    import subprocess
    tmp = tempfile.mkdtemp() if tmp_path is None else str(tmp_path)
    lib = os.path.join(tmp, "拆文库")
    os.makedirs(os.path.join(lib, "短篇甲", "原文"))
    os.makedirs(os.path.join(lib, "长篇乙", "原文"))
    open(os.path.join(lib, "短篇甲", "原文", "a.txt"), "w", encoding="utf-8").write("短" * 5000)
    open(os.path.join(lib, "长篇乙", "原文", "b.txt"), "w", encoding="utf-8").write("长" * 800000)
    json.dump({"entries": {"长篇乙": {"scope": "long-analyze", "status": "in-progress", "reason": "在途"}}},
              open(os.path.join(lib, "_audit_scope.json"), "w", encoding="utf-8"), ensure_ascii=False)
    audit = open(os.path.join(ROOT, "scripts", "audit_analyze_lib.py"), encoding="utf-8").read()
    assert "_audit_scope.json" in audit and "LONG" in audit, "审计脚本未做范围感知"
    out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "audit_analyze_lib.py")],
                         cwd=tmp, capture_output=True, text=True)
    assert "PENDing" in out.stdout and "BAD" not in out.stdout.split("BAD count")[0].replace("BAD ", ""), out.stdout[-500:]
    assert "BAD count: 1 " in out.stdout or "BAD count: 1" in out.stdout, out.stdout[-200:]  # 短篇甲缺文件 → 1 BAD


def test_skill_dependency_lock_matches():
    manifest = json.load(open(os.path.join(ROOT, "skills", "_manifest.json"), encoding="utf-8"))["locked"]
    for rel, entry in manifest.items():
        target = os.path.join(ROOT, rel)
        assert os.path.exists(target), f"依赖锁登记的文件不存在: {rel}"
        digest = hashlib.sha256(open(target, "rb").read()).hexdigest()
        assert digest == entry["sha256"], f"{rel} 已变更但未 relock——上游更新须人工复核后重锁"


if __name__ == "__main__":
    # 无 pytest 环境的独立跑法（CI 用 pytest，本函数用于本地快速复验）
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
