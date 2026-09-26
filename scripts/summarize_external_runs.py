#!/usr/bin/env python3
"""Audit expected external run slots without treating absent records as success."""
import argparse
from collections import Counter
import json
from pathlib import Path


def summarize(manifest, root):
    counts=Counter()
    missing=[]
    for unit in manifest['workunits']:
        base=Path(root)/unit['method_id']
        if 'system_index' in unit:
            base=base/unit['condition']/f'system-{unit["system_index"]+1}'
            variants=[unit['condition']]
        else:
            base=base/unit['task_id']
            variants=manifest['variants']
        for variant in variants:
            for track in manifest['resource_tracks']:
                for seed in manifest['formal_search_seeds']:
                    p=base/variant/track/str(seed)/'result.json'
                    if not p.exists():
                        counts['missing']+=1
                        if len(missing)<20:missing.append(str(p))
                        continue
                    try:
                        d=json.loads(p.read_text())
                        counts[d['status']]+=1
                    except (ValueError,KeyError):
                        counts['invalid_record']+=1
    total=sum(counts.values())
    return {'run_id':manifest['run_id'],'expected_records':manifest['run_count'],
            'enumerated_records':total,'counts':dict(counts),
            'complete':total==manifest['run_count'] and counts['missing']==0 and counts['invalid_record']==0,
            'formal_claim':False,'missing_examples':missing,
            'interpretation':'Completion includes timeout/failure/NA outcomes; no cross-method ranking is inferred.'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    d=summarize(json.loads(a.manifest.read_text()),a.root)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps(d,sort_keys=True))


if __name__=='__main__':
    main()
