#!/usr/bin/env python3
"""Prepare a separate, train-only extension of the frozen B7 method scope.

This changes registration gates, never the solver, data, feature columns,
positive-input requirement, checkpoint weights, scoring or search budgets.
The original B7 tree and all of its terminal outcomes remain read-only.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil


AMENDMENT = 'native-scope-extension-20261027-v1'
REQUEST_SHA = '094891ac33f2824a67bd757ee338dff95caa1aa2c68e4ef3a796e6e0f36c4591'
PATCHES = {
    'worker.py': (
        '5e726ec8c8188015e38161c9f8cc7c813feb3319414510fbf7b4e595fa5b408e',
        [
            ("if request['method'] == 'tf4sr' and not request.get('task_id', '').startswith('srsd-'):",
             "if request.get('applicability_amendment') != AMENDMENT and request['method'] == 'tf4sr' and not request.get('task_id', '').startswith('srsd-'):"),
            ("if request['method'] == 'ai_feynman_2' and not request.get('ground_truth_available', False):",
             "if request.get('applicability_amendment') != AMENDMENT and request['method'] == 'ai_feynman_2' and not request.get('ground_truth_available', False):"),
        ],
    ),
    'solvers.py': (
        '4d2e0472e6d9461152d0c9efc4b017350d8356dcb570bc2371f78bdea9e5ad2f',
        [
            ("if not request.get('ground_truth_available', False):",
             "if request.get('applicability_amendment') != AMENDMENT and not request.get('ground_truth_available', False):"),
            ("if not request.get('task_id', '').startswith('srsd-'):",
             "if request.get('applicability_amendment') != AMENDMENT and not request.get('task_id', '').startswith('srsd-'):"),
        ],
    ),
    'runner.py': (
        '925b71528e8496252877c7b6933d59c5c7763212865311d6e70cdb279a95e782',
        [("('comparison_protocol', 'comparison_protocol_sha256', 'component')",
          "('comparison_protocol', 'comparison_protocol_sha256', 'component', 'applicability_amendment', 'original_not_applicable')")],
    ),
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def patch_sources(frozen, destination):
    """Create an independently named deployment from checksum-locked sources."""
    frozen, destination = Path(frozen), Path(destination)
    for name, (expected, replacements) in PATCHES.items():
        source = frozen / 'benchmark_mysr/external' / name
        if sha(source) != expected:
            raise ValueError('Unexpected frozen source: ' + str(source))
        for before, after in replacements:
            if source.read_text().count(before) != 1:
                raise ValueError('Patch anchor is not unique: ' + name)
    shutil.copytree(frozen, destination,
                    ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache'))
    receipts = {}
    for name, (expected, replacements) in PATCHES.items():
        target = destination / 'benchmark_mysr/external' / name
        text = target.read_text()
        for before, after in replacements:
            text = text.replace(before, after, 1)
        if name in ('worker.py', 'solvers.py'):
            # Put the constant after the module docstring, retaining its meaning.
            anchor = 'import '
            index = text.index(anchor)
            text = text[:index] + 'AMENDMENT = ' + repr(AMENDMENT) + '\n\n' + text[index:]
        compile(text, str(target), 'exec')
        target.write_text(text)
        receipts[name] = {'original_sha256': expected, 'amended_sha256': sha(target)}
    return receipts


def training_eligibility(request, cache):
    """Inspect observed training rows only; no held-out data or reference formula."""
    if request['method'] == 'ai_feynman_2':
        return {'eligible': True, 'reason': 'ai_feynman_scope_only'}
    if request['method'] != 'tf4sr':
        raise ValueError('Unexpected method in original NA set')
    path = Path(request['data']) / 'train.csv'
    key = str(path)
    if key not in cache:
        with path.open() as stream:
            reader = csv.DictReader(stream)
            features = [name for name in reader.fieldnames if name.startswith('x_')]
            values = [([float(row[name]) for name in features], float(row['target']))
                      for row in reader]
        # Match the frozen common multiplicative preprocessor, including
        # floating-point underflow and the public angular-coordinate rule.
        scales = [max(abs(row[j]) for row, _ in values) or 1.0
                  for j in range(len(features))]
        for j, unit in enumerate(request.get('input_units', [])):
            if unit == '$rad$':
                scales[j] = 1.0
        yscale = max(abs(y) for _, y in values) or 1.0
        rows = len(values)
        valid = sum(y / yscale != 0 and all(x / s > 0 for x, s in zip(row, scales))
                    for row, y in values)
        cache[key] = {'features': len(features), 'training_rows': rows,
                      'native_eligible_training_rows': valid}
    detail = dict(cache[key])
    reason = ('more_than_six_inputs' if detail['features'] > 6 else
              'fewer_than_50_positive_nonzero_rows'
              if detail['native_eligible_training_rows'] < 50 else 'tf4sr_scope_only')
    return dict(detail, eligible=reason == 'tf4sr_scope_only', reason=reason)


def prepare(original, baseline, frozen, root, helpers, workers):
    original, baseline, frozen, root, helpers = map(Path, (original, baseline, frozen, root, helpers))
    requests = original / 'requests.jsonl'
    if sha(requests) != REQUEST_SHA:
        raise ValueError('Original frozen requests changed')
    marker = json.loads((baseline / 'RUN_COMPLETE.json').read_text())
    summary = baseline / 'final-audit/summary.json'
    if sha(summary) != marker['audit_summary_sha256']:
        raise ValueError('Original audit completion marker mismatch')
    if json.loads(summary.read_text())['missing_results']:
        raise ValueError('Original matrix must have no missing records')
    records = baseline / 'final-audit/records.jsonl'
    not_applicable = {}
    with records.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('status') == 'not_applicable':
                if row['issues']:
                    raise ValueError('Unaudited original NA result')
                not_applicable[row['relative_output']] = row
    if len(not_applicable) != 20980:
        raise ValueError('Unexpected original not-applicable count')
    root.mkdir(parents=True, exist_ok=False)
    for name in ('results', 'slurm', 'orchestration', 'preflight', 'audit'):
        (root / name).mkdir()
    patches = patch_sources(frozen, root / 'code')
    for name in ('extend_applicability.py', 'run_applicability_extension.py', 'resilient_node_pool.py'):
        shutil.copy2(helpers / name, root / 'orchestration' / name)
    count, selection, skipped, cache, preflight = Counter(), [], [], {}, {}
    with requests.open('rb') as source, (root / 'requests.jsonl').open('wb') as output:
        for raw in source:
            item = json.loads(raw)
            relative = item['relative_output']
            if relative not in not_applicable:
                continue
            if Path(relative).is_absolute() or '..' in Path(relative).parts:
                raise ValueError('Unsafe output path')
            request = item['request']
            eligibility = training_eligibility(request, cache)
            count[eligibility['reason']] += 1
            if not eligibility['eligible']:
                skipped.append({'relative_output': relative, 'method': request['method'], **eligibility})
                continue
            old_path = Path(not_applicable[relative]['result'])
            old_raw = old_path.read_bytes()
            old = json.loads(old_raw)
            if old['status'] != 'not_applicable':
                raise ValueError('Selected original was not NA')
            request['applicability_amendment'] = AMENDMENT
            request['original_not_applicable'] = {
                'result': str(old_path), 'sha256': hashlib.sha256(old_raw).hexdigest(),
                'request_line_sha256': hashlib.sha256(raw).hexdigest(),
                'reason': old.get('reason', old.get('failure_reason')),
            }
            raw_new = (json.dumps(item, sort_keys=True, allow_nan=False) + '\n').encode()
            index = {'kind': 'comparison_fit', 'method': request['method'],
                     'offset': output.tell(), 'sha256': hashlib.sha256(raw_new).hexdigest(),
                     'relative_output': relative}
            selection.append(index)
            output.write(raw_new)
            # Deterministic startup gate, independent of all fitted/test outcomes.
            kind = ('ai_feynman_blackbox' if request['method'] == 'ai_feynman_2' else
                    'tf4sr_ode' if request.get('component') is not None else 'tf4sr_tabular')
            if request['resource_track'] == 'constrained_resource':
                preflight.setdefault(kind, index)
    if len(selection) != 12100 or sum(count.values()) != 20980:
        raise ValueError('Eligibility census differs from reviewed counts')
    dump(root / 'fits-index.json', {'schema': AMENDMENT, 'fits': selection})
    dump(root / 'preflight/fits-index.json', {'schema': AMENDMENT, 'fits': list(preflight.values())})
    dump(root / 'unsupported.json', {'records': skipped})
    dump(root / 'census.json', {'original_not_applicable': 20980, 'scheduled': len(selection),
                               'unsupported': len(skipped), 'reasons': dict(count),
                               'training_files_examined': len(cache)})
    dump(root / 'amendment.json', {
        'id': AMENDMENT,
        'authority': 'User2026-10-27: run previously not-applicable cases if they can run',
        'changes': 'Remove dataset-family/known-equation registration gates only',
        'unchanged': ['all input columns', 'all data split bytes', 'search seeds',
                      '120/900-second scientific track budgets', 'solver parameters',
                      'positive-input sampling', 'six-variable pretrained weights',
                      'validation-only model selection', 'held-out evaluation'],
        'analysis_policy': 'Use each scheduled extension outcome, including failures, for its former NA slot; never select the better test result across attempts. Keep original B7 as a separate immutable protocol. Report unsupported coverage separately.',
        'no_mysr_execution': True, 'formal_comparison_ready': False, 'patches': patches,
    })
    code_hashes = {str(p.relative_to(root / 'code')): sha(p)
                   for p in (root / 'code').rglob('*') if p.is_file()}
    dump(root / 'source-manifest.json', code_hashes)
    config = {
        'root': str(root.resolve()), 'workers': workers, 'node': 'carbon',
        'original': str(original.resolve()), 'baseline': str(baseline.resolve()),
        'baseline_records_sha256': sha(records), 'requests_sha256': sha(root / 'requests.jsonl'),
        'index_sha256': sha(root / 'fits-index.json'), 'source_manifest_sha256': sha(root / 'source-manifest.json'),
        'supervisor_python': '${SUPERVISOR_PYTHON}',
        'bundles': str(Path('parallel_comparsion/runtime-bundles/20260926-v1').resolve()),
        'resource_epoch': 'carbon-128-physical-native-scope-extension-20261027',
        'applicability_amendment': AMENDMENT,
    }
    dump(root / 'config.json', config)
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--frozen', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=128)
    args = parser.parse_args()
    config = prepare(args.original, args.baseline, args.frozen, args.root,
                     Path(__file__).resolve().parent, args.workers)
    print(json.dumps({'root': config['root'], 'config_sha256': sha(args.root / 'config.json')}))


if __name__ == '__main__':
    main()
