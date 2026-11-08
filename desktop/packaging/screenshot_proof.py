"""Expose small, hash-bound requested screenshots over read-only Actions Check annotations.

Artifacts remain the primary download. The bounded notice transport lets the coding
workspace retrieve real Windows images via api.github.com without redirecting to a
blocked third-party artifact host. It contains ONLY isolated screenshot-mode files.
"""
import base64
import hashlib
import json
import re
from pathlib import Path
import struct
import sys


def main(folder, source=None, emit=True):
    proof=json.loads((folder/'windows-x86-screenshot-proof.json').read_text(encoding='utf-8'))
    assert proof['platform']=='windows-x86' and proof['os']=='Windows' and proof['python_bits']==32 and proof['qt_binding']=='PyQt5' and proof['frozen'] is True
    assert proof['format']==1 and proof['application']=='Dkord' and proof['version']=='0.10.0'
    assert re.fullmatch('[0-9a-f]{40}',proof['source']) and int(proof['source'],16)>0
    assert proof['qt_version'].startswith('5.15.')
    assert len(proof['images'])==2 and {x['name'] for x in proof['images']}=={'windows-x86-player.png','windows-x86-studio.png'}
    if source is not None:assert proof['source']==source
    if emit:print('::notice title=Dkord Windows screenshot provenance::'+json.dumps(proof,separators=(',',':')))
    for item in proof['images']:
        assert item['name'] in ('windows-x86-player.png','windows-x86-studio.png')
        assert 940<=item['width']<=4096 and 640<=item['height']<=4096
        data=(folder/item['name']).read_bytes()
        assert len(data)==item['bytes'] and len(data)<=512*1024 and hashlib.sha256(data).hexdigest()==item['sha256']
        assert data[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',data[16:24])==(item['width'],item['height'])
        if not emit:continue
        encoded=base64.b64encode(data).decode('ascii');parts=[encoded[i:i+58000] for i in range(0,len(encoded),58000)]
        for i,part in enumerate(parts,1):print(f'::notice title=Dkord Windows screenshot {item["name"]} part {i} of {len(parts)}::'+part)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);parser.add_argument('--source');parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args();main(args.folder,args.source,not args.verify_only)
