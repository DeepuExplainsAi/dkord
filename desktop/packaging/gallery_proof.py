"""Verify actual source-bound frozen native galleries and package an offline viewer.

No image synthesis or retouching. Original PNG bytes and runtime/source/hash
receipts are retained for every target; generated fixtures are conspicuously labelled.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import struct
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dkord_desktop import __version__
from dkord_desktop.gallery_contract import SCREENS

TARGETS = ('windows-x64', 'windows-x86', 'macos-x64', 'macos-arm64', 'linux-x64', 'linux-arm64')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(folder, source, target, version=__version__, frozen=True):
    if target not in TARGETS or not re.fullmatch('[a-f0-9]{40}', source) or int(source, 16) == 0:
        raise ValueError('Exact gallery target/source is required')
    proof_path = folder / 'gallery-proof.json'
    if proof_path.is_symlink() or not proof_path.is_file() or proof_path.stat().st_size > 100_000:
        raise ValueError('Missing/bounded gallery proof')
    proof = json.loads(proof_path.read_text(encoding='utf-8'))
    expected_os = 'Windows' if target.startswith('windows-') else 'Darwin' if target.startswith('macos-') else 'Linux'
    x86 = target == 'windows-x86'
    if (proof.get('format') != 1 or proof.get('application') != 'Dkord' or proof.get('source') != source
            or proof.get('version') != version or proof.get('platform') != target or proof.get('os') != expected_os
            or proof.get('python_bits') != (32 if x86 else 64) or proof.get('qt_binding') != ('PyQt5' if x86 else 'PyQt6')
            or proof.get('frozen') is not frozen or not proof.get('qt_version', '').startswith('5.15.' if x86 else '6.10.')
            or proof.get('liveProviderTested') is not False or proof.get('heardAudioTested') is not False
            or proof.get('userDataAccessed') is not False or 'OFFLINE DEMO' not in proof.get('data', '')):
        raise ValueError('Gallery runtime/source/fixture provenance mismatch')
    records = proof.get('images')
    if (not isinstance(records, list) or len(records) != len(SCREENS)
            or {r.get('id') for r in records} != set(SCREENS)):
        raise ValueError('Incomplete or duplicated native screenshot gallery')
    expected = {'gallery-proof.json'}
    for record in records:
        name = record['id'] + '.png'
        if record.get('name') != name or not isinstance(record.get('title'), str) or not record['title']:
            raise ValueError('Invalid gallery image name/title')
        path = folder / name
        if path.is_symlink() or not path.is_file() or not 100 < path.stat().st_size <= 2 * 1024**2:
            raise ValueError('Missing/oversized gallery PNG')
        data = path.read_bytes()
        if (record.get('bytes') != len(data) or record.get('sha256') != sha(data)
                or data[:8] != b'\x89PNG\r\n\x1a\n'
                or struct.unpack('>II', data[16:24]) != (record.get('width'), record.get('height'))
                or not 200 <= record['width'] <= 4096 or not 150 <= record['height'] <= 4096
                or 'OFFLINE DEMO' not in record.get('data', '')):
            raise ValueError('Gallery PNG bytes/dimensions/fixture label mismatch')
        expected.add(name)
    if {p.name for p in folder.iterdir()} != expected:
        raise ValueError('Unexpected gallery files')
    return proof


def viewer(proofs, source, version):
    cards = []
    for target, proof in proofs.items():
        for record in proof['images']:
            url = target + '/' + record['name']
            caption = html.escape(record['title'])
            cards.append(f'<article data-platform="{target}"><a href="{url}" target="_blank"><img loading="lazy" src="{url}" alt="{caption}"></a><div><small>{target} · {record["width"]}×{record["height"]}</small><h2>{caption}</h2><a href="{url}" download>Download original PNG ↗</a></div></article>')
    buttons = '<button data-filter="all" class="active">All 180 screenshots</button>' + ''.join(f'<button data-filter="{t}">{t}</button>' for t in TARGETS)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>dKORD {version} · Actual native PC screenshots</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#0c0c12;color:#eeeef5;font-family:system-ui,sans-serif}}header{{padding:48px 5vw 26px;max-width:1500px;margin:auto}}.eyebrow{{letter-spacing:.2em;color:#c4b5fd;font-size:12px}}h1{{font-size:clamp(30px,5vw,54px);letter-spacing:-.045em;line-height:1.08;margin:16px 0}}p{{color:#abaabc;max-width:850px;line-height:1.7}}.notice{{border:1px solid #4c4265;border-radius:12px;padding:14px 18px;background:#191421;color:#ddd3f6}}nav{{display:flex;flex-wrap:wrap;gap:8px;margin:25px 0}}button{{background:#20202d;color:#dddde8;border:1px solid #353545;padding:11px 16px;border-radius:25px;cursor:pointer}}button.active{{background:#d6c4ff;color:#221334;border-color:#d6c4ff}}main{{max-width:1600px;margin:auto;padding:0 5vw 60px;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:24px}}article{{background:#17171f;border:1px solid #30303c;border-radius:14px;overflow:hidden}}article img{{display:block;width:100%;height:300px;object-fit:contain;background:#09090d;padding:8px}}article div{{padding:18px}}h2{{font-size:16px;line-height:1.5;margin:9px 0 16px}}small{{color:#a2a1b4;font-size:12px}}a{{color:#cdb7ff;font-size:13px;text-decoration:none}}footer{{padding:25px 5vw;background:#13131b;color:#a2a1b4;font-size:12px;word-break:break-all}}[hidden]{{display:none!important}}
</style></head><body><header><div class="eyebrow">dKORD / NATIVE DESKTOP / {version}</div><h1>Every corner.<br>Actual PC screenshots.</h1><p>30 production pages, dialogs and responsive/theme states on each of six genuine OS/CPU builds. Click a screenshot to inspect its original full-resolution PNG. These are captured native Qt windows, not browser app mockups, AI images or phone screenshots.</p><p class="notice">OFFLINE DEMO: real locally generated tones and clearly labelled sample search/YouTube metadata. No user files, live-provider success, heard audio or physical-device acceptance is claimed.</p><nav>{buttons}</nav></header><main>{''.join(cards)}</main><footer>Exact application source: {source}<br>Original image SHA-256/runtime receipts: each platform’s gallery-proof.json and gallery-manifest.json. No image compositing or retouching.</footer><script>document.querySelectorAll('button[data-filter]').forEach(b=>b.onclick=()=>{{document.querySelectorAll('button[data-filter]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('article').forEach(c=>c.hidden=b.dataset.filter!=='all'&&c.dataset.platform!==b.dataset.filter)}});</script></body></html>'''


def bundle(root, output, source, version=__version__):
    proofs = {}
    folders = {}
    for target in TARGETS:
        folder = root / ('desktop-gallery-' + target)
        proofs[target] = verify(folder, source, target, version)
        folders[target] = folder
    manifest = dict(format=1, application='Dkord', version=version, source=source,
                    screenCount=len(SCREENS) * len(TARGETS), targets=proofs,
                    data='OFFLINE DEMO; no live/heard/physical-device acceptance')
    data = (json.dumps(manifest, indent=2) + '\n').encode()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'Dkord-PC-screenshots-v{version}.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zip:
        zip.writestr('index.html', viewer(proofs, source, version))
        zip.writestr('gallery-manifest.json', data)
        for target, folder in folders.items():
            for file in sorted(folder.iterdir()):
                zip.write(file, target + '/' + file.name)
    (output / f'Dkord-PC-screenshots-v{version}.json').write_bytes(data)
    print(f'::notice title=Native screenshot gallery::{manifest["screenCount"]} original native PNGs, all6 exact-source frozen targets; PNG hashes/runtime/fixture labels verified. No AI or browser app mockups.')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--version', default=__version__)
    parser.add_argument('--folder', type=Path)
    parser.add_argument('--target', choices=TARGETS)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.folder and args.target and not args.root:
        verify(args.folder, args.source, args.target, args.version)
    elif args.root and args.output and not args.folder:
        bundle(args.root, args.output, args.source, args.version)
    else:
        parser.error('Choose single-target verification or complete six-target bundle')
