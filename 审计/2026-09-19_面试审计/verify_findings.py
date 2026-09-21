#!/usr/bin/env python3
"""Read-only repository audit probes; NOT a production release gate.

Run from any directory:
  python3 审计/2026-09-19_面试审计/verify_findings.py

Writes only audit_results.json and audit_log.txt beside this script (or --out-dir).
All fault injection / CSV writes use TemporaryDirectory, never production files.
Observed defects are evidence, not tests that should keep passing after a fix.
No network access, publication, hook installation, or story edits are performed.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))
import fuben_loop  # noqa: E402
import fuben_hype  # noqa: E402
from fuben_density import density  # noqa: E402

ORIGINAL_RUN = subprocess.run
LOG: list[str] = []
RESULTS: dict = {}


def run(name: str, command: list[str], env: dict | None = None) -> dict:
    result = ORIGINAL_RUN(command, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", timeout=90, env=env)
    entry = {"command": command, "returncode": result.returncode,
             "stdout": result.stdout, "stderr": result.stderr}
    LOG.extend([f"\n=== {name} ===", "$ " + " ".join(command),
                f"exit={result.returncode}", result.stdout, result.stderr])
    return entry


def tracked_hashes() -> dict[str, str]:
    output = ORIGINAL_RUN(["git", "ls-files", "-z"], cwd=ROOT,
                          capture_output=True, check=True).stdout.decode()
    # Audit artifacts are the only intentionally writable outputs.
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in output.split("\0") if name and not name.startswith("审计/")
            and (ROOT / name).is_file()}


def capture_function(fn, *args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        rc = fn(*args)
    return {"returncode": rc, "stdout": stream.getvalue()}


def defect_probes(latest: Path) -> dict:
    probes = {}
    with tempfile.TemporaryDirectory(prefix="fuben_readonly_audit_") as temp:
        fixture = Path(temp)
        setting = (latest / "设定.md").read_text(encoding="utf-8")
        body = (latest / "正文.md").read_text(encoding="utf-8")
        # 1. Individual review stage: do not confuse this with a full pipeline run.
        start, end = setting.index("## 呼应表"), setting.index("## 场面表")
        (fixture / "设定.md").write_text(setting[:start] + setting[end:], encoding="utf-8")
        (fixture / "正文.md").write_text(
            "今天体验的人生副本是\n测试的人\n桌面一片白\n红色圆点落在纸上\n墨迹停在中央\n", encoding="utf-8")
        result = capture_function(fuben_loop.review, str(fixture))
        result["false_condition_printed_ok"] = any(
            line.startswith("OK") and line.endswith("False")
            for line in result["stdout"].splitlines())
        probes["review_argument_order"] = result

        # 2. Same environmental-word gap: advisory in draft, blocking in lint.
        (fixture / "正文.md").write_text(
            "今天体验的人生副本是\n测试的人\n你整理材料\n" * 16, encoding="utf-8")
        probes["environment_gap_draft"] = run("environment gap: draft", [
            sys.executable, "scripts/fuben_loop.py", "draft", str(fixture)])
        probes["environment_gap_lint"] = run("environment gap: lint", [
            sys.executable, "scripts/fuben_lint.py", str(fixture)])

        # 3. Real Python gates on real 78; only Node checker path is fault-injected.
        # Node actually returns MODULE_NOT_FOUND. We do not fake a successful gate.
        observations = {}
        def missing_checker(command, *args, **kwargs):
            if command[0] == "node" and "check-ai-patterns.js" in command[1]:
                command = list(command)
                command[1] = str(fixture / "does-not-exist.js")
                output = ORIGINAL_RUN(command, *args, **kwargs)
                observations.update(node_returncode=output.returncode,
                                    node_stdout=output.stdout, node_stderr=output.stderr)
                return output
            return ORIGINAL_RUN(command, *args, **kwargs)
        stream, rc = io.StringIO(), 0
        with patch("sys.argv", ["scripts/fuben_run.py", str(latest)]), \
             patch("subprocess.run", side_effect=missing_checker), \
             contextlib.redirect_stdout(stream):
            try:
                runpy.run_path(str(ROOT / "scripts/fuben_run.py"), run_name="__main__")
            except SystemExit as exc:
                rc = exc.code
        probes["node_failure_runner_fail_open"] = {
            **observations, "runner_returncode": rc, "runner_stdout": stream.getvalue()}

        # 4. Demonstrates coverage boundary, not a violation of runner's own stated scope.
        (fixture / "正文.md").write_text(body, encoding="utf-8")
        (fixture / "设定.md").write_text(setting.split("## 场面表")[0], encoding="utf-8")
        (fixture / "审核报告.md").write_text(
            "自检\n## VERDICT: BLOCK\n新稿缺场面表，TTS 听感 QA 未完成。\n", encoding="utf-8")
        probes["mechanical_gate_not_release_gate"] = run("mechanical gate ignores human artifacts", [
            sys.executable, "scripts/fuben_run.py", str(fixture)])
        probes["missing_scene_legacy_exemption"] = run("missing scene no date classification", [
            sys.executable, "scripts/fuben_scene_check.py", str(fixture)])

        # 5. Current record() appends its nine features under the existing ten-feature header.
        data = fixture / "_数据.csv"
        data.write_text((ROOT / "作品/_数据.csv").read_text(encoding="utf-8"), encoding="utf-8")
        with patch.object(fuben_loop, "DATA", str(data)):
            capture = capture_function(fuben_loop.record, ["78", "10", "100"])
            with data.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            error = None
            try:
                capture_function(fuben_loop.report)
            except Exception as exc:
                error = {"type": type(exc).__name__, "message": str(exc)}
        probes["legacy_record_schema_drift"] = {
            "existing_header": rows[0], "new_row": rows[-1],
            "header_columns": len(rows[0]), "row_columns": len(rows[-1]),
            "record_stdout": capture["stdout"], "report_error": error}

        # 6. Non-ambiguous Chinese numbers; avoid colloquial '二百五' in expected values.
        cases = {"二百": 200, "二百五十": 250, "三百六十": 360,
                 "一千二百": 1200, "一万": 10000}
        probes["hype_chinese_number_parser"] = [
            {"input": text, "expected": expected, "actual": fuben_hype._cn_value(text)}
            for text, expected in cases.items()]

    env = dict(os.environ)
    env.pop("FUBEN_CPS", None)
    probes["shotmap_cps_cli"] = run("documented --cps flag", [
        sys.executable, "scripts/fuben_shotmap.py", str(latest), "--cps", "6.4"], env=env)
    LOG.append("\n=== isolated probes summary ===\n" + json.dumps(probes, ensure_ascii=False, indent=2))
    return probes


def csv_audit() -> dict:
    with (ROOT / "作品/_数据_v2.csv").open(encoding="utf-8", newline="") as file:
        all_rows = list(csv.reader(file))
    header = all_rows[0]
    numeric = [*header[4:20], *header[25:35]]
    qualities = {"backend_export", "manual", "legacy_unverified", "pending_backend",
                 "derived_script", "candidate_patched", "company_delivery", "original", "approved_v2"}
    rows = []
    for line, values in enumerate(all_rows[1:], 2):
        mapped = dict(zip(header, values))
        defects = []
        if len(values) != len(header):
            defects.append(f"column count {len(values)} != {len(header)}")
        for key in numeric:
            value = mapped.get(key)
            if value and not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
                defects.append(f"numeric field {key}={value!r}")
        quality = mapped.get("data_quality", "")
        if quality and quality not in qualities:
            defects.append(f"unexpected data_quality={quality!r}")
        timestamp = mapped.get("快照时间", "")
        if timestamp and not re.match(r"\d{4}-\d{2}-\d{2}", timestamp):
            defects.append(f"snapshot timestamp not date: {timestamp!r}")
        rows.append({"line": line, "id": mapped.get("id"), "columns": len(values),
                     "raw_values": values, "mapped_fields": mapped, "defects": defects})
    return {"header": header, "expected_columns": len(header), "row_count": len(rows),
            "wrong_width_count": sum(row["columns"] != len(header) for row in rows),
            "rows_with_detected_schema_or_type_defects": sum(bool(row["defects"]) for row in rows),
            "validation_scope": "limited width/type checks, not full semantic validation", "rows": rows}


def latest_measurements() -> dict:
    measurements, variant_ai = [], {}
    for prefix in ("75_", "76_", "77_", "78_"):
        for directory in sorted((ROOT / "作品").glob(prefix + "*")):
            files = [directory / "正文.md", directory / "正文_3分钟版.md",
                     *sorted(directory.glob("切条D0/*/正文.md"))]
            for path in files:
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8")
                tokens, chars, per_k = density(text)
                measurements.append({
                    "path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "fuben_density_chars": chars, "han_only_chars": len(re.findall(r"[\u4e00-\u9fff]", text)),
                    "numeric_tokens": tokens, "numeric_density_per_k": per_k,
                    "estimate_seconds_at_6_4_cps": round(chars / 6.4, 2),
                    "audio_or_video_measured": False})
                if path != directory / "正文.md":
                    variant_ai[str(path.relative_to(ROOT))] = run("variant AI style check", [
                        "node", "skills/story-review/scripts/check-ai-patterns.js", "--json",
                        "--fail-on=blocking", str(path)])
    clip = (ROOT / "作品/78_Codex上瘾的人/切条D0/条1_罚单是全车的/正文.md").read_text(encoding="utf-8")
    clip_offsets = []
    for anchor in ("四个人 合租一个大号", "同车有人挂了个大的", "早上七点你点开手机", "全车 429", "完整版在主页"):
        chars = density(clip[:clip.index(anchor)])[1]
        clip_offsets.append({"anchor": anchor, "preceding_chars": chars,
                             "nominal_start_seconds_at_6_4_cps": round(chars / 6.4, 2)})
    assertions = [
        ("作品/75_人生副本作者的一天/正文.md", "你在封皮上写了两个字\n弃", "弃", 2),
        ("作品/75_人生副本作者的一天/正文.md", "你打了六个字\n替她谢谢你", "替她谢谢你", 6),
        ("作品/75_人生副本作者的一天/正文.md", "第二行 你打了两个字\n你自己", "你自己", 2),
        ("作品/75_人生副本作者的一天/正文_3分钟版.md", "第二行 你打了两个字\n你自己", "你自己", 2),
        ("作品/77_出道即巅峰却泯然众人的一生/正文_3分钟版.md", "晚上你发了条微博 七个字\n现在我就是世一中", "现在我就是世一中", 7),
        ("作品/77_出道即巅峰却泯然众人的一生/正文_3分钟版.md", "标题四个字 脸疼吗", "脸疼吗", 4),
    ]
    count_findings = []
    for file, span, quotation, claimed in assertions:
        text = (ROOT / file).read_text(encoding="utf-8")
        count_findings.append({"file": file, "evidence": span, "quotation": quotation,
                               "claimed": claimed, "actual_han": len(re.findall(r"[\u4e00-\u9fff]", quotation)),
                               "span_exists": span in text,
                               "line": text[:text.index(span)].count("\n") + 1 if span in text else None})
    return {"measurements": measurements, "variant_ai_checks": variant_ai,
            "clip_timing_assumption": "all text voiced sequentially, no pauses, 6.4 chars/s; not measured audio",
            "clip_78_offsets": clip_offsets, "literal_count_findings": count_findings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=AUDIT)
    args = parser.parse_args()
    before = tracked_hashes()
    RESULTS["metadata"] = {
        "audit_date": "2026-09-19", "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT), "python": sys.version.split()[0],
        "head": run("git head", ["git", "rev-parse", "HEAD"])["stdout"].strip(),
        "branch": run("git branch", ["git", "branch", "--show-current"])["stdout"].strip(),
        "mode": "solo/direct independent audit; no historical multi-agent execution inferred",
        "scope": "mechanical top-level work checks + isolated probes; not a platform analytics verification"}
    RESULTS["controls"] = {
        "existing_tests": run("existing tests", [sys.executable, "scripts/test_gates.py", "--works"]),
        "corpus_contract_fuben": run("fuben corpus contract", [sys.executable, "scripts/audit_analyze_lib.py"]),
        "long_scope_short_contract_comparison": run("long corpus compared with short contract (not long validator)", [
            sys.executable, "scripts/audit_analyze_lib.py", "--scope=long"]),
        "reverse_corpus": run("reverse corpus (read-only)", [sys.executable, "scripts/fuben_health.py", "--corpus"])}
    works = []
    for directory in sorted((ROOT / "作品").iterdir()):
        if not directory.is_dir() or not (directory / "正文.md").is_file():
            continue
        result = run("work " + directory.name, [sys.executable, "scripts/fuben_run.py", str(directory)])
        works.append({"directory": directory.name, **result})
    RESULTS["all_primary_works"] = {"count": len(works),
                                    "pass": sum(row["returncode"] == 0 for row in works),
                                    "fail": sum(row["returncode"] != 0 for row in works), "rows": works}
    latest = ROOT / "作品/78_Codex上瘾的人"
    RESULTS["isolated_probes"] = defect_probes(latest)
    RESULTS["generic_phase2_on_fuben78"] = run("generic short Phase 2 vs latest fuben", [
        "node", "skills/story-short-write/scripts/check-phase2-contract.js", "--json", str(latest)])
    RESULTS["csv_v2"] = csv_audit()
    RESULTS["latest"] = latest_measurements()
    RESULTS["deployment_presence"] = {name: (ROOT / name).exists() for name in (
        ".claude", ".codex", ".opencode", ".agents", ".story-deployed", ".github/workflows")}
    snapshot = datetime.fromisoformat("2026-09-19T15:22")
    reported = []
    for wid, published, plays, likes, watch, duration in (
        ("76", "2026-09-19T14:09", 798, 12, 18, 446),
        ("72", "2026-09-18T19:41", 1033, 28, 30, 497),
        ("legacy-01", "2026-09-17T19:40", 2094, 15, 17, 375),
    ):
        reported.append({"id": wid, "play_pv": plays, "likes": likes, "avg_watch_sec": watch,
                         "duration_sec": duration, "like_rate_pct": round(likes / plays * 100, 4),
                         "mean_watched_fraction_pct_NOT_completion": round(watch / duration * 100, 4),
                         "age_minutes_assuming_same_timezone": int((snapshot - datetime.fromisoformat(published)).total_seconds() / 60)})
    RESULTS["reported_backend_values_recalculated_NOT_verified"] = {
        "source": "_发布战报_D0_2026-09-19.md table, NOT ragged CSV field positions",
        "raw_platform_screenshots_or_video_ids_verified": False, "rows": reported}
    after = tracked_hashes()
    changed = [name for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)]
    RESULTS["production_tracked_files_changed"] = changed
    relevant = {name: sha for name, sha in before.items() if name.startswith("scripts/") or
                name.endswith("/SKILL.md") or name in ("AGENTS.md", "README.md", "作品/_数据.csv", "作品/_数据_v2.csv") or
                re.match(r"作品/(75_|76_|77_|78_)", name)}
    RESULTS["input_sha256"] = relevant
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "audit_results.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "audit_log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    print(json.dumps({"work_count": len(works), "passes": RESULTS["all_primary_works"]["pass"],
                      "csv_bad_width": RESULTS["csv_v2"]["wrong_width_count"],
                      "csv_width_or_type_defects": RESULTS["csv_v2"]["rows_with_detected_schema_or_type_defects"],
                      "production_files_changed": changed, "outputs": str(args.out_dir)}, ensure_ascii=False, indent=2))
    return 1 if changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
