#!/usr/bin/env python3
"""Software regressions + dynamic corpus/work coverage (no allowlisted green works).

--works reports ALL current numeric work dirs + standalone body variants, including
content BLOCKs. Those are not software-test failures. --strict-works additionally
returns 1 for a current manuscript BLOCK (use only when all works must be ready).
--corpus requires no creative-style BLOCKs; it is not a claim of literary quality.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fuben_engine import sha256
from fuben_health import inspect_collection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--works', action='store_true')
    parser.add_argument('--corpus', action='store_true')
    parser.add_argument('--strict-works', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT / 'tests')))
    summary = {'software_tests': result.testsRun, 'software_pass': result.wasSuccessful(),
               'test_failures': len(result.failures), 'test_errors': len(result.errors), 'collections': {}}
    failure = not result.wasSuccessful()
    manifest = json.loads((ROOT / 'tests/protected_sources.json').read_text(encoding='utf-8'))['sha256']
    actual_paths = {str(p.relative_to(ROOT)) for p in (ROOT / '拆文库').glob('*/原文/*') if p.is_file()}
    recorded_paths = {p for p in manifest if p.startswith('拆文库/')}
    mismatches = [p for p, expected in manifest.items() if not (ROOT / p).is_file() or sha256(ROOT / p) != expected]
    if actual_paths != recorded_paths:
        mismatches += sorted(actual_paths ^ recorded_paths)
    summary['protected_input_changes'] = mismatches
    failure |= bool(mismatches)
    for scope, enabled in [('works', args.works or args.strict_works), ('corpus', args.corpus)]:
        if not enabled:
            continue
        report = inspect_collection(corpus=scope == 'corpus')
        style_blocks = [row['source'] for row in report['rows'] if any(
            f['severity'] == 'BLOCK' and f['category'] == 'style' for f in row['result']['findings'])]
        summary['collections'][scope] = {'coverage': report['coverage'], 'statuses': report['status_counts'],
                                        'tool_errors': report['errors'], 'creative_style_blocks': style_blocks,
                                        'content_blocked': [row['source'] for row in report['rows'] if row['result']['status'] == 'FAIL'],
                                        'unassessed': report['excluded_or_unassessed']}
        failure |= bool(report['errors'] or style_blocks)
        if scope == 'works' and args.strict_works:
            failure |= bool(report['blocks'])
    summary['software_and_coverage_pass'] = not failure
    summary['not_a_release_verdict'] = True
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('SOFTWARE-AND-COVERAGE:', 'FAIL' if failure else 'PASS')
    print('各稿的内容 BLOCK 和待核实项另列；本结果不是稿件通过或发布批准。')
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())
