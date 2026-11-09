"""Offline orchestration/guard fixtures; actual install-over needs emulator CI."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import verify_android_install_over as upgrade

class AndroidInstallOverGuardTest(unittest.TestCase):
    def test_installed_version_and_uid_require_actual_package_metadata(self):
        with patch.object(upgrade,'command',return_value='userId=10123\nversionCode=14 minSdk=26'):
            self.assertEqual((14,10123),upgrade.package())
        with patch.object(upgrade,'command',return_value='unavailable'),self.assertRaises(ValueError):upgrade.package()
    def test_instrumentation_requires_one_actual_successful_case_and_success_code(self):
        for result in ('FAILURES!!!\nINSTRUMENTATION_CODE: -1','OK (1 test)\nINSTRUMENTATION_CODE: 0','OK (0 tests)\nINSTRUMENTATION_CODE: -1'):
            with patch.object(upgrade,'command',return_value=result),patch('builtins.print'),self.assertRaises(ValueError):upgrade.phase('verify')
        with patch.object(upgrade,'command',return_value='OK (1 test)\nINSTRUMENTATION_CODE: -1'),patch('builtins.print'):upgrade.phase('verify')
    def test_real_device_or_non_ci_execution_is_refused_before_any_apk_install(self):
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'false'}),patch.object(upgrade,'command') as command,self.assertRaises(ValueError):
            upgrade.verify(Path('missing-old'),Path('missing-new'),Path('missing-test'),Path('not-written'))
        command.assert_not_called()
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'DeepuExplainsAi/dkord'}),patch.object(upgrade,'command',return_value='0') as command,self.assertRaises(ValueError):
            upgrade.verify(Path('missing-old'),Path('missing-new'),Path('missing-test'),Path('not-written'))
        self.assertEqual(1,command.call_count)
    def test_actual_orchestration_preserves_uid_and_never_uses_uninstall_clear_or_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'synthetic.apk';old.write_bytes(b'SYNTHETIC TEST ONLY; NOT AN APK');output=root/'receipt.json';calls=[];metadata=[(14,10123),(15,10123)]
            def command(*args):
                calls.append(args)
                if args==('shell','getprop','ro.kernel.qemu'):return '1'
                if args==('shell','dumpsys','package','app.dkord'):
                    code,uid=metadata.pop(0);return f'versionCode={code} userId={uid}'
                if args[:3]==('shell','am','instrument'):return 'OK (1 test)\nINSTRUMENTATION_CODE: -1'
                return 'Success'
            fake=Mock();fake.hexdigest.return_value='d2a354903e3eda3707aab77721a391ee0eee3134010284e7ffd1a3e28f2deed9'
            env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'DeepuExplainsAi/dkord','GITHUB_SHA':'7'*40}
            with patch.dict(os.environ,env),patch.object(upgrade,'command',side_effect=command),patch.object(upgrade.hashlib,'sha256',return_value=fake),patch('builtins.print'):
                upgrade.verify(old,root/'new.apk',root/'test.apk',output)
            result=json.loads(output.read_text());self.assertTrue(result['sameUid']);self.assertTrue(result['noDataReset'])
            installs=[args for args in calls if args[0]=='install'];self.assertEqual(3,len(installs));self.assertTrue(all(args[1:3]==('-r','-t') for args in installs))
            self.assertEqual(2,sum(args[:3]==('shell','am','instrument') for args in calls))
            self.assertFalse(any('uninstall' in args or 'clear' in args for args in calls))
    def test_release_requires_real_upgrade_before_draft_creation_and_wipes_no_app_data(self):
        root=Path(__file__).resolve().parents[2];workflow=(root/'.github/workflows/release-v0101.yml').read_text()
        self.assertLess(workflow.index('verify_android_install_over.py'),workflow.index('gh release create'))
        self.assertLess(workflow.index('Remove the temporary keystore'),workflow.index('verify_android_install_over.py'))
        self.assertIn('android-install-over-proof.json',workflow)
        source=(root/'desktop/packaging/install_over.py').read_text()
        for text in ('desktop-v0.10.0-preview.2','--verify-upgrade-fixture','GITHUB_ACTIONS','standardUserData','--appimage-extract-and-run'):
            self.assertIn(text,source)
        self.assertNotIn('uninstall.exe',source);self.assertNotIn('dpkg -r',source)
