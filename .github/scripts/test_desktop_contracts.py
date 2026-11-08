"""Read-only desktop source/build contracts, not a substitute for 5-host native execution."""
import json
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[2]
def read(path):return (ROOT/path).read_text()
class DesktopContractsTest(unittest.TestCase):
    def test_native_validation_covers_all_os_and_cpu_builds_without_publication_or_secrets(self):
        flow=read('.github/workflows/validate-desktop.yml')
        for target in ('windows-x64','macos-x64','macos-arm64','linux-x64','linux-arm64'):self.assertIn('target: '+target,flow)
        for required in ('contents: read','--self-test','packaging/build.py','no failures/errors/skips','assert len(cases) >= 26'):
            self.assertIn(required,flow)
        for forbidden in ('secrets.','contents: write','gh release','continue-on-error'):self.assertNotIn(forbidden,flow)
    def test_desktop_has_real_native_widgets_codec_renderer_and_no_mock_browser(self):
        gui=read('desktop/dkord_desktop/ui.py');media=read('desktop/dkord_desktop/media.py')
        for required in ('QMainWindow','QMediaPlayer','QAudioOutput','QTableWidget','QDockWidget'):self.assertIn(required,gui)
        for required in ('av.open','imageio_ffmpeg.get_ffmpeg_exe','subprocess.Popen','-filter_complex','aresample=48000','-c:a'):
            self.assertIn(required,media)
        self.assertNotIn('QWebEngineView',gui)
        self.assertIn('test_actual_ffmpeg_merges_mixed_rate_clips_in_order',read('desktop/tests/test_core.py'))
    def test_updates_are_disjoint_from_android_pinned_signed_and_platform_matched(self):
        source=read('desktop/dkord_desktop/updates.py')
        for required in ('Ed25519PublicKey','key.verify','desktop-v','artifact["sha256"]','platform_key()','Package content is not the expected native installer type'):
            self.assertIn(required,source)
        self.assertNotIn('/releases/latest',source)
        self.assertEqual({},json.loads(read('desktop/assets/update-keys.json')))
        self.assertIn('not yet a finished Android-parity',read('desktop/README.md'))
    def test_stable_user_data_is_outside_installation_and_uninstall_has_no_data_delete(self):
        entry=read('desktop/dkord_desktop/__main__.py');installer=read('desktop/packaging/windows.iss')
        self.assertIn('user_data_path("Dkord","Dkord",roaming=False)',entry)
        self.assertIn('AppId=app.dkord.desktop',installer)
        self.assertNotIn('[UninstallDelete]',installer)
        self.assertNotIn('fallbackToDestructiveMigration',read('app/src/main/java/app/dkord/data/db/AppDatabase.kt'))
    def test_desktop_and_android_unpublished_version_agree_without_replaying_releases(self):
        gradle=read('app/build.gradle.kts');desktop=read('desktop/dkord_desktop/__init__.py')
        self.assertEqual(re.search(r'versionName = "([^"]+)"',gradle)[1],re.search(r'__version__ = "([^"]+)"',desktop)[1])
        self.assertIn('branches: [arena/59a2f745-dkord]',read('.github/workflows/release.yml'))
        self.assertNotIn('release',read('desktop/packaging/windows.iss').split('[Files]')[1].split('[Icons]')[0].lower())
if __name__=='__main__':unittest.main()
