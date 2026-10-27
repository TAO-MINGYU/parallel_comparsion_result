#!/usr/bin/env python3
"""Replay one explicitly selected published fit in new, user-supplied locations."""
import argparse
import gzip
import json
import os
from pathlib import Path
import sys


def expand(value, bindings):
    if isinstance(value, dict):return {k: expand(v, bindings) for k, v in value.items()}
    if isinstance(value, list):return [expand(v, bindings) for v in value]
    if isinstance(value, str):
        for key, path in bindings.items():value = value.replace('${' + key + '}', str(path))
    return value


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--requests', type=Path, required=True)
    p.add_argument('--relative-output', required=True)
    p.add_argument('--b7-root', type=Path, required=True)
    p.add_argument('--sources', type=Path, required=True)
    p.add_argument('--env-root', type=Path, required=True)
    p.add_argument('--output-root', type=Path, required=True)
    p.add_argument('--code-root', type=Path, default=Path(__file__).resolve().parents[2])
    args = p.parse_args()
    if len(os.sched_getaffinity(0)) != 1:
        raise ValueError('Run inside the documented one-CPU Slurm affinity')
    relative = Path(args.relative_output)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe output identity')
    output = args.output_root.resolve()
    if output.exists() or output.is_relative_to(args.b7_root.resolve()):
        raise ValueError('Use a new output root outside the preserved B7 input/result tree')
    selected = None
    with gzip.open(args.requests, 'rt') as stream:
        for line in stream:
            item = json.loads(line)
            if item['relative_output'] == args.relative_output:
                if selected is not None:raise ValueError('Duplicate published identity')
                selected = item['request']
    if selected is None:raise ValueError('Selected fit not found')
    if selected['method'] == 'mysr':
        raise ValueError('MySR templates need a future MySR adapter; no MySR execution here')
    request = expand(selected, {'B7_ROOT': args.b7_root.resolve()})
    request['source_root'] = str(args.sources.resolve())
    if '${' in request['data']:
        raise ValueError('Unresolved data root')
    sys.path.insert(0, str(args.code_root.resolve()))
    from benchmark_mysr.external.fair import protocol
    from benchmark_mysr.external.runner import run
    policy = protocol(request)
    if request['budget'] != policy['tracks'][request['resource_track']]:
        raise ValueError('Published scientific budget changed')
    if request.get('applicability_amendment'):
        from benchmark_mysr.external import solvers
        if getattr(solvers, 'AMENDMENT', None) != request['applicability_amendment']:
            raise ValueError('Apply the published scope patch before replaying an expanded-scope fit')
    result = run(request, output / relative, args.env_root.resolve())
    print(json.dumps({'status': result['status'], 'method': result['method'],
                      'task_id': result['task_id'], 'seed': result['seed']}))


if __name__ == '__main__':main()
