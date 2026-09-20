#!/usr/bin/env python3
"""Versioned, evidence-labelled observations. Legacy CSV is immutable/quarantined.

  template                           print the new JSON record shape
  record --input snapshot.json       validate, bind text hash, append atomically
  report                             observed vs derived metrics, no causal ranking
  migrate --write                    byte-exact backups + quarantine, no guessed repair

JSON rates use fractions (0..1), times seconds, timestamps explicit timezone.
Average watch / duration is a mean watched fraction, NEVER completion rate.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '作品/数据'
OBSERVED_FIELDS = {'plays', 'likes', 'comments', 'shares', 'saves', 'followers_gained',
                   'average_watch_seconds', 'completion_rate', 'retention_5s_rate'}
COUNT_FIELDS = {'plays', 'likes', 'comments', 'shares', 'saves', 'followers_gained'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be an ISO string with timezone')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.utcoffset() is None:
        raise ValueError('timestamp needs timezone offset, e.g. +08:00')
    return stamp


def finite(value, field, *, fraction=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(field + ' must be a finite nonnegative number or null')
    if fraction and value > 1:
        raise ValueError(field + ' must be a fraction in [0,1], not a percentage')


def validate(record, *, bind=False, root=ROOT):
    if not isinstance(record, dict) or record.get('schema_version') != 3:
        raise ValueError('schema_version must be 3')
    allowed = {'schema_version', 'work_id', 'text_version', 'text_path', 'text_sha256', 'video_id',
               'video_version', 'published_at', 'snapshot_at', 'window', 'traffic_scope', 'duration_seconds',
               'observed', 'source', 'notes'}
    if set(record) - allowed:
        raise ValueError('unknown fields: ' + ', '.join(sorted(set(record) - allowed)))
    for key in ('work_id', 'text_version', 'text_path', 'video_id', 'video_version', 'traffic_scope'):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError(key + ' is required; missing identity must stay quarantined')
    if not re.fullmatch(r'\d+[a-z]?', record['work_id']):
        raise ValueError('work_id must be a numeric work identifier with optional suffix')
    if record['traffic_scope'] not in ('organic', 'paid', 'mixed', 'unknown'):
        raise ValueError('invalid traffic_scope')
    if record.get('window') != 'cumulative_since_publication':
        raise ValueError('only explicitly cumulative snapshots are currently supported')
    published, snapshot = timestamp(record.get('published_at')), timestamp(record.get('snapshot_at'))
    if snapshot < published:
        raise ValueError('snapshot precedes publication')
    if not re.fullmatch(r'[a-f0-9]{64}', record.get('text_sha256', '')):
        raise ValueError('text_sha256 is required')
    duration = record.get('duration_seconds')
    if duration is not None:
        finite(duration, 'duration_seconds')
        if duration == 0:
            raise ValueError('duration must be positive or null')
    obs = record.get('observed')
    if not isinstance(obs, dict) or set(obs) != OBSERVED_FIELDS:
        raise ValueError('observed keys must match schema; missing values are null, not zero')
    if all(value is None for value in obs.values()):
        raise ValueError('no actual observations supplied')
    for key, value in obs.items():
        if value is None:
            continue
        finite(value, key, fraction=key.endswith('_rate'))
        if key in COUNT_FIELDS and type(value) is not int:
            raise ValueError(key + ' must be an integer count')
    source = record.get('source')
    if not isinstance(source, dict) or source.get('kind') not in ('owner_report', 'screenshot', 'platform_export'):
        raise ValueError('source kind must identify provenance')
    if not all(isinstance(source.get(key), str) and source[key].strip() for key in ('location', 'reported_by')):
        raise ValueError('source.location and source.reported_by are required')
    if bind:
        target = (root / record['text_path']).resolve()
        if not target.is_relative_to((root / '作品').resolve()):
            raise ValueError('text_path must be inside 作品')
        relative = target.relative_to((root / '作品').resolve())
        if len(relative.parts) < 2 or relative.parts[0].split('_')[0] != record['work_id']:
            raise ValueError('work_id and text_path disagree')
        if digest(target) != record['text_sha256']:
            raise ValueError('text hash does not match the identified version')
        if source['kind'] in ('screenshot', 'platform_export'):
            evidence = (root / source['location']).resolve()
            if not evidence.is_relative_to(root.resolve()):
                raise ValueError('evidence path must be workspace-local')
            if digest(evidence) != source.get('sha256'):
                raise ValueError('source evidence hash missing or stale')
    return record


def derived(record):
    obs = record['observed']
    plays, likes = obs['plays'], obs['likes']
    duration, watched = record.get('duration_seconds'), obs['average_watch_seconds']
    return {'like_rate': likes / plays if plays and likes is not None else None,
            'mean_watched_fraction': watched / duration if duration and watched is not None else None,
            'age_seconds': (timestamp(record['snapshot_at']) - timestamp(record['published_at'])).total_seconds(),
            'warning': '均播/时长不是完播率；可因重播超过1。来源申报不是独立验真；不同观察龄/流量来源不可直接归因。'}


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
            name = out.name
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def read_records(path):
    if not path.exists():
        return []
    records = []
    for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            raise ValueError(f'empty data row {n}; refusing silent skip')
        try:
            records.append(validate(json.loads(line)))
        except (ValueError, TypeError) as exc:
            raise ValueError(f'{path.name}:{n}: {exc}') from exc
    return records


def append_record(record, data_dir=DATA, root=ROOT):
    # No third-party dependencies; flock is available on this POSIX workspace.
    import fcntl
    validate(record, bind=True, root=root)
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / 'snapshots.jsonl'
    with (data_dir / '.snapshots.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        rows = read_records(target)
        key_fields = ('work_id', 'text_version', 'video_id', 'video_version', 'snapshot_at', 'traffic_scope', 'window')
        key = tuple(record[k] for k in key_fields)
        for old in rows:
            if tuple(old[k] for k in key_fields) == key:
                if old == record:
                    return 'ALREADY_RECORDED'
                raise ValueError('conflicting observation for same video/version/snapshot; retain evidence, do not overwrite')
        rows.append(record)
        atomic_write(target, ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows).encode('utf-8'))
    return 'RECORDED_UNVERIFIED_SOURCE'


def migrate(paths, data_dir=DATA, *, write=False):
    rows, manifests = [], []
    for path in paths:
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        parsed = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline='')))
        if not parsed:
            raise ValueError('empty legacy CSV: ' + str(path))
        header = parsed[0]
        backup = data_dir / 'legacy_raw' / (path.stem + '_' + sha[:12] + '.csv')
        for index, values in enumerate(parsed[1:], 2):
            reasons = ['legacy provenance/version/timezone not independently verified; no guessed column shifting']
            if len(values) != len(header):
                reasons.append(f'column_count:{len(values)} expected:{len(header)}')
            candidates = dict(zip(header, values)) if len(values) == len(header) else None
            if candidates and 'likes' in candidates:
                for field in ('likes', 'play_pv', 'comments', 'shares', 'saves', '字数'):
                    value = candidates.get(field, '')
                    if value and not re.fullmatch(r'\d+', value):
                        reasons.append(f'non_integer_candidate:{field}={value}')
                if candidates.get('发布状态') not in ('published', 'draft', 'planned', ''):
                    reasons.append('unrecognized_publication_state')
            rows.append({'schema_version': 1, 'state': 'QUARANTINED', 'source_file': path.name,
                         'source_sha256': sha, 'csv_record_number': index, 'header': header, 'raw_cells': values,
                         'parsed_candidates_not_observations': candidates, 'reasons': reasons})
        manifests.append({'file': path.name, 'sha256': sha, 'records': len(parsed) - 1,
                          'columns': len(header), 'backup': str(backup.relative_to(data_dir))})
        if write:
            if backup.exists() and digest(backup) != sha:
                raise ValueError('backup collision or corruption')
            atomic_write(backup, raw)
    if write:
        atomic_write(data_dir / 'legacy_quarantine.jsonl', ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows).encode('utf-8'))
        atomic_write(data_dir / 'legacy_manifest.json', (json.dumps(manifests, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return {'sources': manifests, 'quarantined_records': len(rows),
            'wrong_width': sum(any(reason.startswith('column_count:') for reason in row['reasons']) for row in rows),
            'verified_observations_imported': 0, 'write': write}


def template():
    return {'schema_version': 3, 'work_id': '', 'text_version': '', 'text_path': '', 'text_sha256': '',
            'video_id': '', 'video_version': '', 'published_at': '', 'snapshot_at': '',
            'window': 'cumulative_since_publication', 'traffic_scope': 'unknown', 'duration_seconds': None,
            'observed': {key: None for key in sorted(OBSERVED_FIELDS)},
            'source': {'kind': 'owner_report', 'location': '', 'reported_by': ''}, 'notes': ''}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('template')
    record = sub.add_parser('record')
    record.add_argument('--input', type=Path, required=True)
    report = sub.add_parser('report')
    report.add_argument('--json', action='store_true')
    migration = sub.add_parser('migrate')
    migration.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'template':
            result = template()
        elif args.command == 'migrate':
            result = migrate([ROOT / '作品/_数据.csv', ROOT / '作品/_数据_v2.csv'], write=args.write)
        elif args.command == 'record':
            result = {'status': append_record(json.loads(args.input.read_text(encoding='utf-8')))}
        else:
            records = read_records(DATA / 'snapshots.jsonl')
            quarantine = DATA / 'legacy_quarantine.jsonl'
            result = {'observations': [{**row, 'derived_not_observed': derived(row)} for row in records],
                      'valid_schema_observations': len(records), 'independently_verified_by_this_tool': 0,
                      'quarantined_legacy_records': len(quarantine.read_text(encoding='utf-8').splitlines()) if quarantine.exists() else 0,
                      'conclusion': '不按少量异龄快照相关性改写创作硬规则；点赞可撤回/修正，不强制单调。'}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print('ERROR: ' + str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
