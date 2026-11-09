"""Offline orchestration/guard fixtures; actual install-over needs emulator CI."""
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch,Mock
import verify_android_install_over as upgrade

class AndroidInstallOverGuardTest(unittest.TestCase):
    def test_installed_version_and_uid_require_actual_package_metadata(self):
        with patch.object(upgrade,'command',side_effect=['userId=10123\nversionCode=14 minSdk=26','package:app.dkord uid:10123\n']) as command:
            self.assertEqual((14,10123),upgrade.package())
        self.assertEqual(('shell','cmd','package','list','packages','-U','--user','0','app.dkord'),command.call_args_list[1].args)
        with patch.object(upgrade,'command',return_value='unavailable'),patch('builtins.print'),self.assertRaises(ValueError):upgrade.package()
    def test_current_android_appid_label_uses_real_owner_package_uid_not_dump_display_label(self):
        dump='Packages:\n  Package [app.dkord] (abc):\n    appId=10123\n    versionCode=14 minSdk=26\n'
        with patch.object(upgrade,'command',side_effect=[dump,'package:app.dkord.test uid:10124\npackage:app.dkord uid:10123\n']):
            self.assertEqual((14,10123),upgrade.package())
    def test_wrong_missing_zero_or_ambiguous_package_uid_is_refused_without_fallback(self):
        dump='userId=10123\nappId=10123\nversionCode=14'
        for listing in ('','package:app.dkord.test uid:10123\n','package:app.dkord uid:0\n',
                        'package:app.dkord uid:10123\npackage:app.dkord uid:10124\n'):
            with self.subTest(listing=listing),patch.object(upgrade,'command',side_effect=[dump,listing]) as command,patch('builtins.print'),self.assertRaises(ValueError):
                upgrade.package()
            self.assertEqual(2,command.call_count)
    def test_adb_failure_is_bounded_visible_and_raised_without_command_retry(self):
        failure=subprocess.CalledProcessError(1,['adb','install'],output='Failure [INSTALL_FAILED_TEST_ONLY]\n'+('x'*16000),stderr='synthetic fixture stderr')
        with patch.object(upgrade.subprocess,'run',side_effect=failure) as run,patch('builtins.print') as output,self.assertRaises(subprocess.CalledProcessError):
            upgrade.command('install','-r','-t','synthetic-fixture.apk')
        run.assert_called_once()
        self.assertEqual(4,output.call_count)
        messages=[call.args[0] for call in output.call_args_list]
        self.assertTrue(all(text.startswith('::error title=Android install-over adb failure part ') and len(text)<4096 for text in messages))
        self.assertIn('synthetic fixture stderr',messages[-1])
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
                    code,uid=metadata.pop(0);return f'versionCode={code} appId={uid}'
                if args==('shell','cmd','package','list','packages','-U','--user','0','app.dkord'):
                    return 'package:app.dkord.test uid:10124\npackage:app.dkord uid:10123\n'
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
    def test_changed_actual_uid_or_wrong_version_cannot_write_a_success_receipt_or_run_verify_phase(self):
        for new_metadata in ((15,10124),(14,10123)):
            with self.subTest(new_metadata=new_metadata),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);old=root/'synthetic.apk';old.write_bytes(b'SYNTHETIC TEST ONLY; NOT AN APK');output=root/'receipt.json'
                fake=Mock();fake.hexdigest.return_value='d2a354903e3eda3707aab77721a391ee0eee3134010284e7ffd1a3e28f2deed9'
                env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'DeepuExplainsAi/dkord','GITHUB_SHA':'7'*40}
                with patch.dict(os.environ,env),patch.object(upgrade,'command',return_value='1') as command,patch.object(upgrade,'package',side_effect=[(14,10123),new_metadata]),patch.object(upgrade,'phase') as phase,patch.object(upgrade.hashlib,'sha256',return_value=fake),self.assertRaises(ValueError):
                    upgrade.verify(old,root/'new.apk',root/'test.apk',output)
                self.assertFalse(output.exists());phase.assert_called_once_with('seed')
                self.assertFalse(any('uninstall' in call.args or 'clear' in call.args for call in command.call_args_list))
    def test_release_requires_real_upgrade_before_draft_creation_and_wipes_no_app_data(self):
        root=Path(__file__).resolve().parents[2];workflow=(root/'.github/workflows/release-v0101.yml').read_text()
        self.assertLess(workflow.index('verify_android_install_over.py'),workflow.index('gh release create'))
        self.assertLess(workflow.index('Remove the temporary keystore'),workflow.index('verify_android_install_over.py'))
        self.assertIn('android-install-over-proof.json',workflow)
        source=(root/'desktop/packaging/install_over.py').read_text()
        for text in ('desktop-v0.10.0-preview.2','--verify-upgrade-fixture','GITHUB_ACTIONS','standardUserData','--appimage-extract-and-run'):
            self.assertIn(text,source)
        self.assertNotIn('uninstall.exe',source);self.assertNotIn('dpkg -r',source)
