"""Offline tests of emulator fixture setup with a command stub, NOT Android validation."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('prepare_emulator_ime.sh')
LATIN = 'com.android.inputmethod.latin/.LatinIME'
VOICE = 'test.voice/.VoiceInputMethod'


class EmulatorImeSetupTest(unittest.TestCase):
    def run_setup(self, available, current='null', fail=None, ignore_setting=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'current').write_text(current)
            (root / 'hardware').write_text('0')
            stub = root / 'adb'
            stub.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
root=Path(os.environ['IME_TEST_ROOT'])
args=sys.argv[1:]
with (root/'calls').open('a') as out: out.write(json.dumps(args)+'\\n')
if os.environ.get('IME_FAIL') and args[:3]==json.loads(os.environ['IME_FAIL']): sys.exit(42)
if args[:3]==['shell','ime','list']: print(os.environ['IME_AVAILABLE'])
elif args==['shell','settings','get','secure','default_input_method']: print((root/'current').read_text())
elif args==['shell','settings','get','secure','show_ime_with_hard_keyboard']: print((root/'hardware').read_text())
elif args[:3]==['shell','ime','set']: (root/'current').write_text(args[3])
elif args==['shell','settings','put','secure','show_ime_with_hard_keyboard','1'] and not os.environ.get('IME_IGNORE_SETTING'): (root/'hardware').write_text('1')
''')
            stub.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                       IME_TEST_ROOT=str(root), IME_AVAILABLE=available)
            if fail:
                env['IME_FAIL'] = json.dumps(fail)
            if ignore_setting:
                env['IME_IGNORE_SETTING'] = '1'
            run = subprocess.run(['bash', str(SCRIPT)], env=env, text=True, capture_output=True)
            calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
            return run, calls

    def test_wake_unlock_and_hardware_keyboard_setting_are_applied_before_real_ime_selection(self):
        run, calls = self.run_setup(LATIN)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual(['shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'], calls[0])
        self.assertIn(['shell', 'wm', 'dismiss-keyguard'], calls)
        self.assertIn(['shell', 'settings', 'put', 'system', 'screen_off_timeout', '2147483647'], calls)
        self.assertIn(['shell', 'settings', 'put', 'secure', 'show_ime_with_hard_keyboard', '1'], calls)
        self.assertIn(['shell', 'ime', 'enable', LATIN], calls)
        self.assertIn(['shell', 'ime', 'set', LATIN], calls)

    def test_installed_real_latin_keyboard_is_selected_instead_of_a_voice_only_default(self):
        run, calls = self.run_setup(VOICE + '\r\n' + LATIN + '\r\n', current=VOICE)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertIn(['shell', 'ime', 'set', LATIN], calls)

    def test_image_without_latin_preserves_a_listed_default_never_an_invented_component(self):
        keyboard = 'test.vendor/.Keyboard'
        run, calls = self.run_setup(keyboard + '\n' + VOICE, current=keyboard)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertIn(['shell', 'ime', 'set', keyboard], calls)
        self.assertNotIn(['shell', 'ime', 'set', LATIN], calls)

    def test_missing_input_method_fails_closed_instead_of_skipping_real_ime_tests(self):
        run, calls = self.run_setup('')
        self.assertNotEqual(0, run.returncode)
        self.assertIn('No real input method', run.stderr)
        self.assertFalse(any(call[:3] == ['shell', 'ime', 'set'] for call in calls))

    def test_device_command_failure_propagates_without_masking_exit_status(self):
        run, _ = self.run_setup(LATIN, fail=['shell', 'ime', 'set'])
        self.assertEqual(42, run.returncode)

    def test_unapplied_hardware_keyboard_policy_fails_the_fixture(self):
        run, _ = self.run_setup(LATIN, ignore_setting=True)
        self.assertNotEqual(0, run.returncode)
        self.assertIn('fixture not applied', run.stderr)


if __name__ == '__main__':
    unittest.main()
