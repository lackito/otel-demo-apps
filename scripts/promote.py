#!/usr/bin/env python3
"""Promote one verified image; replay the edit on latest main after push races."""
import argparse
import re
import subprocess
import time
from pathlib import Path
from ruamel.yaml import YAML


def update(path, component, repository, tag, target="aws"):
    if component not in {'recommendation', 'product-catalog', 'ad'}:
        raise ValueError('unsupported component')
    if not re.fullmatch(r'[0-9a-f]{40}', tag):
        raise ValueError('tag must be a full Git SHA')
    patterns = {
        'aws': r'\d{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/' + re.escape(component),
        'local': r'ghcr\.io/[a-z0-9][a-z0-9-]*/otel-demo-local-' + re.escape(component),
    }
    if target not in patterns or not re.fullmatch(patterns[target], repository):
        raise ValueError('repository must match the target registry and component')
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    data = yaml.load(path.read_text())
    service = data.setdefault('components', {}).setdefault(component, {})
    override = service.setdefault('imageOverride', {})
    override.update(repository=repository, tag=tag)
    if target == 'local':
        override['pullPolicy'] = 'IfNotPresent'
    with path.open('w') as output:
        yaml.dump(data, output)


def git(cwd, *args, check=True):
    return subprocess.run(['git', '-C', str(cwd), *args], check=check, text=True, capture_output=True)


def promote(checkout, file, component, repository, tag, attempts=8, target="aws"):
    checkout = Path(checkout).resolve()
    path = (checkout / file).resolve()
    if not path.is_relative_to(checkout):
        raise ValueError('values path must be inside checkout')
    if git(checkout, 'status', '--porcelain').stdout.strip():
        raise ValueError('promotion requires a clean, dedicated checkout')
    for attempt in range(attempts):
        git(checkout, 'fetch', 'origin', 'main')
        git(checkout, 'reset', '--hard', 'origin/main')
        update(path, component, repository, tag, target)
        git(checkout, 'diff', '--check')
        if git(checkout, 'diff', '--quiet', '--', file, check=False).returncode == 0:
            return
        git(checkout, 'add', '--', file)
        git(checkout, '-c', 'user.name=github-actions[bot]', '-c',
            'user.email=41898282+github-actions[bot]@users.noreply.github.com',
            'commit', '-m', f'chore({component}): deploy {tag}')
        result = git(checkout, 'push', 'origin', 'HEAD:main', check=False)
        if result.returncode == 0:
            return
        # A rejected push cannot overwrite main. Fetch and replay only this edit.
        if attempt + 1 < attempts:
            time.sleep(min(attempt + 1, 5))
    raise RuntimeError('GitOps push failed after retries; inspect permissions/branch protection')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', required=True)
    parser.add_argument('--file', default='applications/otel-demo/values.yaml')
    parser.add_argument('--component', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--target', choices=['aws', 'local'], default='aws')
    args = parser.parse_args()
    promote(args.checkout, args.file, args.component, args.repository, args.tag, target=args.target)
