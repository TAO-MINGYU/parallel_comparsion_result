#!/usr/bin/env python3
"""Export all selected B7 terminal records without fitting or modifying them.

The completed native audit remains the source of frontier/prediction validation.
This exporter independently checks every raw result against that audit and the
effective frozen request, adds both observed and clean-target scores, and saves
portable, lossless result metadata with original byte hashes.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path


METHODS = ('pysr', 'operon', 'dsr', 'ai_feynman_2', 'gplearn', 'tf4sr')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def finite_score(value):
    return isinstance(value, dict) and all(
        isinstance(value.get(k), (float, int)) and math.isfinite(value[k]) and value[k] >= 0
        for k in ('mse', 'nrmse'))


def portable(value, roots):
    if isinstance(value, dict):
        return {k: portable(v, roots) for k, v in value.items()}
    if isinstance(value, list):
        return [portable(v, roots) for v in value]
    if isinstance(value, str):
        for prefix, replacement in roots:
            value = value.replace(prefix, replacement)
    return value


def export_one(args):
    audit, request, request_sha, locations, roots = args
    path = Path(audit['result'])
    raw = path.read_bytes()
    result = json.loads(raw)
    issues = []
    for key in ('method', 'task_id', 'seed', 'variant', 'resource_track', 'budget',
                'comparison_protocol', 'comparison_protocol_sha256'):
        if result.get(key) != request.get(key):
            issues.append('request_identity_changed:' + key)
    if result.get('data_hashes') != request['expected_data_hashes']:
        issues.append('data_identity_changed')
    for key in ('status', 'selected_expression'):
        if result.get(key) != audit.get(key):
            issues.append('completed_audit_changed:' + key)
    if audit['issues']:
        issues.append('source_audit_has_issues')
    observed_usable = bool(result.get('selected_expression')) and all(
        finite_score(result.get(key)) for key in ('train_score', 'validation_score', 'test_score'))
    if observed_usable != audit['usable']:
        issues.append('observed_usability_changed')
    if observed_usable and not math.isclose(result['test_score']['nrmse'], audit['test_nrmse'],
                                           rel_tol=1e-13, abs_tol=0):
        issues.append('observed_test_metric_changed')
    original = request.get('original_not_applicable')
    if original is not None:
        for key in ('original_not_applicable', 'applicability_amendment'):
            if result.get(key) != request[key]:
                issues.append('amendment_identity_changed:' + key)
    location = next(({'root_id': name, 'relative_dir': str(path.parent.relative_to(base))}
                     for name, base in locations if path.is_relative_to(base)), None)
    if location is None:
        issues.append('unrecognized_retained_result_location')
    primary_target = ('observed_blackbox' if not request.get('ground_truth_available') else
                      'clean_independent_derivative' if request.get('component') is not None else
                      'clean_latent')
    primary = result.get('test_score') if primary_target == 'observed_blackbox' else result.get('test_clean_score')
    primary_usable = observed_usable and finite_score(primary)
    # Validate only identities/metadata here. Do not mislabel historical audit
    # frontier hashes as fresh reads of the multi-terabyte raw frontier store.
    row = {'relative_output': audit['relative_output'], 'family': audit['family'],
           'kind': 'ode' if request.get('component') is not None else 'tabular',
           'method': request['method'], 'task_id': request['task_id'],
           'variant': request['variant'], 'resource_track': request['resource_track'],
           'seed': request['seed'], 'component': request.get('component'),
           'dimension': request.get('ode_dimension'),
           'ground_truth_available': request.get('ground_truth_available', False),
           'status': result['status'], 'applicable': result['status'] != 'not_applicable',
           'observed_usable': observed_usable, 'primary_usable': primary_usable,
           'primary_target': primary_target,
           'primary_nrmse': primary['nrmse'] if primary_usable else None,
           'observed_nrmse': result['test_score']['nrmse'] if observed_usable else None,
           'resource_epoch': audit.get('resource_epoch'),
           'writer_job': audit.get('writer_job', result.get('slurm_job_id')),
           'raw_result_sha256': hashlib.sha256(raw).hexdigest(),
           'effective_request_line_sha256': request_sha,
           'artifact_location': location,
           'result': portable(result, roots), 'issues': issues}
    return row


def gzip_writer(stack, path):
    raw = stack.enter_context(Path(path).open('wb'))
    gz = stack.enter_context(gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6))
    return stack.enter_context(io.TextIOWrapper(gz, encoding='utf-8', newline='\n'))


def collect(original, continuation, extension, output, workers=16, runtime_cache=None):
    original, continuation, extension, output = map(Path, (original, continuation, extension, output))
    marker = json.loads((extension / 'RUN_COMPLETE.json').read_text())
    for rel, key in [('audit/summary.json', 'audit_summary_sha256'),
                     ('combined-audit/summary.json', 'combined_summary_sha256')]:
        if sha(extension / rel) != marker[key]:
            raise ValueError('Completed audit hash mismatch')
    combined = json.loads((extension / 'combined-audit/summary.json').read_text())
    output.mkdir(parents=True, exist_ok=False)
    locations = [('B7', original), ('continuation', continuation), ('extension', extension)]
    runtime_cache = runtime_cache or Path('/tmp') / ('mysr-external-' + str(os.getuid()))
    roots = sorted([(str(base), '${' + name.upper() + '_ROOT}') for name, base in locations] + [
        (str(runtime_cache), '${RUNTIME_CACHE}'),
        (str(original.parents[1]), '${WORKSPACE_ROOT}'),
    ], key=lambda x: len(x[0]), reverse=True)
    requests = {}
    input_hashes = {}
    for name, path in [('B7', original / 'requests.jsonl'), ('extension', extension / 'requests.jsonl')]:
        input_hashes[name + '_requests_sha256'] = sha(path)
        with path.open('rb') as stream:
            for raw in stream:
                item = json.loads(raw)
                relative = item['relative_output']
                if name == 'extension' and relative not in requests:
                    raise ValueError('Extension introduced an unregistered task')
                requests[relative] = (item['request'], hashlib.sha256(raw).hexdigest())
    if len(requests) != 221400:
        raise ValueError('Unexpected effective request count')
    input_hashes['combined_audit_records_sha256'] = sha(extension / 'combined-audit/records.jsonl')
    counts, method_counts, issues, source_hashes, seen = Counter(), {m: Counter() for m in METHODS}, [], {}, set()
    with ExitStack() as stack:
        outputs = {m: gzip_writer(stack, output / (m + '.results.jsonl.gz')) for m in METHODS}
        request_out = gzip_writer(stack, output / 'effective-requests.portable.jsonl.gz')
        pool = stack.enter_context(ThreadPoolExecutor(max_workers=workers))
        with (extension / 'combined-audit/records.jsonl').open() as stream:
            while True:
                batch = []
                for _ in range(2048):
                    raw = stream.readline()
                    if not raw:
                        break
                    audit = json.loads(raw)
                    relative = audit['relative_output']
                    if relative in seen:
                        raise ValueError('Duplicate fit identity')
                    seen.add(relative)
                    req, req_sha = requests[relative]
                    batch.append((audit, req, req_sha, locations, roots))
                    request_out.write(json.dumps(portable({'relative_output': relative, 'request': req}, roots),
                                                 separators=(',', ':'), allow_nan=False) + '\n')
                if not batch:
                    break
                for row in pool.map(export_one, batch):
                    outputs[row['method']].write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')
                    counts['records'] += 1
                    counts[row['status']] += 1
                    counts['observed_usable'] += row['observed_usable']
                    counts['primary_usable'] += row['primary_usable']
                    method_counts[row['method']]['records'] += 1
                    method_counts[row['method']]['observed_usable'] += row['observed_usable']
                    method_counts[row['method']]['primary_usable'] += row['primary_usable']
                    identity = (row['method'], row['writer_job'])
                    hashes = row['result']['adapter_hashes']
                    if identity in source_hashes and source_hashes[identity] != hashes:
                        raise ValueError('Mixed adapter sources within a writer/method')
                    source_hashes[identity] = hashes
                    if row['issues']:
                        issues.append({'relative_output': row['relative_output'], 'issues': row['issues']})
                progress = {'at': datetime.now(timezone.utc).isoformat(), 'counts': dict(counts),
                            'issue_count': len(issues), 'native_searches_started': 0}
                (output / 'progress.json').write_text(json.dumps(progress, indent=2) + '\n')
                print(json.dumps(progress), flush=True)
    if seen != set(requests):
        raise ValueError('Exported identities differ from effective request matrix')
    if counts['observed_usable'] != combined['usable_predictions']:
        raise ValueError('Overall observed prediction count differs from completed audit')
    for status, count in combined['statuses'].items():
        if counts[status] != count:
            raise ValueError('Outcome census differs from completed audit')
    summary = {'completed_at': datetime.now(timezone.utc).isoformat(), 'counts': dict(counts),
               'method_counts': {k: dict(v) for k, v in method_counts.items()},
               'issue_count': len(issues), 'issues': issues, 'input_hashes': input_hashes,
               'adapter_sources': [{'method': k[0], 'writer_job': k[1], 'hashes': v}
                                   for k, v in source_hashes.items()],
               'outputs': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size}
                           for p in sorted(output.glob('*.gz'))},
               'freshly_verified': 'All221400 raw result files, scientific identities, both target scores and original audit agreement',
               'frontier_prediction_evidence': 'Retained expected frontier hashes and prediction metadata from completed native audits; not a new full multi-terabyte frontier rehash',
               'native_searches_started': 0, 'raw_results_modified': False,
               'portable_requests_change_paths': True,
               'portable_request_hashes_are_not_original_request_hashes': True,
               'formal_comparison_ready': False}
    (output / 'collection-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    if issues:
        raise ValueError('Export failed integrity checks; inspect retained summary')
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--original', type=Path, required=True)
    p.add_argument('--continuation', type=Path, required=True)
    p.add_argument('--extension', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workers', type=int, default=16)
    p.add_argument('--runtime-cache', type=Path)
    args = p.parse_args()
    collect(args.original, args.continuation, args.extension, args.output, args.workers, args.runtime_cache)
