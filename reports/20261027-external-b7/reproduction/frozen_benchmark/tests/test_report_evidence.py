import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/external/collect_report_evidence.py'
spec = importlib.util.spec_from_file_location('report_evidence', SCRIPT)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def fixture(tmp_path, truth=True, status='search_timeout'):
    result = {'method': 'pysr', 'task_id': 'fixture', 'seed': 7, 'variant': 'output_noise_10',
              'resource_track': 'constrained_resource', 'budget': {'search_seconds': 120},
              'comparison_protocol': 'frozen', 'comparison_protocol_sha256': 'protocol',
              'data_hashes': {'train': 'T', 'validation': 'V', 'test': 'H'},
              'status': status, 'selected_expression': 'x0',
              'train_score': {'mse': 1., 'nrmse': 1.},
              'validation_score': {'mse': 2., 'nrmse': 2.},
              'test_score': {'mse': 4., 'nrmse': 2.},
              'test_clean_score': {'mse': .01, 'nrmse': .1}}
    request = {k: v for k, v in result.items() if k in ('method', 'task_id', 'seed', 'variant',
               'resource_track', 'budget', 'comparison_protocol', 'comparison_protocol_sha256')}
    request.update(expected_data_hashes=result['data_hashes'], ground_truth_available=truth)
    path = tmp_path / 'fit/result.json'; path.parent.mkdir()
    path.write_text(json.dumps(result))
    audit = {'result': str(path), 'relative_output': 'fit', 'family': 'srsd',
             'status': status, 'selected_expression': 'x0', 'usable': True,
             'test_nrmse': 2., 'issues': [], 'writer_job': 'job', 'resource_epoch': 'epoch'}
    return result, request, path, audit


def test_observed_and_clean_targets_are_separate_and_timeout_can_be_usable(tmp_path):
    result, request, path, audit = fixture(tmp_path)
    row = evidence.export_one((audit, request, 'line', [('B7', tmp_path)], []))
    assert row['status'] == 'search_timeout'
    assert row['observed_nrmse'] == 2
    assert row['primary_nrmse'] == .1
    assert row['primary_target'] == 'clean_latent'
    assert row['observed_usable'] and row['primary_usable']
    assert row['issues'] == []
    assert row['raw_result_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_blackbox_primary_target_remains_observed(tmp_path):
    result, request, path, audit = fixture(tmp_path, truth=False)
    row = evidence.export_one((audit, request, 'line', [('B7', tmp_path)], []))
    assert row['primary_target'] == 'observed_blackbox'
    assert row['primary_nrmse'] == 2


@pytest.mark.parametrize('mutation', ['seed', 'data', 'metric', 'expression'])
def test_modified_final_result_fails_closed(tmp_path, mutation):
    result, request, path, audit = fixture(tmp_path)
    if mutation == 'seed': result['seed'] = 8
    elif mutation == 'data': result['data_hashes'] = {}
    elif mutation == 'metric': result['test_score']['nrmse'] = .5
    else: result['selected_expression'] = 'fabricated'
    path.write_text(json.dumps(result))
    row = evidence.export_one((audit, request, 'line', [('B7', tmp_path)], []))
    assert row['issues']


def test_invalid_output_is_retained_without_fabricating_a_score(tmp_path):
    result, request, path, audit = fixture(tmp_path, status='invalid_output')
    result['test_score'] = None; result['test_clean_score'] = None
    path.write_text(json.dumps(result)); audit.update(usable=False, test_nrmse=None)
    row = evidence.export_one((audit, request, 'line', [('B7', tmp_path)], []))
    assert not row['observed_usable'] and not row['primary_usable']
    assert row['primary_nrmse'] is None
    assert row['result']['selected_expression'] == 'x0'
    assert row['issues'] == []


def test_portable_paths_do_not_change_numbers_or_formulas():
    value = {'path': '/data/project/file', 'expression': 'x0/2', 'metric': 1e-8}
    out = evidence.portable(value, [('/data/project', '${B7_ROOT}')])
    assert out == {'path': '${B7_ROOT}/file', 'expression': 'x0/2', 'metric': 1e-8}
    assert value['path'] == '/data/project/file'
