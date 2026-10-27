import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/external/package_frozen_inputs.py'
spec = importlib.util.spec_from_file_location('package_inputs', SCRIPT)
inputs = importlib.util.module_from_spec(spec); spec.loader.exec_module(inputs)


def test_archive_readback_checks_every_member_and_rejects_wrong_hash(tmp_path):
    path = tmp_path / 'input.tar.gz'
    data = b'x_0,target\n1,2\n'
    with tarfile.open(path, 'w:gz') as archive:
        info = tarfile.TarInfo('data/train.csv'); info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    expected = {'data/train.csv': hashlib.sha256(data).hexdigest()}
    assert inputs.verify_archive(path, expected) == 1
    with pytest.raises(ValueError, match='checksum mismatch'):
        inputs.verify_archive(path, {'data/train.csv': 'modified'})


def test_unsafe_archive_entry_is_rejected_without_extracting(tmp_path):
    path = tmp_path / 'unsafe.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        info = tarfile.TarInfo('../unsafe'); info.size = 1
        archive.addfile(info, io.BytesIO(b'x'))
    with pytest.raises(ValueError, match='Unsafe'):
        inputs.verify_archive(path, {'../unsafe': hashlib.sha256(b'x').hexdigest()})
    assert not (tmp_path.parent / 'unsafe').exists()


def test_conflicting_data_hashes_fail_before_archive_creation(tmp_path):
    q = {'data': str(tmp_path / 'data/case'), 'task_id': 'case', 'variant': 'clean',
         'expected_data_hashes': {'train': 'one'}}
    path = tmp_path / 'requests.jsonl'
    path.write_text(json.dumps({'request': q}) + '\n' +
                    json.dumps({'request': dict(q, expected_data_hashes={'train': 'two'})}) + '\n')
    with pytest.raises(ValueError, match='Conflicting'):
        inputs.collect_csvs(path, tmp_path)
