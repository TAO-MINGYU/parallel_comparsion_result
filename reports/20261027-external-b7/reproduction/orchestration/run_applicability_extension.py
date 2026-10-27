#!/usr/bin/env python3
"""Run an audited B7 scope extension once, without changing original results."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

from extend_applicability import AMENDMENT, sha, dump
from resilient_node_pool import physical_cpus, available_memory_gib


def verify_code(root, manifest):
    for relative, expected in manifest.items():
        if sha(root / relative) != expected:
            raise ValueError('Source checksum mismatch: ' + relative)


def audit_selected(config, code, requests, report):
    from benchmark_mysr.external.fair_finalize import audit_one
    report.mkdir(parents=True, exist_ok=True)
    root = Path(config['root'])
    hashes = {p.name: sha(p) for p in (code / 'benchmark_mysr/external').glob('*.py')}
    rows = {}
    with Path(requests).open() as stream, (report / 'records.jsonl').open('w') as out:
        items = [json.loads(line) for line in stream]
        args = ((item, root / 'results', os.environ['SLURM_JOB_ID'], hashes) for item in items)
        with ProcessPoolExecutor(max_workers=min(8, config['workers'])) as pool:
            for item, row in zip(items, pool.map(audit_one, args, chunksize=8)):
                req = item['request']
                path = root / 'results' / item['relative_output'] / 'result.json'
                if path.exists():
                    result = json.loads(path.read_text())
                    for key in ('applicability_amendment', 'original_not_applicable'):
                        if result.get(key) != req[key]:
                            row['issues'].append('amendment_identity_changed:' + key)
                    old = req['original_not_applicable']
                    if sha(old['result']) != old['sha256']:
                        row['issues'].append('original_na_result_changed')
                    if row.get('status') == 'not_applicable':
                        row['issues'].append('unexpected_native_inapplicability')
                    if not (result.get('startup_seconds') or
                            result.get('stage', {}).get('startup_seconds')):
                        row['issues'].append('native_search_not_entered')
                row.update(writer_job=os.environ['SLURM_JOB_ID'],
                           applicability_amendment=AMENDMENT,
                           resource_epoch=config['resource_epoch'])
                rows[row['relative_output']] = row
                out.write(json.dumps(row, allow_nan=False) + '\n')
    summary = {'records': len(rows), 'usable': sum(row['usable'] for row in rows.values()),
               'statuses': dict(Counter(row.get('status', 'missing') for row in rows.values())),
               'issue_count': sum(bool(row['issues']) for row in rows.values()),
               'issues': [{'relative_output': k, 'issues': v['issues']}
                          for k, v in rows.items() if v['issues']],
               'applicability_amendment': AMENDMENT, 'formal_comparison_ready': False}
    dump(report / 'summary.json', summary)
    return rows, summary


def pool_phase(config, code, name, index, workers):
    root = Path(config['root'])
    phase = root / name
    phase.mkdir(exist_ok=True)
    dispatch = {
        'pool_output': str(phase / 'pools'), 'local_pool_root': str(phase / 'journals'),
        'requests': str(root / 'requests.jsonl'),
        'comparison_requests_sha256': config['requests_sha256'],
        'comparison_index_sha256': sha(index),
        'supervisor_python': config['supervisor_python'], 'bundles': config['bundles'],
        'minimum_available_memory_gib': 64, 'minimum_available_storage_gib': 64,
        'physical_cores_only': True, 'resource_epoch': config['resource_epoch'],
        'starts_per_second': 4, 'resume_stale_locks': False,
        'finalize_comparison': False,
        'campaigns': [{'method': method, 'kind': 'comparison_fit', 'node': config['node'],
                       'code': str(code), 'manifest': str(index),
                       'environment': 'parallel_' + ('ai_feynman' if method == 'ai_feynman_2' else method),
                       'output': str(root / 'results')}
                      for method in ('ai_feynman_2', 'tf4sr')],
    }
    path = phase / 'dispatch-config.json'
    dump(path, dispatch)
    environment = dict(os.environ, PYTHONPATH=str(code))
    return subprocess.run([sys.executable, str(root / 'orchestration/resilient_node_pool.py'),
                           '--config', str(path), '--node', config['node'],
                           '--workers', str(workers)], cwd=code, env=environment).returncode


def combined_audit(config, replacements):
    """Apply the frozen NA-only selection; never choose by observed test score."""
    from benchmark_mysr.external.fair_finalize import aggregate_one
    root, baseline = Path(config['root']), Path(config['baseline'])
    records = baseline / 'final-audit/records.jsonl'
    if sha(records) != config['baseline_records_sha256']:
        raise ValueError('Preserved original audit changed')
    report = root / 'combined-audit'
    report.mkdir(exist_ok=False)
    counts, methods, groups, replaced = Counter(), defaultdict(Counter), defaultdict(list), set()
    with records.open() as stream, (report / 'records.jsonl').open('w') as out:
        for line in stream:
            row = json.loads(line)
            relative = row['relative_output']
            if relative in replacements:
                if row['status'] != 'not_applicable':
                    raise ValueError('Refusing to replace a previously applicable outcome')
                row = replacements[relative]
                replaced.add(relative)
            counts['records'] += 1
            counts[row.get('status', 'missing')] += 1
            counts['usable'] += row['usable']
            methods[row['method']]['records'] += 1
            methods[row['method']]['applicable'] += row.get('status') != 'not_applicable'
            methods[row['method']]['usable'] += row['usable']
            if row['component'] is not None:
                groups[str(Path(relative).parent)].append(row)
            out.write(json.dumps(row, allow_nan=False) + '\n')
    if replaced != set(replacements) or counts['records'] != 221400:
        raise ValueError('Incomplete deterministic overlay')
    with ProcessPoolExecutor(max_workers=8) as pool:
        complete = sum(pool.map(aggregate_one,
            ((k, rows, root / 'ode-aggregates') for k, rows in groups.items()), chunksize=16))
    if len(groups) != 37800 or complete != 37800:
        raise ValueError('Incomplete ODE aggregate matrix')
    summary = {'native_records': counts.pop('records'), 'usable_predictions': counts.pop('usable'),
               'statuses': dict(counts), 'method_counts': {k: dict(v) for k, v in methods.items()},
               'replaced_original_na_records': len(replaced), 'ode_aggregates': len(groups),
               'complete_ode_aggregates': complete, 'formal_comparison_ready': False,
               'mysr_results_present': False, 'applicability_amendment': AMENDMENT,
               'scope': 'Original audited B7 plus all prespecified native-eligible formerly NA outcomes, including negative results; no best-of-retry selection.'}
    dump(report / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    root = Path(config['root'])
    with (root / 'owner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0] != config['node']:
            raise ValueError('Requires the registered Slurm node/allocation')
        cpus = sorted(os.sched_getaffinity(0))
        physical = physical_cpus(cpus)
        if len(physical) < config['workers']:
            raise ValueError('Insufficient allocated physical cores')
        for name, expected in [('requests.jsonl', config['requests_sha256']),
                               ('fits-index.json', config['index_sha256']),
                               ('source-manifest.json', config['source_manifest_sha256'])]:
            if sha(root / name) != expected:
                raise ValueError('Frozen deployment changed: ' + name)
        manifest = json.loads((root / 'source-manifest.json').read_text())
        verify_code(root / 'code', manifest)
        cache = Path('/tmp') / ('mysr-applicability-' + str(os.getuid())) / os.environ['SLURM_JOB_ID']
        cache.mkdir(parents=True, exist_ok=False)
        code = cache / 'code'
        shutil.copytree(root / 'code', code)
        verify_code(code, manifest)
        sys.path.insert(0, str(code))
        os.environ['PYTHONPATH'] = str(code)
        expected_python = Path(config['supervisor_python'])
        if not expected_python.is_file():
            raise ValueError('Verified supervisor runtime cache is unavailable')
        allocation = {'job_id': os.environ['SLURM_JOB_ID'], 'node': config['node'],
                      'allowed_logical_cpus': cpus, 'physical_cpu_selection': physical[:config['workers']],
                      'workers': config['workers'], 'single_thread_per_fit': True,
                      'available_memory_gib_at_start': available_memory_gib(),
                      'host_loadavg_at_start': Path('/proc/loadavg').read_text().strip(),
                      'cgroup_membership': Path('/proc/self/cgroup').read_text(),
                      'local_code': str(code), 'source_manifest_sha256': config['source_manifest_sha256'],
                      'config_sha256': sha(args.config), 'resource_epoch': config['resource_epoch'],
                      'started_at': time.time()}
        for name in ('cpu.max', 'memory.max', 'cpuset.cpus.effective'):
            p = Path('/sys/fs/cgroup') / name
            allocation[name] = p.read_text().strip() if p.exists() else 'not exposed at unified mount root'
        dump(root / 'allocation.json', allocation)
        print(json.dumps({'event': 'allocation_verified', 'workers': config['workers'],
                          'job': os.environ['SLURM_JOB_ID']}), flush=True)
        result = pool_phase(config, code, 'preflight', root / 'preflight/fits-index.json', 3)
        preflight_requests = root / 'preflight/requests.jsonl'
        index = json.loads((root / 'preflight/fits-index.json').read_text())['fits']
        with (root / 'requests.jsonl').open('rb') as stream, preflight_requests.open('wb') as out:
            for entry in index:
                stream.seek(entry['offset']); out.write(stream.readline())
        _, summary = audit_selected(config, code, preflight_requests, root / 'preflight/audit')
        if result or summary['issue_count'] or summary['records'] != 3:
            dump(root / 'PREFLIGHT_FAILED.json', summary)
            return 1
        dump(root / 'PREFLIGHT_PASSED.json', summary)
        print(json.dumps({'event': 'native_preflight_passed', 'records': 3}), flush=True)
        result = pool_phase(config, code, 'production', root / 'fits-index.json', config['workers'])
        rows, summary = audit_selected(config, code, root / 'requests.jsonl', root / 'audit')
        if result or summary['issue_count'] or summary['records'] != 12100:
            dump(root / 'AUDIT_FAILED.json', summary)
            return 1
        combined = combined_audit(config, rows)
        dump(root / 'RUN_COMPLETE.json', {'job_id': os.environ['SLURM_JOB_ID'],
             'extension_records': len(rows), 'combined_records': combined['native_records'],
             'audit_summary_sha256': sha(root / 'audit/summary.json'),
             'combined_summary_sha256': sha(root / 'combined-audit/summary.json'),
             'completed_at': time.time(), 'formal_comparison_ready': False})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
