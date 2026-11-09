"""Synthetic PNG/schema/transport fixtures only; real native pixels require GUI CI."""
import base64
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'desktop'))
spec = importlib.util.spec_from_file_location('gallery_proof', ROOT / 'desktop/packaging/gallery_proof.py')
gallery = importlib.util.module_from_spec(spec); spec.loader.exec_module(gallery)
from dkord_desktop.gallery_contract import SCREENS
import gallery_transport as transport


def png():
    def block(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + block(b'IHDR', struct.pack('>IIBBBBB', 400, 300, 8, 2, 0, 0, 0))
            + block(b'IDAT', zlib.compress((b'\0' + b'\0' * 1200) * 300)) + block(b'IEND', b''))


class NativeGalleryGuardTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.inputs = self.root / 'inputs'; self.output = self.root / 'output'
        self.source = '7' * 40
        for target in gallery.TARGETS:
            folder = self.inputs / ('desktop-gallery-' + target); folder.mkdir(parents=True)
            data = png(); records = []
            for screen in SCREENS:
                (folder / (screen + '.png')).write_bytes(data)
                records.append(dict(id=screen, name=screen+'.png', title='SYNTHETIC UNIT FIXTURE ONLY', bytes=len(data),
                                    sha256=hashlib.sha256(data).hexdigest(), width=400, height=300, data='OFFLINE DEMO UNIT FIXTURE'))
            x86 = target == 'windows-x86'
            proof = dict(format=1, application='Dkord', version=gallery.__version__, source=self.source, platform=target,
                         os='Windows' if target.startswith('windows') else 'Darwin' if target.startswith('macos') else 'Linux',
                         python_bits=32 if x86 else 64, qt_binding='PyQt5' if x86 else 'PyQt6', qt_version='5.15.2' if x86 else '6.10.2',
                         frozen=True, liveProviderTested=False, heardAudioTested=False, userDataAccessed=False,
                         data='OFFLINE DEMO UNIT FIXTURE; NOT REAL SCREENSHOTS', images=records)
            (folder / 'gallery-proof.json').write_text(json.dumps(proof))
        self.folder = self.inputs / 'desktop-gallery-windows-x86'
        self.proof = json.loads((self.folder / 'gallery-proof.json').read_text())

    def verify(self, proof):
        (self.folder / 'gallery-proof.json').write_text(json.dumps(proof))
        return gallery.verify(self.folder, self.source, 'windows-x86')

    def bundle(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return gallery.bundle(self.inputs, self.output, self.source)

    def test_all_six_profiles_and_thirty_screen_ids_are_required_in_original_zip_and_viewer(self):
        archive = self.bundle()
        with zipfile.ZipFile(archive) as zip:
            self.assertEqual(188, len(zip.namelist()))
            manifest = json.loads(zip.read('gallery-manifest.json')); self.assertEqual(180, manifest['screenCount'])
            self.assertEqual(set(gallery.TARGETS), set(manifest['targets']))
            self.assertIn('OFFLINE DEMO', zip.read('index.html').decode())
        self.assertEqual(30, len(SCREENS))
        original = archive.read_bytes()
        with self.assertRaises(FileExistsError): self.bundle()
        self.assertEqual(original, archive.read_bytes())

    def test_wrong_source_bitness_binding_frozen_or_fixture_claims_cannot_pass(self):
        for key, value in (('source','8'*40), ('python_bits',64), ('qt_binding','PyQt6'), ('qt_version','6.10.2'),
                           ('frozen',False), ('liveProviderTested',True), ('heardAudioTested',True), ('userDataAccessed',True), ('data','live successful results')):
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify(self.proof | {key:value})

    def test_missing_duplicate_traversal_corrupt_or_dimension_mismatched_pngs_are_refused(self):
        for field, value in (('name','../outside.png'), ('sha256','0'*64), ('width',500), ('bytes',1), ('data','not labelled')):
            proof = copy.deepcopy(self.proof); proof['images'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.verify(proof)
        proof = copy.deepcopy(self.proof); proof['images'][0] = proof['images'][1]
        with self.assertRaises(ValueError): self.verify(proof)
        proof = copy.deepcopy(self.proof); proof['images'].pop()
        with self.assertRaises(ValueError): self.verify(proof)

    def test_missing_target_or_unexpected_file_cannot_be_promoted(self):
        (self.folder / 'unapproved.txt').write_text('not a screenshot')
        with self.assertRaises(ValueError): self.bundle()
        (self.folder / 'unapproved.txt').unlink(); (self.folder / '01-home.png').unlink()
        with self.assertRaises(ValueError): self.bundle()

    def test_transport_reconstructs_original_zip_with_bounded_messages_and_no_loss(self):
        archive = self.bundle(); folder = self.root / 'transport'
        receipt = transport.plan(archive, folder, self.source); recovered = []
        for part in receipt['parts']:
            lines = []
            for batch in range(6):
                out = io.StringIO()
                with contextlib.redirect_stdout(out): transport.emit(folder, part['index'], batch)
                messages = out.getvalue().splitlines(); self.assertLessEqual(len(messages),8)
                self.assertTrue(all(len(line)<4096 for line in messages)); lines.extend(messages)
            chunks = [line.split('::',2)[2] for line in lines if 'title=Dkord gallery chunk '+str(part['index'])+' part ' in line]
            recovered.append(base64.b64decode(''.join(chunks)))
        self.assertEqual(archive.read_bytes(), b''.join(recovered))
        self.assertEqual(hashlib.sha256(b''.join(recovered)).hexdigest(), receipt['sha256'])

    def test_transport_refuses_tampered_chunk_wrong_source_or_existing_destination(self):
        archive = self.bundle(); folder = self.root / 'transport'
        with self.assertRaises(ValueError): transport.plan(archive, folder, '8'*40)
        receipt = transport.plan(archive, folder, self.source)
        with self.assertRaises(FileExistsError): transport.plan(archive, folder, self.source)
        (folder / receipt['parts'][0]['name']).write_bytes(b'changed')
        with self.assertRaises(ValueError): transport.emit(folder, 0, 0)

    def test_signed_release_requires_fresh_gallery_baseline_and_no_historical_route_reuse(self):
        workflow = (ROOT / '.github/workflows/release-v0102.yml').read_text()
        for requirement in ('v0.10.2.json', 'CODE', 'gallery_proof.py', 'v0.10.1', '--target-code 16', 'desktop-gallery-*', 'test "${#assets[@]}" -eq 22'):
            if requirement == 'CODE': continue
            self.assertIn(requirement, workflow)
        self.assertLess(workflow.index('gallery_proof.py'), workflow.index('gh release create'))
        self.assertLess(workflow.index('verify_android_install_over.py'), workflow.index('gh release create'))
        self.assertNotIn('continue-on-error', workflow)
        cli = (ROOT / 'desktop/dkord_desktop/__main__.py').read_text()
        self.assertIn('if args.capture_gallery:', cli)
        self.assertLess(cli.index('if args.capture_gallery:'), cli.index('root=args.data_dir'))


if __name__ == '__main__': unittest.main()
