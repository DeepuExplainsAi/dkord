"""Bounded read-only transport of original screenshot ZIP bytes through Check notices.

The public release ZIP/artifact is primary. The workspace can reach api.github.com
but not redirected artifact storage. No credentials/private files enter this channel.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import zipfile

CHUNK = 114000


def plan(archive, output, source):
    if not re.fullmatch('[a-f0-9]{40}', source) or int(source, 16) == 0:
        raise ValueError('Exact gallery source required')
    data = archive.read_bytes()
    if not 100 < len(data) <= CHUNK * 200:
        raise ValueError('Screenshot archive exceeds bounded public transport')
    with zipfile.ZipFile(archive) as zip:
        manifest = json.loads(zip.read('gallery-manifest.json'))
        if manifest['source'] != source or manifest['screenCount'] != 180 or len(manifest['targets']) != 6:
            raise ValueError('Only complete six-target public screenshot galleries can be transported')
    output.mkdir(parents=True, exist_ok=False)
    parts = []
    for index, offset in enumerate(range(0, len(data), CHUNK)):
        chunk = data[offset:offset + CHUNK]
        name = f'chunk-{index:03}.bin'
        (output / name).write_bytes(chunk)
        parts.append(dict(index=index, name=name, bytes=len(chunk), sha256=hashlib.sha256(chunk).hexdigest()))
    receipt = dict(format=1, name=archive.name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), source=source, parts=parts)
    (output / 'transport.json').write_text(json.dumps(receipt))
    return receipt


def emit(folder, index, batch):
    receipt = json.loads((folder / 'transport.json').read_text())
    if type(index) is not int or not 0 <= index < len(receipt['parts']) or batch not in range(6):
        raise ValueError('Unknown screenshot transport part/batch')
    part = receipt['parts'][index]
    if part['index'] != index or part['name'] != f'chunk-{index:03}.bin':
        raise ValueError('Unexpected screenshot chunk identity')
    data = (folder / part['name']).read_bytes()
    if len(data) != part['bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
        raise ValueError('Original screenshot chunk bytes changed')
    provenance = {key: receipt[key] for key in ('format', 'name', 'bytes', 'sha256', 'source')}
    provenance.update(chunk=part, chunks=len(receipt['parts']))
    notices = ['::notice title=Dkord gallery chunk provenance::' + json.dumps(provenance, separators=(',', ':'))]
    encoded = base64.b64encode(data).decode('ascii')
    pieces = [encoded[i:i + 3800] for i in range(0, len(encoded), 3800)]
    for position, piece in enumerate(pieces, 1):
        notices.append(f'::notice title=Dkord gallery chunk {index} part {position} of {len(pieces)}::' + piece)
    if len(notices) > 48:
        raise ValueError('Screenshot transport exceeds per-job notice budget')
    for notice in notices[batch * 8:(batch + 1) * 8]:
        print(notice)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('plan'); p.add_argument('--archive', required=True, type=Path); p.add_argument('--output', required=True, type=Path); p.add_argument('--source', required=True)
    p = commands.add_parser('emit'); p.add_argument('--folder', required=True, type=Path); p.add_argument('--part', required=True, type=int); p.add_argument('--batch', required=True, type=int, choices=range(6))
    args = parser.parse_args()
    if args.command == 'plan':
        receipt = plan(args.archive, args.output, args.source)
        import os
        matrix = json.dumps({'include': [{'part': p['index']} for p in receipt['parts']]})
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('matrix=' + matrix + '\n')
        print('::notice title=Screenshot archive transport::' + json.dumps({k: v for k, v in receipt.items() if k != 'parts'}))
    else:
        emit(args.folder, args.part, args.batch)
