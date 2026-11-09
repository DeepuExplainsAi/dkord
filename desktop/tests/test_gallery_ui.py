"""Execute real native pages/dialogs with isolated, explicitly offline screenshot fixtures."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dkord_desktop.gallery import capture_gallery
from dkord_desktop.gallery_contract import SCREENS
from dkord_desktop.platforms import platform_key
from dkord_desktop.qt import QApplication, QImage


class NativeGalleryWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def test_all_thirty_real_pages_dialogs_and_themes_have_original_pixels_and_safe_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canary = root / 'original-user-file.wav'
            canary.write_bytes(b'KEEP original user audio; never a screenshot source')
            output = root / 'fresh-gallery'
            source = '6' * 40
            with patch.dict(os.environ, {'DKORD_SOURCE_SHA': source}):
                self.assertEqual(0, capture_gallery(self.app, output))
            proof = json.loads((output / 'gallery-proof.json').read_text())
            self.assertEqual(set(SCREENS), {item['id'] for item in proof['images']})
            self.assertEqual(30, len(proof['images']))
            self.assertFalse(proof['liveProviderTested']); self.assertFalse(proof['userDataAccessed'])
            self.assertFalse(proof['frozen']); self.assertFalse(proof['heardAudioTested'])
            for item in proof['images']:
                image = QImage(str(output / item['name']))
                self.assertFalse(image.isNull(), item['id'])
                self.assertEqual((item['width'], item['height']), (image.width(), image.height()))
                self.assertEqual(item['sha256'], hashlib.sha256((output / item['name']).read_bytes()).hexdigest())
            spec = importlib.util.spec_from_file_location('gallery_proof', Path(__file__).resolve().parents[1] / 'packaging/gallery_proof.py')
            verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
            verifier.verify(output, source, platform_key(), frozen=False)
            self.assertEqual(b'KEEP original user audio; never a screenshot source', canary.read_bytes())
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            with self.assertRaises(ValueError):
                capture_gallery(self.app, output)
            self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir()})

    def test_gallery_refuses_user_directory_file_and_symlink_before_creating_any_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); file = root / 'original.wav'; file.write_bytes(b'KEEP')
            for output in (root, file):
                with self.assertRaises(ValueError):
                    capture_gallery(self.app, output)
            self.assertEqual(b'KEEP', file.read_bytes()); self.assertEqual([file], list(root.iterdir()))


if __name__ == '__main__':
    unittest.main()
