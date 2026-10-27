#!/usr/bin/env python3
"""Package exact frozen CSV inputs and independently verify every tar member.

No original file is moved, rewritten or deleted. Only numerical input CSVs
and supplied attribution documents enter the archive; no upstream source code
or environment binaries are redistributed by this program.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile


class HashReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, n=-1):
        block = self.stream.read(n)
        self.digest.update(block)
        return block


def collect_csvs(requests, b7):
    b7 = Path(b7)
    files, cases = {}, {}
    with Path(requests).open() as stream:
        for line in stream:
            req = json.loads(line)['request']
            directory = Path(req['data'])
            relative = directory.relative_to(b7)
            if relative.parts[0] != 'data' or '..' in relative.parts:
                raise ValueError('Unexpected frozen input location')
            cases[str(relative)] = {'expected_data_hashes': req['expected_data_hashes'],
                                    'task_id': req['task_id'], 'variant': req['variant']}
            for split, expected in req['expected_data_hashes'].items():
                if split not in ('train', 'validation', 'test'):
                    raise ValueError('Unregistered data split')
                key = str(relative / (split + '.csv'))
                if key in files and files[key] != expected:
                    raise ValueError('Conflicting immutable data hash')
                files[key] = expected
    return files, cases


def verify_archive(path, expected):
    seen = {}
    with tarfile.open(path, 'r:gz') as archive:
        for entry in archive:
            if not entry.isfile() or entry.name.startswith('/') or '..' in Path(entry.name).parts:
                raise ValueError('Unsafe archive entry')
            if entry.name in seen or entry.name not in expected:
                raise ValueError('Unexpected or duplicate archive member')
            h = hashlib.sha256()
            with archive.extractfile(entry) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
            if h.hexdigest() != expected[entry.name]:
                raise ValueError('Archive readback checksum mismatch')
            seen[entry.name] = h.hexdigest()
    if seen != expected:
        raise ValueError('Missing archive member')
    return len(seen)


def package(requests, b7, output, notices):
    b7, output, notices = map(Path, (b7, output, notices))
    files, cases = collect_csvs(requests, b7)
    if len(cases) != 1845 or len(files) != 5535:
        raise ValueError('Unexpected full frozen input coverage')
    expected = dict(files)
    extras = {}
    manifest = {'schema': 'b7-exact-input-bytes-v1', 'cases': cases, 'csv_sha256': files,
                'scalar_data_cases': len(cases), 'split_csvs': len(files),
                'layout': 'Set B7_ROOT to the extracted directory; data paths are beneath data/.',
                'upstream_program_sources_included': False}
    extras['INPUT_MANIFEST.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    for p in sorted(notices.iterdir()):
        if p.is_file():
            extras['ATTRIBUTIONS/' + p.name] = p.read_bytes()
    if not extras or len(extras) == 1:
        raise ValueError('Attribution files required')
    expected.update({name: hashlib.sha256(data).hexdigest() for name, data in extras.items()})
    if output.exists():
        raise ValueError('Refusing to replace an existing frozen input archive')
    with output.open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=1, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
                for name, expected_sha in sorted(files.items()):
                    source = b7 / name
                    before = source.stat()
                    if not source.is_file() or source.is_symlink():
                        raise ValueError('Only regular frozen CSV sources are accepted')
                    info = tarfile.TarInfo(name); info.size = before.st_size; info.mode = 0o644
                    with source.open('rb') as stream:
                        reader = HashReader(stream); archive.addfile(info, reader)
                    after = source.stat()
                    if reader.digest.hexdigest() != expected_sha or (
                            before.st_ino, before.st_size, before.st_mtime_ns) != (
                            after.st_ino, after.st_size, after.st_mtime_ns):
                        raise ValueError('Frozen source data changed during packaging')
                for name, data in sorted(extras.items()):
                    info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o644
                    archive.addfile(info, io.BytesIO(data))
    members = verify_archive(output, expected)
    h = hashlib.sha256()
    with output.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):h.update(block)
    receipt = {'archive': output.name, 'bytes': output.stat().st_size, 'sha256': h.hexdigest(),
               'verified_members': members, 'csv_files': len(files), 'data_cases': len(cases),
               'every_source_csv_matches_frozen_request': True,
               'every_archived_member_independently_read_back': True,
               'original_files_modified_or_deleted': False}
    output.with_name(output.name + '.verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--requests', type=Path, required=True)
    p.add_argument('--b7-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--notices', type=Path, required=True)
    args = p.parse_args()
    package(args.requests, args.b7_root, args.output, args.notices)
