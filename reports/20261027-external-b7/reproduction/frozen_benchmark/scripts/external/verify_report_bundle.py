#!/usr/bin/env python3
"""Verify the complete published report package and its declared evidence."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):h.update(block)
    return h.hexdigest()


def files(root):
    return sorted(p for p in root.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'
                  and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts)


def verify(root):
    expected = {}
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        digest, relative = line.split('  ', 1)
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or relative in expected:
            raise ValueError('Unsafe or duplicate checksum entry')
        expected[relative] = digest
    actual = {str(p.relative_to(root)): sha(p) for p in files(root)}
    if actual != expected:raise ValueError('Package file set or checksum mismatch')
    frozen = json.loads((root / 'metadata/frozen-source-sha256.json').read_text())
    for relative, digest in frozen.items():
        if sha(root / 'reproduction/frozen_benchmark' / relative) != digest:
            raise ValueError('Frozen original source changed: ' + relative)
    collection = json.loads((root / 'evidence/collection-summary.json').read_text())
    if collection['issue_count'] or collection['counts']['records'] != 221400:
        raise ValueError('Incomplete or invalid result collection')
    for relative, value in collection['outputs'].items():
        if sha(root / 'evidence' / relative) != value['sha256']:
            raise ValueError('Portable result evidence changed')
    combined = json.loads((root / 'metadata/combined-summary.json').read_text())
    tables = json.loads((root / 'tables/summary.json').read_text())
    if tables['records'] != 221400 or tables['statuses'] != combined['statuses']:
        raise ValueError('Report outcome census differs from completed native audit')
    if tables['complete_ode_system_records'] != 37800:
        raise ValueError('Missing full ODE system matrix')
    if tables['common_all_six_applicable_scalar_cases'] != 28020:
        raise ValueError('Incorrect common applicability denominator')
    if tables['mysr_results_present'] or tables['formal_comparison_ready']:
        raise ValueError('Unexpected MySR or formal readiness claim')
    return {'verified_files': len(actual), 'frozen_original_source_files': len(frozen),
            'selected_terminal_records': 221400, 'complete_ode_system_records': 37800,
            'raw_result_identity_issues': collection['issue_count'],
            'formal_comparison_ready': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--write-checksums', action='store_true')
    args = p.parse_args(); root = args.root.resolve()
    if args.write_checksums:
        (root / 'SHA256SUMS').write_text(''.join(sha(path) + '  ' + str(path.relative_to(root)) + '\n'
                                             for path in files(root)))
    print(json.dumps(verify(root)))
