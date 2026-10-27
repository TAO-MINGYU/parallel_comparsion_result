import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/external/build_report_tables.py'
spec = importlib.util.spec_from_file_location('report_tables', SCRIPT)
tables = importlib.util.module_from_spec(spec); spec.loader.exec_module(tables)


def row(usable=True, applicable=True, component=0, value=.05):
    return {'method': 'fixture', 'task_id': 'ode', 'variant': 'noise01_nodrop',
            'resource_track': 'constrained_resource', 'seed': 7, 'dimension': 2,
            'component': component, 'applicable': applicable,
            'primary_usable': usable, 'observed_usable': usable,
            'status': 'not_applicable' if not applicable else 'success' if usable else 'invalid_output',
            'primary_nrmse': value if usable else None, 'observed_nrmse': 2 if usable else None,
            'resource_epoch': 'epoch', 'result': {'runtime': 3, 'cpu_time': 2, 'peak_memory': 10}}


def test_failures_remain_in_attainment_denominator_and_na_is_separate():
    bucket = tables.Bucket()
    for r in [row(), row(usable=False), row(usable=False, applicable=False)]:bucket.add(r)
    summary = bucket.summary()
    assert summary['registered'] == 3 and summary['applicable'] == 2
    assert summary['not_applicable'] == 1
    assert summary['primary_nrmse_le_0.1_count'] == 1
    assert summary['primary_nrmse_le_0.1_rate_all_applicable'] == .5
    assert summary['observed_nrmse_le_0.1_count'] == 0
    assert summary['primary_conditional_median_nrmse'] == .05


def test_ode_macro_average_requires_all_components():
    system = tables.aggregate_system([row(component=0, value=.05), row(component=1, value=.15)])
    assert system['primary_usable']
    assert system['primary_nrmse'] == .1
    assert system['components_present'] == 2
    assert system['result']['cpu_time'] == 4
    failed = tables.aggregate_system([row(component=0), row(usable=False, component=1)])
    assert not failed['primary_usable'] and failed['primary_nrmse'] is None


@pytest.mark.parametrize('components', [[0], [0, 0], [0, 2]])
def test_incomplete_or_duplicate_ode_components_fail_closed(components):
    with pytest.raises(ValueError, match='Incomplete or duplicate'):
        tables.aggregate_system([row(component=c) for c in components])


def test_quantiles_are_explicit_and_empty_is_missing():
    assert tables.quantile([], .5) is None
    assert tables.quantile([2, 4], .5) == 3
    assert tables.quantile([2], .9) == 2
