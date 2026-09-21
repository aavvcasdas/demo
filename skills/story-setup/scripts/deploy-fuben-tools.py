#!/usr/bin/env python3
"""Explicitly deploy fuben tools beside a project (no hosts/agents assumed).

python3 skills/story-setup/scripts/deploy-fuben-tools.py --dest /path/to/project
Copies only managed tool files; refuses to overwrite user modifications or write
through destination symlinks. Writing Skill prose alone does not install its tools.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

SOURCE = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deploy(source, dest):
    source, dest = source.resolve(), dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    marker = dest / '.story/fuben-tools.json'
    previous = json.loads(marker.read_text(encoding='utf-8')) if marker.is_file() else {'files': {}}
    files = {str(p.relative_to(source)): p for p in (source / 'scripts').glob('fuben_*.py')}
    files['scripts/fuben_policy.json'] = source / 'scripts/fuben_policy.json'
    for name in ('check-ai-patterns.js', 'style-whitelist.js', 'story-profile.js'):
        files['scripts/_fuben_vendor/' + name] = source / 'skills/story-review/scripts' / name
    if len(files) < 10:
        raise ValueError('incomplete source toolkit')
    for name, origin in files.items():
        if not origin.is_file():
            raise ValueError('missing source: ' + str(origin))
        target = dest / name
        if not target.resolve().is_relative_to(dest) or any(p.is_symlink() for p in [target, *target.parents] if p != dest.parent):
            raise ValueError('refusing symlink destination: ' + str(target))
        if target.exists() and sha(target) not in (sha(origin), previous.get('files', {}).get(name)):
            raise ValueError('unmanaged or locally edited file; not overwriting: ' + str(target))
    if not marker.resolve().is_relative_to(dest) or marker.parent.is_symlink():
        raise ValueError('unsafe deployment manifest path')
    for name, origin in files.items():
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.resolve() != origin:
            shutil.copy2(origin, target)
    marker.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'schema_version': 1, 'files': {name: sha(origin) for name, origin in files.items()},
                'scope': 'fuben tools only; does not deploy host hooks, custom agents, media tools or publish'}
    marker.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = deploy(args.source, args.dest)
        print(json.dumps({'status': 'DEPLOYED', 'files': len(result['files']), 'scope': result['scope']}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
