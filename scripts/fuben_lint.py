#!/usr/bin/env python3
"""Fuben readability candidates, not a separate creative quota gate.

All CLI entries share the engine and severity policy. --human is accepted for
old callers but never counts as evidence of actual human review.
"""
from fuben_engine import cli

if __name__ == '__main__':
    raise SystemExit(cli(label='LINT', components={'facts', 'style', 'account'}))
