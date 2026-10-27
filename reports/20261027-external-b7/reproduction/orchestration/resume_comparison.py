#!/usr/bin/env python3
"""Continue an immutable comparison without replacing its historical attempts.

Native searches and scoring use the original, checksum-verified adapter release.
This file only selects missing outputs, records writer/resource epochs, and
audits the deterministic union of original and continuation results.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def safe_relative(relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Output escapes its registered result root')
    return path


def choose_root(item, original, continuation):
    """Choose by existence before reading scores; never select a best retry."""
    relative = safe_relative(item['relative_output'])
    old = Path(original) / relative / 'result.json'
    new = Path(continuation) / relative / 'result.json'
    if old.exists():
        if new.exists():
            raise ValueError('Duplicate terminal attempts require review: ' + str(relative))
        return Path(original)
    return Path(continuation)


def missing_items(items, original):
    return [item for item in items if not
            (Path(original) / safe_relative(item['relative_output']) / 'result.json').exists()]


def census_missing_items(items, config):
    """Use the locked shutdown census for dispatch, then audit the whole union."""
    if sha(config['failure_census']) != config['failure_census_sha256']:
        raise ValueError('Original shutdown census changed')
    census = json.loads(Path(config['failure_census']).read_text())
    rows = census['unfinished_or_unreadable_rows']
    if (census['known_terminal_plus_additional_json'] + len(rows) != len(items)
            or len(rows) != census['remaining_without_confirmed_terminal_json']):
        raise ValueError('Original shutdown census count mismatch')
    lookup = {item['relative_output']: item for item in items}
    selected = []
    seen = set()
    for row in rows:
        relative = Path(row['path']).relative_to(config['original_results']).parent.as_posix()
        item = lookup[relative]
        if relative in seen or item['request']['method'] != row['method']:
            raise ValueError('Original shutdown census identity mismatch')
        seen.add(relative)
        selected.append(item)
    return missing_items(selected, config['original_results'])


def selected_index(missing, original_index):
    wanted = {item['relative_output'] for item in missing}
    entries = [entry for entry in original_index['fits'] if entry['relative_output'] in wanted]
    if len(entries) != len(wanted):
        raise ValueError('Missing-fit selection is not a one-to-one original index subset')
    return {'schema': original_index['schema'], 'fits': entries}


def verify_source(config):
    release = Path(config['native_release'])
    actual = {str(path.relative_to(release)): sha(path)
              for path in release.rglob('*.py') if '__pycache__' not in path.parts}
    if actual != config['native_source_hashes']:
        raise ValueError('Frozen native release differs from the preparation source lock')
    protocol = release/'manifests/formal/fair-comparison-v2.json'
    if sha(protocol) != config['protocol_sha256']:
        raise ValueError('Frozen scientific protocol changed')
    return {Path(name).name: digest for name, digest in actual.items()
            if Path(name).parent == Path('benchmark_mysr/external')}


def audit_epoch(items, config, root, original_only=False, aggregate=False):
    # Import only the immutable native release, not the older session worktree.
    from benchmark_mysr.external.fair_finalize import audit_one, aggregate_one
    from benchmark_mysr.external.fair import protocol
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    hashes = verify_source(config)
    native_root = config['original_results']
    new_root = str(Path(config['continuation_root'])/'results')
    job = os.environ['SLURM_JOB_ID']
    statuses, issues, groups, methods, epochs = Counter(), [], defaultdict(list), defaultdict(Counter), Counter()
    missing, usable = 0, 0
    thresholds = protocol()['failure_metrics']['nrmse_thresholds']

    def audit(item):
        selected = Path(native_root) if original_only else choose_root(item, native_root, new_root)
        expected_job = config['original_job'] if selected == Path(native_root) else job
        row = audit_one((item, selected, expected_job, hashes))
        row['writer_job'] = expected_job
        row['resource_epoch'] = (config['original_resource_epoch'] if selected == Path(native_root)
                                 else config['resource_epoch'])
        return row

    with ThreadPoolExecutor(max_workers=config['audit_workers']) as pool, (root/'records.jsonl').open('x') as stream:
        for row in pool.map(audit, items):
            stream.write(json.dumps(row, allow_nan=False)+'\n')
            statuses[row.get('status', 'missing')] += 1
            epochs[row['resource_epoch']] += 1
            missing += row.get('status') is None
            usable += bool(row['usable'] and not row['issues'])
            method = methods[row['method']]
            method['records'] += 1
            method['applicable'] += row.get('status') != 'not_applicable'
            method['usable'] += bool(row['usable'] and not row['issues'])
            for threshold in thresholds:
                method['nrmse_le_'+str(threshold)] += bool(
                    row['usable'] and not row['issues'] and row['test_nrmse'] <= threshold)
            if row['issues']:
                issues.append({'result': row['result'], 'issues': row['issues']})
            if aggregate and row['component'] is not None:
                groups[str(Path(row['relative_output']).parent)].append(row)
            if sum(statuses.values()) % 5000 == 0:
                dump(root/'progress.json', {'checked': sum(statuses.values()), 'total': len(items),
                     'statuses': dict(statuses), 'issue_count': len(issues), 'time': time.time()})
        stream.flush()
        os.fsync(stream.fileno())
        complete_systems = sum(pool.map(aggregate_one, (
            (relative, rows, Path(config['continuation_root'])/'ode-aggregates')
            for relative, rows in groups.items()))) if aggregate else None
    passed = not issues and not missing and len(items) == config['expected_fit_count']
    if aggregate:
        passed = passed and len(groups) == complete_systems == config['expected_ode_count']
    summary = {'native_records': len(items), 'statuses': dict(statuses), 'usable_predictions': usable,
               'missing_results': missing, 'issue_count': len(issues), 'issues': issues,
               'method_counts': dict(methods), 'resource_epochs': dict(epochs),
               'ode_aggregates': len(groups) if aggregate else None,
               'complete_ode_aggregates': complete_systems, 'external_audit_passed': bool(passed),
               'formal_comparison_ready': False, 'mysr_results_present': False,
               'scope': 'Deterministic multi-writer continuation of B7, preserved negative outcomes; SMT resource amendment must be matched by MySR.',
               'request_sha256': config['comparison_requests_sha256']}
    dump(root/'summary.json', summary)
    return summary


def verify_data(items, workers):
    expected = {}
    for item in items:
        request = item['request']
        for split, digest in request['expected_data_hashes'].items():
            path = str(Path(request['data'])/(split+'.csv'))
            if path in expected and expected[path] != digest:
                raise ValueError('Inconsistent immutable data identity')
            expected[path] = digest
    def check(pair):
        path, expected_hash = pair
        if sha(path) != expected_hash:
            raise ValueError('Immutable data bytes changed: ' + path)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(check, expected.items()))
    return len(expected)


def bootstrap(config, config_path):
    stage = Path(config['native_release'])/'benchmark_mysr/external/stage.py'
    name = 'env_1_mysr'
    staged = subprocess.check_output([
        '/usr/bin/python3', str(stage), '--bundles', config['supervisor_bundles'],
        '--cache', f'/tmp/mysr-external-{os.getuid()}', '--name', name], text=True).strip()
    python = str(Path(staged)/name/'bin/python')
    env = dict(os.environ, PYTHONPATH=config['native_release'], OPENBLAS_NUM_THREADS='1',
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', JULIA_NUM_THREADS='1',
               PYTHON_JULIACALL_THREADS='1', NUMEXPR_NUM_THREADS='1')
    os.execve(python, [python, str(Path(__file__).resolve()), '--config', str(config_path), '--staged'], env)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if not args.staged:
        bootstrap(config, args.config.resolve())
    root = Path(config['continuation_root'])
    # Keep the lock for the entire allocation. Never clear any original fit locks.
    with (root/'owner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (root/'dispatch-config.json').exists():
            raise ValueError('Continuation already dispatched; inspect its receipt before another attempt')
        verify_source(config)
        for name, expected in config['orchestration_hashes'].items():
            if sha(Path(__file__).parent/name) != expected:
                raise ValueError('Continuation orchestration changed: ' + name)
        if sha(config['requests']) != config['comparison_requests_sha256']:
            raise ValueError('Original request manifest changed')
        if sha(config['original_index']) != config['original_index_sha256']:
            raise ValueError('Original dispatch index changed')
        items = [json.loads(line) for line in Path(config['requests']).read_text().splitlines()]
        if len(items) != config['expected_fit_count'] or len({item['relative_output'] for item in items}) != len(items):
            raise ValueError('Original request count or uniqueness changed')
        cpus = sorted(os.sched_getaffinity(0))
        if len(cpus) != config['workers_per_node']:
            raise ValueError('Slurm affinity differs from the registered500 logical CPUs')
        dump(root/'allocation.json', {'job_id': os.environ['SLURM_JOB_ID'], 'cpus': cpus,
             'config_sha256': sha(args.config), 'started': time.time(),
             'resource_epoch': config['resource_epoch'], 'no_task_limits_added': True})
        print('Checking original terminal-file presence; scores do not affect retry selection', flush=True)
        missing = census_missing_items(items, config)
        print('Verifying immutable input bytes for missing fits', flush=True)
        dump(root/'preflight-data-verification.json', {
            'verified_files': verify_data(missing, config['audit_workers']),
            'scope': 'Missing-fit inputs; full saved-result and input audit follows dispatch'})
        original_index = json.loads(Path(config['original_index']).read_text())
        index_path = root/'remaining-index.json'
        dump(index_path, selected_index(missing, original_index))
        dump(root/'decision-ledger.json', {
            'missing_count': len(missing), 'preserved_terminal_count': len(items)-len(missing),
            'missing_by_method': dict(Counter(item['request']['method'] for item in missing)),
            'full_original_integrity_audit': 'pending; mandatory after dispatch',
            'selection_policy': 'Only absent terminal files; preserve all existing outcomes regardless of test quality. Existing corrupt or runtime-fault records require explicit review, never automatic best retry.',
            'source_hashes': config['native_source_hashes'], 'original_job': config['original_job'],
            'continuation_job': os.environ['SLURM_JOB_ID'], 'created_at': time.time()})
        dispatch = dict(config)
        dispatch['comparison_index_sha256'] = sha(index_path)
        dispatch['finalize_comparison'] = False
        for entry in dispatch['campaigns']:
            entry['manifest'] = str(index_path)
            entry['output'] = str(root/'results')
        dump(root/'dispatch-config.json', dispatch)
        command = [sys.executable, str(Path(__file__).parent/'resilient_node_pool.py'),
                   '--config', str(root/'dispatch-config.json'), '--node', 'carbon',
                   '--workers', str(config['workers_per_node'])]
        print('Dispatching only missing fits: '+str(len(missing)), flush=True)
        result = subprocess.run(command, check=False)
        dump(root/'dispatch-exit.json', {'returncode': result.returncode, 'finished_at': time.time()})
        print('Auditing complete deterministic union and independent ODE systems', flush=True)
        dump(root/'data-verification.json', {'verified_files': verify_data(items, config['audit_workers'])})
        final = audit_epoch(items, config, root/'final-audit', aggregate=True)
        verify_source(config)
        if final['external_audit_passed'] and result.returncode == 0:
            dump(root/'RUN_COMPLETE.json', {'job_id': os.environ['SLURM_JOB_ID'],
                 'audit_summary_sha256': sha(root/'final-audit/summary.json'),
                 'fit_count': len(items), 'ode_count': final['ode_aggregates'],
                 'completed_at': time.time(), 'formal_comparison_ready': False})
            return 0
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
