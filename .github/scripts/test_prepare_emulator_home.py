"""Offline CI fixture checks, not executed Android HOME/keyboard acceptance."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name('prepare_emulator_home.sh')
COMPONENT = 'app.dkord.test/app.dkord.EmulatorHomeActivity'

class EmulatorHomeSetupTest(unittest.TestCase):
    def setup(self, resolved=COMPONENT, launcher=True, failure=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stub = root / 'adb'
            stub.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
root=Path(os.environ['HOME_TEST_ROOT']); args=sys.argv[1:]
with (root/'calls').open('a') as out: out.write(json.dumps(args)+'\\n')
if os.environ.get('HOME_FAIL') and args==json.loads(os.environ['HOME_FAIL']): sys.exit(42)
if args[:4]==['shell','cmd','package','resolve-activity']: print(os.environ['HOME_RESOLVED'])
elif args[:3]==['shell','pm','path'] and os.environ['HOME_LAUNCHER']=='yes': print('package:/system/launcher.apk')
''')
            stub.chmod(0o755)
            env = dict(os.environ, PATH=str(root)+os.pathsep+os.environ['PATH'], HOME_TEST_ROOT=folder,
                       HOME_RESOLVED=resolved, HOME_LAUNCHER='yes' if launcher else 'no')
            if failure: env['HOME_FAIL'] = json.dumps(failure)
            result = subprocess.run(['bash', str(SCRIPT), '--installed'], text=True, capture_output=True, env=env)
            calls = [json.loads(line) for line in (root/'calls').read_text().splitlines()]
            return result, calls

    def test_verified_test_only_home_is_set_before_old_google_launcher_is_stopped(self):
        result, calls = self.setup()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(['shell','cmd','package','set-home-activity','--user','0',COMPONENT], calls[0])
        self.assertIn('resolve-activity', calls[1])
        stop = ['shell','am','force-stop','--user','0','com.google.android.apps.nexuslauncher']
        self.assertIn(stop, calls)
        self.assertGreater(calls.index(stop), 1)
        self.assertEqual(['shell','am','start','-W','-a','android.intent.action.MAIN','-c','android.intent.category.HOME'], calls[-1])
        self.assertTrue(all('app.dkord' not in part or part == COMPONENT for call in calls for part in call))

    def test_wrong_home_fails_before_stopping_any_process_or_starting_tests(self):
        result, calls = self.setup(resolved='other.home/.Launcher')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('CI HOME fixture not applied', result.stdout)
        self.assertFalse(any('force-stop' in call for call in calls))

    def test_command_failure_is_not_ignored_and_absent_google_launcher_needs_no_stop(self):
        result, _ = self.setup(failure=['shell','cmd','package','set-home-activity','--user','0',COMPONENT])
        self.assertEqual(42, result.returncode)
        result, calls = self.setup(launcher=False)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(any('force-stop' in call for call in calls))

    def test_home_activity_is_only_in_androidtest_never_the_production_manifest(self):
        android = '{http://schemas.android.com/apk/res/android}'
        manifest = ET.parse(ROOT/'app/src/androidTest/AndroidManifest.xml').getroot()
        activity = manifest.find('application/activity')
        self.assertEqual('app.dkord.EmulatorHomeActivity', activity.get(android+'name'))
        self.assertIn('android.intent.category.HOME', [x.get(android+'name') for x in activity.findall('intent-filter/category')])
        production = (ROOT/'app/src/main/AndroidManifest.xml').read_text()
        self.assertNotIn('EmulatorHomeActivity', production)
        self.assertNotIn('android.intent.category.HOME', production)

    def test_fixture_has_no_hidden_dialogs_retries_fake_insets_or_app_data_reset(self):
        script = SCRIPT.read_text()
        for forbidden in ('hide_error_dialogs', 'KEYCODE_BACK', 'statusbar collapse', 'pm clear', 'adb uninstall', 'until ', 'while ', '|| true'):
            self.assertNotIn(forbidden, script)
        self.assertIn('set -euo pipefail', script)
        self.assertIn('./gradlew assembleDebug assembleDebugAndroidTest --stacktrace', script)
        self.assertIn('adb install -r -t', script)
        workflow = (ROOT/'.github/workflows/validate-pr.yml').read_text()
        self.assertIn('bash .github/scripts/prepare_emulator_home.sh', workflow)
        self.assertIn("bash -o pipefail -c './gradlew connectedDebugAndroidTest --stacktrace", workflow)
        self.assertIn('tee -a "$RUNNER_TEMP/dkord-device-build.log"', workflow)
        self.assertNotIn('continue-on-error', workflow)

if __name__ == '__main__':
    unittest.main()
