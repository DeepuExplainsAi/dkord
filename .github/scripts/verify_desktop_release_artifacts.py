"""Promote only exact-head, hash-verified native CI DEVELOPMENT PREVIEWS, never a trust/signing claim."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import xml.etree.ElementTree as ET

TARGETS = ('windows-x64', 'windows-x86', 'macos-x64', 'macos-arm64', 'linux-x64', 'linux-arm64')
PARITY_CLASSES = ('CoreTest','UpdateTest','NativeWidgetTest','RoomProtocolTest','LyricsTest','PhoneContractTest','NewReleasesTest','DiagnosticsTest','ModernUpdateIdentityTest','PublicUpdateIdentityTest','CatalogueTest','ManifestSignerTest','UpgradeFixtureTest')
KINDS = {'windows-x64': ('exe',), 'windows-x86': ('exe',), 'macos-x64': ('pkg',), 'macos-arm64': ('pkg',),
         'linux-x64': ('deb', 'AppImage'), 'linux-arm64': ('deb', 'AppImage')}


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field in preview proof')
        result[key] = value
    return result


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def verify_tests(path, minimum=36, classes=('CoreTest', 'UpdateTest', 'NativeWidgetTest')):
    root = ET.parse(path).getroot()
    cases = root.findall('.//testcase')
    if len(cases) < minimum:
        raise ValueError('Missing executed native cases')
    for cls in classes:
        if not any(cls in c.get('classname', '') for c in cases):
            raise ValueError('Missing native test class ' + cls)
    if any(root.findall('.//' + marker) for marker in ('failure', 'error', 'skipped')):
        raise ValueError('Failed/error/skipped native tests cannot be promoted')
    suites = list(root.iter('testsuite'))
    if any(int(s.get(key, '0')) for s in suites for key in ('failures', 'errors', 'skipped')):
        raise ValueError('Nonzero native JUnit aggregate')
    leaf = [s for s in suites if s.findall('testcase')]
    if not leaf or sum(int(s.get('tests', '-1')) for s in leaf) != len(cases):
        raise ValueError('Inconsistent native JUnit test totals')


def verify_magic(path, target, kind):
    with path.open('rb') as source:
        header = source.read(64)
        if kind == 'exe':
            if len(header) < 64 or not header.startswith(b'MZ'):
                raise ValueError('Not a Windows installer')
            offset = struct.unpack_from('<I', header, 60)[0]
            if not 64 <= offset <= min(path.stat().st_size - 6, 8 * 1024 * 1024):
                raise ValueError('Invalid PE offset')
            source.seek(offset)
            pe = source.read(6)
            # An Inno Setup bootstrap may be x86 even when its tested bundled app is x64.
            if pe[:4] != b'PE\0\0' or struct.unpack('<H', pe[4:])[0] not in (0x14c, 0x8664):
                raise ValueError('Invalid Windows installer PE')
        elif kind == 'pkg' and not header.startswith(b'xar!'):
            raise ValueError('Not a macOS installer')
        elif kind == 'deb' and not header.startswith(b'!<arch>\n'):
            raise ValueError('Not a Debian package')
        elif kind == 'AppImage':
            expected = 183 if target.endswith('arm64') else 62
            if len(header) < 64 or header[:6] != b'\x7fELF\x02\x01' or header[8:11] != b'AI\x02' or int.from_bytes(header[18:20], 'little') != expected:
                raise ValueError('Not a matching-CPU AppImage')


def verify_and_stage(root, output, sha, version):
    if not re.fullmatch(r'[0-9a-f]{40}', sha) or int(sha, 16) == 0 or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid source/version')
    if root.is_symlink() or output.is_symlink():
        raise ValueError('Artifact/staging root cannot be a symlink')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Never overwrite previously staged assets')
    checked = []
    for target in TARGETS:
        folder = root / ('desktop-preview-' + target)
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError('Missing native artifact directory ' + target)
        manifest = folder / ('preview-' + target + '.json')
        if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 32_768:
            raise ValueError('Missing/bounded preview provenance')
        data = json.loads(manifest.read_text(encoding='utf-8'), object_pairs_hook=unique)
        if (data.get('channel') != 'development-preview' or data.get('version') != version or data.get('target') != target
                or data.get('source') != sha or data.get('trusted_signed_release') is not False or data.get('notarized') is not False):
            raise ValueError('Wrong source/version/target or misleading signing claim')
        if tuple(map(int,version.split('.'))) >= (0,10,1):
            evidence=data.get('installOver',{})
            if (evidence.get('format')!=1 or evidence.get('baselineTag')!='desktop-v0.10.0-preview.2'
                    or evidence.get('baselineSource')!='0d97e6413d999cdfbb562397cc230f1798f02606'
                    or evidence.get('toVersion')!=version or evidence.get('target')!=target or evidence.get('source')!=sha
                    or any(evidence.get(key) is not True for key in ('noUninstall','standardUserData','frozenClient'))):
                raise ValueError('Missing actual old-to-new installer and frozen-client data preservation proof')
            packages=evidence.get('packages',[])
            kinds=KINDS[target]
            if len(packages)!=len(kinds) or {entry.get('kind') for entry in packages}!=set(kinds):
                raise ValueError('Every installed package kind must be exercised, including both Linux kinds')
            for entry in packages:
                if entry.get('baselineName')!=f'Dkord-desktop-v0.10.0-{target}.{entry["kind"]}' or not re.fullmatch('[a-f0-9]{64}',entry.get('baselineSha256','')):
                    raise ValueError('Wrong immutable baseline installer')
                if any(entry.get('checks',{}).get(key) is not True for key in ('library','playlists','likes','history','settings','queue','privateDownload','deviceDownload','studioSources','studioClips','audioDecoded')):
                    raise ValueError('Incomplete actual frozen-client persistence/byte/native audio verification')
        runtime=data.get('runtime',{})
        x86=target=='windows-x86'
        if (runtime.get('python_bits')!=(32 if x86 else 64) or runtime.get('qt_binding')!=('PyQt5' if x86 else 'PyQt6')
                or runtime.get('audio_probe')!=('ffmpeg' if x86 else 'pyav')):
            raise ValueError('Wrong installed-process bitness/Qt/codec profile')
        if target.startswith('windows-'):
            arch='x86' if x86 else 'x64'
            expected={'application':arch,'node':arch,'ffmpeg':arch}
            if x86:expected['ffprobe']='x86'
            if runtime.get('verified_pe_payloads')!=expected:
                raise ValueError('Missing real application/Node/FFmpeg PE payload proof')
        if x86:
            source=data.get('codec_source',{})
            if (source.get('version')!='8.1.3' or source.get('source_commit')!='1041abdc962f4cc4f394aa8de9dc5236c0c3b9e7'
                    or source.get('source_archive_sha256')!='a406fe831cbb605f5fe50e43eb566e502ae63ff3b3206bfa744e4b31b8bb73ac'
                    or source.get('architecture')!='x86'):
                raise ValueError('Win32 requires a current digest-pinned native codec, not the obsolete wheel')
        if target.startswith('linux-') and data.get('minimum_glibc') != '2.39':
            raise ValueError('Linux preview must declare the conservative glibc2.39 build baseline')
        proof = folder / 'test-results.xml'
        if proof.is_symlink() or not proof.is_file() or proof.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('Missing/bounded native JUnit proof')
        if tuple(map(int,version.split('.'))) >= (0,10,1):
            verify_tests(proof,120,PARITY_CLASSES)
        else:
            verify_tests(proof)
        expected = {f'Dkord-desktop-v{version}-{target}.{kind}': kind for kind in KINDS[target]}
        entries = data.get('artifacts')
        if not isinstance(entries, list) or len(entries) != len(expected):
            raise ValueError('Incomplete native packages')
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {'name', 'bytes', 'sha256'}:
                raise ValueError('Unexpected package metadata')
            name = entry['name']
            if not isinstance(name, str) or name not in expected or name in seen:
                raise ValueError('Unexpected/duplicate/traversal package name')
            seen.add(name)
            path = folder / name
            if path.is_symlink() or not path.is_file() or type(entry['bytes']) is not int or not 0 < entry['bytes'] < 2 * 1024**3:
                raise ValueError('Missing/invalid native package')
            if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
                raise ValueError('Native package byte count/hash mismatch')
            verify_magic(path, target, expected[name])
            checked.append(path)
        allowed = set(expected) | {manifest.name, proof.name}
        if any(p.is_symlink() or not p.is_file() or p.name not in allowed for p in folder.iterdir()):
            raise ValueError('Unexpected file/directory in native artifact')
        checked.append(manifest)
    output.mkdir(parents=True, exist_ok=True)
    for path in checked:
        shutil.copyfile(path, output / path.name)
    return sorted(output.iterdir())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    paths = verify_and_stage(args.root, args.output, args.sha, args.version)
    minimum=120 if tuple(map(int,args.version.split('.'))) >= (0,10,1) else 36
    print(f'::notice title=Native build release proof::{len(paths)} native files verified for {args.sha}: all6 targets, hashes, formats and actual minimum {minimum}-case proof. Build-stage artifacts require separate owner manifest attestation; no OS signing/notarization is claimed.')

if __name__ == '__main__':
    main()
