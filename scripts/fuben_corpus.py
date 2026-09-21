#!/usr/bin/env python3
"""Read-only corpus calibration. Baseline code is materialized from a pinned Git commit.

python3 scripts/fuben_corpus.py --baseline-only --out 审计/2026-09-19_规则修复/baseline.json
python3 scripts/fuben_corpus.py --out 审计/2026-09-19_规则修复/corpus_comparison.json

44 independent sources + 00 anthology (reported separately, not 45 independent videos).
Never invent setting files for external prose; missing production contracts are N/A.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "c064a61fe81edf8b8bb5a784f44e162815249f2d"


def discover(root=ROOT):
    files = []
    for directory in sorted((root / "拆文库").iterdir()):
        if not directory.is_dir() or not re.match(r"^\d", directory.name):
            continue
        originals = sorted(p for p in (directory / "原文").glob("*") if p.is_file() and p.suffix.lower() in (".txt", ".md"))
        if len(originals) != 1:
            raise ValueError(f"{directory}: expected one identified original, found {len(originals)}; refusing silent skip/double counting")
        files.extend(originals)
    return files


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, cwd):
    r = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=90)
    return {"exit_code": r.returncode, "stdout": r.stdout, "stderr": r.stderr}


def materialize(ref, target):
    # No checkout / branch manipulation; only the needed old source files in a temp dir.
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", ref, "scripts"], cwd=ROOT, text=True).splitlines()
    paths += ["skills/story-review/scripts/check-ai-patterns.js", "skills/story-review/scripts/style-whitelist.js"]
    for name in paths:
        if not name.endswith((".py", ".js")):
            continue
        data = subprocess.check_output(["git", "show", f"{ref}:{name}"], cwd=ROOT)
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def annotate_metadata(path):
    """Existing analysis annotations, not audience measurements or inferred new labels."""
    meta = path.parents[1] / "_meta.json"
    if not meta.exists():
        return {"available": False}
    data = json.loads(meta.read_text(encoding="utf-8"))
    peak = data.get("peak", {})
    rows = {"available": bool(peak), "source": str(meta.relative_to(ROOT)), "peak": peak}
    if isinstance(peak, dict):
        position = peak.get("max_pos")
        if isinstance(position, (float, int)) and 0 <= position <= 1:
            rows["old_generic_peak_25_48_compatible"] = .25 <= position <= .48
            rows["old_decline_peak_15_55_compatible"] = .15 <= position <= .55
        bottom = peak.get("min")
        if isinstance(bottom, (float, int)):
            rows["old_valley_le_minus6_compatible"] = bottom <= -6
    return rows


def baseline(ref, files):
    rows = []
    with tempfile.TemporaryDirectory(prefix="fuben_corpus_baseline_") as temp:
        old = Path(temp)
        materialize(ref, old)
        probe = old / "probe.py"
        probe.write_text('''import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'scripts'))
from fuben_health import text_checks
out=[]
for name in json.load(sys.stdin):
 try:
  checks=text_checks(Path(name).read_text(encoding='utf-8'))
  out.append({'path':name,'checks':checks})
 except Exception as e:
  out.append({'path':name,'error':repr(e)})
print(json.dumps(out,ensure_ascii=False))
''', encoding="utf-8")
        r = subprocess.run([sys.executable, str(probe)], input=json.dumps([str(p) for p in files]),
                           capture_output=True, text=True, cwd=old, timeout=90, check=True)
        checks = {row["path"]: row for row in json.loads(r.stdout)}
        for path in files:
            item = {"source": str(path.relative_to(ROOT)), "source_sha256": digest(path),
                    "kind": "anthology" if path.parents[1].name.startswith("00_") else "individual",
                    "annotation": annotate_metadata(path), "legacy_text": checks[str(path)]}
            # Only body-readable stage; empty setting is explicitly unassessed, never a fabricated lock.
            work = old / "probe_work"
            work.mkdir(exist_ok=True)
            (work / "正文.md").write_bytes(path.read_bytes())
            (work / "设定.md").write_text("", encoding="utf-8")
            item["legacy_lint"] = execute([sys.executable, "scripts/fuben_lint.py", str(work)], old)
            item["legacy_ai"] = execute(["node", "skills/story-review/scripts/check-ai-patterns.js",
                                         "--json", "--fail-on=blocking", str(work / "正文.md")], old)
            if item["legacy_ai"]["exit_code"] not in (0, 1):
                raise RuntimeError("baseline AI checker failed: " + item["legacy_ai"]["stderr"])
            json.loads(item["legacy_ai"]["stdout"])
            item["not_applicable"] = ["production design fields", "declared fact-lock comparisons",
                                      "hype table/causal ledger minimum rows", "TTS QA", "publication analytics"]
            rows.append(item)
    return rows


def summarize(rows):
    individuals = [row for row in rows if row["kind"] == "individual"]
    rule_counts = Counter()
    rejected_text, rejected_lint, rejected_ai, rejected_any = 0, 0, 0, 0
    for row in individuals:
        failures = [name for name, (ok, _) in row["legacy_text"]["checks"].items() if not ok and name != "无不必要品牌"]
        rule_counts.update(failures)
        lint = row["legacy_lint"]["exit_code"] != 0
        ai = row["legacy_ai"]["exit_code"] != 0
        rejected_text += bool(failures)
        rejected_lint += lint
        rejected_ai += ai
        rejected_any += bool(failures or lint or ai)
    return {"individuals": len(individuals), "anthologies": len(rows) - len(individuals),
            "legacy_text_proxy_violations": rejected_text, "legacy_lint_rejections": rejected_lint,
            "legacy_ai_style_rejections": rejected_ai, "legacy_any_style_or_proxy_flag": rejected_any,
            "legacy_text_rule_counts": dict(rule_counts),
            "note": "Text proxy tally includes already-advisory old checks; not equal to full pipeline failure or a quality score."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default=BASELINE)
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    files = discover()
    if not files:
        raise SystemExit("No reference sources; refusing an empty green run")
    before = {str(p.relative_to(ROOT)): digest(p) for p in files}
    rows = baseline(args.baseline_ref, files)
    result = {"schema_version": 1, "baseline_ref": args.baseline_ref,
              "scope": "all numeric fuben source directories; anthology separate; no raw text edited",
              "source_manifest": before, "summary": summarize(rows), "rows": rows}
    if not args.baseline_only:
        from fuben_engine import inspect_path
        for row, path in zip(rows, files):
            row["current"] = inspect_path(path, profile="reference")
            # Cross-check the same prose under draft fact severity too; reference
            # transcription uncertainty must not conceal a changed hard gate.
            row["current_draft_text_facts"] = inspect_path(path, profile="draft", run_style=False, components={"facts"})
        result["summary"]["current_individuals_with_block"] = sum(
            any(f["severity"] == "BLOCK" for f in row["current"]["findings"])
            for row in rows if row["kind"] == "individual")
        result["summary"]["current_draft_text_fact_blocks"] = sum(
            any(f["severity"] == "BLOCK" for f in row["current_draft_text_facts"]["findings"])
            for row in rows if row["kind"] == "individual")
        result["summary"]["current_tool_errors"] = sum(row["current"]["status"] == "ERROR" for row in rows)
        result["summary"]["current_creative_style_blocks"] = sum(
            f["severity"] == "BLOCK" and f["category"] == "style"
            for row in rows for f in row["current"]["findings"])
    after = {str(p.relative_to(ROOT)): digest(p) for p in discover()}
    if before != after:
        raise RuntimeError("Reference corpus changed during calibration")
    result["raw_sources_unchanged"] = True
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 2 if result["summary"].get("current_tool_errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
