#!/usr/bin/env python3
"""Recompute publication tables from the portable, complete result metadata."""
import argparse
import bisect
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import statistics


METHODS = ('pysr', 'operon', 'dsr', 'ai_feynman_2', 'gplearn', 'tf4sr')
THRESHOLDS = (1e-6, 1e-4, .01, .1, 1., 10.)


def quantile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return values[low] * (high - index) + values[high] * (index - low) if low != high else values[low]


class Bucket:
    def __init__(self):
        self.counts = Counter()
        self.primary, self.observed = [], []
        self.runtime, self.cpu, self.rss = [], [], []

    def add(self, row):
        self.counts['registered'] += 1
        self.counts['applicable'] += row['applicable']
        self.counts[row['status']] += 1
        self.counts['primary_usable'] += row['primary_usable']
        self.counts['observed_usable'] += row['observed_usable']
        if row['primary_usable']:
            self.primary.append(row['primary_nrmse'])
        if row['observed_usable']:
            self.observed.append(row['observed_nrmse'])
        if row['applicable']:
            result = row['result']
            for key, target in [('runtime', self.runtime), ('cpu_time', self.cpu), ('peak_memory', self.rss)]:
                value = result.get(key)
                if isinstance(value, (float, int)) and math.isfinite(value):
                    target.append(value)

    def summary(self):
        out = {k: self.counts[k] for k in ('registered', 'applicable', 'primary_usable',
               'observed_usable', 'success', 'search_timeout', 'invalid_output', 'not_applicable')}
        out['applicable_without_primary_prediction'] = out['applicable'] - out['primary_usable']
        for name in ('primary', 'observed'):
            values = sorted(getattr(self, name))
            out[name + '_conditional_median_nrmse'] = quantile(values, .5)
            for threshold in THRESHOLDS:
                label = name + '_nrmse_le_' + str(threshold)
                count = bisect.bisect_right(values, threshold)
                out[label + '_count'] = count
                out[label + '_rate_all_applicable'] = count / out['applicable'] if out['applicable'] else None
        for label, values in [('elapsed_seconds', self.runtime), ('cpu_seconds', self.cpu), ('peak_rss_bytes', self.rss)]:
            out[label + '_count'] = len(values)
            out[label + '_median'] = quantile(values, .5)
            out[label + '_p90'] = quantile(values, .9)
            out[label + '_sum'] = sum(values)
        return out


def case_key(row):
    return '/'.join([row['relative_output'].split('/')[0], *row['relative_output'].split('/')[2:]])


def aggregate_system(rows):
    rows = sorted(rows, key=lambda r: r['component'])
    dimension = rows[0]['dimension']
    if [row['component'] for row in rows] != list(range(dimension)):
        raise ValueError('Incomplete or duplicate ODE components')
    row = rows[0]
    applicable = all(r['applicable'] for r in rows)
    usable = all(r['primary_usable'] for r in rows)
    observed = all(r['observed_usable'] for r in rows)
    return {'method': row['method'], 'task_id': row['task_id'], 'variant': row['variant'],
            'resource_track': row['resource_track'], 'seed': row['seed'], 'dimension': dimension,
            'components_present': len(rows), 'applicable': applicable, 'primary_usable': usable,
            'observed_usable': observed,
            'status': 'not_applicable' if not applicable else 'success' if usable else 'invalid_output',
            'primary_nrmse': sum(r['primary_nrmse'] for r in rows) / dimension if usable else None,
            'observed_nrmse': sum(r['observed_nrmse'] for r in rows) / dimension if observed else None,
            'resource_epochs': sorted({r['resource_epoch'] for r in rows}),
            'result': {'runtime': sum(r['result']['runtime'] for r in rows),
                       'cpu_time': sum(r['result']['cpu_time'] for r in rows),
                       'peak_memory': max(r['result']['peak_memory'] for r in rows)}}


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        raise ValueError('Refusing to write an empty report table')
    fields = list(rows[0])
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def build(evidence, output):
    evidence, output = Path(evidence), Path(output)
    collection = json.loads((evidence / 'collection-summary.json').read_text())
    if collection['issue_count'] or collection['counts']['records'] != 221400:
        raise ValueError('Requires the successful complete221400 record collection')
    output.mkdir(parents=True, exist_ok=True)
    buckets, cases, systems = defaultdict(Bucket), defaultdict(dict), defaultdict(list)
    epochs, statuses, semantic_counts = Counter(), Counter(), Counter()
    by_status_usable = Counter()
    raw_hash = hashlib.sha256()
    for method in METHODS:
        path = evidence / (method + '.results.jsonl.gz')
        expected = collection['outputs'][path.name]['sha256']
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Published input hash mismatch: ' + path.name)
        with gzip.open(path, 'rt') as stream:
            for line in stream:
                raw_hash.update(line.encode())
                row = json.loads(line)
                if row['issues'] or row['method'] != method:
                    raise ValueError('Unreviewed or misfiled raw result')
                result = row['result']
                # Retain small fields only for paired/common and system tables.
                compact = {k: row[k] for k in ('relative_output', 'method', 'kind', 'family', 'task_id',
                    'variant', 'resource_track', 'seed', 'component', 'dimension', 'status',
                    'applicable', 'primary_usable', 'observed_usable', 'primary_nrmse',
                    'observed_nrmse', 'resource_epoch')}
                compact['result'] = {k: result.get(k) for k in ('runtime', 'cpu_time', 'peak_memory')}
                compact['data_hashes'] = result['data_hashes']
                compact['budget'] = result['budget']
                key = case_key(row)
                if method in cases[key]:
                    raise ValueError('Duplicate paired method/case')
                cases[key][method] = compact
                for group in [('overall', method), ('kind', method, row['kind']),
                              ('condition', method, row['kind'], row['variant'], row['resource_track']),
                              ('family', method, row['family'], row['variant'], row['resource_track']),
                              ('resource_epoch', method, row['resource_epoch'])]:
                    buckets[group].add(row)
                epochs[row['resource_epoch']] += 1
                statuses[row['status']] += 1
                semantic_counts[(method, result.get('evaluation_semantics'), result.get('evaluations') == 0)] += 1
                by_status_usable[(row['status'], row['observed_usable'])] += 1
                if row['component'] is not None:
                    systems[(method, str(Path(row['relative_output']).parent))].append(compact)
    if len(cases) != 36900 or any(set(members) != set(METHODS) for members in cases.values()):
        raise ValueError('Incomplete six-method paired matrix')
    common, catalog, conditions_by_case = 0, [], {}
    for key, members in sorted(cases.items()):
        data = {json.dumps(row['data_hashes'], sort_keys=True) for row in members.values()}
        budgets = {json.dumps(row['budget'], sort_keys=True) for row in members.values()}
        if len(data) != 1 or len(budgets) != 1:
            raise ValueError('Mismatched paired data or budget: ' + key)
        applicable_methods = [m for m in METHODS if members[m]['applicable']]
        if len(applicable_methods) == 6:
            common += 1
            for method, row in members.items():
                buckets['common_all_six', method].add(row)
                buckets['common_kind', method, row['kind']].add(row)
                buckets['common_condition', method, row['kind'], row['variant'], row['resource_track']].add(row)
        example = members[METHODS[0]]
        conditions = set()
        for member in members.values():
            epoch = member['resource_epoch']
            if '374-logical' in epoch:
                conditions.add('carbon_374_logical_SMT')
            elif '128-physical' in epoch:
                conditions.add('carbon_128_physical')
            else:
                raise ValueError('Unclassified resource epoch: ' + epoch)
        conditions_by_case[key] = sorted(conditions)
        catalog.append({'case_key': key, 'kind': example['kind'], 'family': example['family'],
                        'task_id': example['task_id'], 'variant': example['variant'],
                        'resource_track': example['resource_track'], 'seed': example['seed'],
                        'component': example['component'], 'dimension': example['dimension'],
                        'applicable_methods': ';'.join(applicable_methods),
                        'shared_data_hashes': next(iter(data)), 'shared_budget': next(iter(budgets)),
                        'resource_epochs_by_method': json.dumps({m: members[m]['resource_epoch'] for m in METHODS}, sort_keys=True)})
    if common != 28020:
        raise ValueError('Unexpected common applicability set')
    write_csv(output / 'paired-case-catalog.csv', catalog)
    template_counts = Counter()
    with gzip.open(evidence / 'effective-requests.portable.jsonl.gz', 'rt') as source, \
            (output / 'mysr-run-template.jsonl.gz').open('wb') as binary:
        with gzip.GzipFile(filename='', mode='wb', fileobj=binary, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding='utf-8', newline='\n') as target:
                for line in source:
                    item = json.loads(line)
                    if item['request']['method'] != 'pysr':
                        continue
                    key = case_key(item)
                    parts = item['relative_output'].split('/'); parts[1] = 'mysr'
                    req = dict(item['request'], method='mysr')
                    for condition in conditions_by_case[key]:
                        template = {'case_key': key, 'hardware_condition': condition,
                                    'relative_output': condition + '/' + '/'.join(parts), 'request': req,
                                    'mysr_parameters': None,
                                    'execution_status': 'template_only_not_launched',
                                    'note': 'A future MySR adapter and frozen MySR settings are required; do not pass this to the six-method external worker.'}
                        target.write(json.dumps(template, separators=(',', ':'), allow_nan=False) + '\n')
                        template_counts[condition] += 1
    system_rows, system_buckets, paired_systems = [], defaultdict(Bucket), defaultdict(dict)
    for (method, key), rows in sorted(systems.items()):
        row = aggregate_system(rows)
        parts = key.split('/')
        paired_systems['/'.join([parts[0], *parts[2:]])][method] = row
        system_buckets[method, row['variant'], row['resource_track']].add(row)
        system_buckets[method, 'ALL', 'ALL'].add(row)
        system_rows.append({k: v if not isinstance(v, (list, dict)) else json.dumps(v, sort_keys=True)
                            for k, v in row.items() if k != 'result'})
    if len(system_rows) != 37800:
        raise ValueError('Expected37800 complete system summaries')
    write_csv(output / 'ode-system-results.csv', system_rows)
    write_csv(output / 'ode-system-summary.csv', ({'method': k[0], 'variant': k[1],
               'resource_track': k[2], **bucket.summary()} for k, bucket in sorted(system_buckets.items())))
    system_common_buckets, common_systems = defaultdict(Bucket), 0
    for key, members in paired_systems.items():
        if set(members) != set(METHODS):
            raise ValueError('Incomplete six-method ODE system matrix: ' + key)
        if all(row['applicable'] for row in members.values()):
            common_systems += 1
            for method, row in members.items():
                system_common_buckets[method, row['variant'], row['resource_track']].add(row)
                system_common_buckets[method, 'ALL', 'ALL'].add(row)
    if len(paired_systems) != 6300 or common_systems != 4300:
        raise ValueError('Unexpected whole-system common applicability set')
    write_csv(output / 'ode-system-common-summary.csv', ({'method': k[0], 'variant': k[1],
               'resource_track': k[2], **bucket.summary()} for k, bucket in sorted(system_common_buckets.items())))
    layouts = {
        'overall': ('method',), 'kind': ('method', 'kind'),
        'condition': ('method', 'kind', 'variant', 'resource_track'),
        'family': ('method', 'family', 'variant', 'resource_track'),
        'resource_epoch': ('method', 'resource_epoch'),
        'common_all_six': ('method',), 'common_kind': ('method', 'kind'),
        'common_condition': ('method', 'kind', 'variant', 'resource_track'),
    }
    for name, fields in layouts.items():
        rows = [dict(zip(fields, key[1:]), **bucket.summary())
                for key, bucket in sorted(buckets.items()) if key[0] == name]
        write_csv(output / (name + '.csv'), rows)
    summary = {'records': sum(statuses.values()), 'statuses': dict(statuses),
               'resource_epochs': dict(epochs), 'paired_scalar_cases': len(cases),
               'common_all_six_applicable_scalar_cases': common,
               'complete_ode_system_records': len(system_rows),
               'common_all_six_applicable_ode_system_cases': common_systems,
               'future_mysr_template_requests_by_hardware_condition': dict(template_counts),
               'future_mysr_templates_are_not_executed_results': True,
               'observed_usable_by_status': [{'status': k[0], 'usable': k[1], 'records': v}
                                            for k, v in sorted(by_status_usable.items())],
               'evaluation_semantics': [{'method': k[0], 'raw_semantics': k[1],
                                        'raw_count_is_zero': k[2], 'records': v}
                                       for k, v in sorted(semantic_counts.items(), key=lambda x: str(x[0]))],
               'canonical_input_stream_sha256': raw_hash.hexdigest(),
               'primary_target_rule': 'Clean latent target for ground-truth tabular tasks; observed unchanged target for black-box; clean held-out derivative forODE. Invalid/no-model outcomes contribute zero to threshold attainment over applicable denominators.',
               'denominator_rule': 'All registered applicable fits; common-applicability tables use the exact same28020 scalar cases for every method. NA coverage reported separately. ODE systems require every component.',
               'formal_comparison_ready': False, 'mysr_results_present': False}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(build(args.evidence, args.output)))
