from datetime import datetime,timezone,timedelta
import unittest
from dkord_desktop.diagnostics import Diagnostics


class DiagnosticsTest(unittest.TestCase):
    def test_report_contains_only_known_environment_and_allowlisted_local_event_codes(self):
        diagnostics=Diagnostics(lambda:datetime(2026,11,7,12,tzinfo=timezone.utc))
        diagnostics.record('playback','prepare_failed')
        report=diagnostics.report('0.10.0','windows-x86','5.15.2 5.15.11','online')
        self.assertIn('windows-x86',report);self.assertIn('playback: prepare_failed',report)
        for private in ('github','https://','roomABC','Bearer','C:\\Users','Song title'):
            self.assertNotIn(private,report)

    def test_raw_exceptions_urls_queries_room_codes_or_paths_cannot_be_recorded(self):
        diagnostics=Diagnostics()
        for kind,code in [('playback','https://example.test/private?token=secret'),('rooms','ABCDEFGHJK'),
                          ('my private query','failed'),('background','C:\\Users\\Private\\music.wav')]:
            with self.assertRaises(ValueError):diagnostics.record(kind,code)
        self.assertEqual(0,len(diagnostics.events))

    def test_ring_buffer_is_bounded_and_not_saved_uploaded_or_auto_copied(self):
        moment=[datetime(2026,11,7,tzinfo=timezone.utc)]
        diagnostics=Diagnostics(lambda:moment[0])
        for index in range(100):
            diagnostics.record('background','failed');moment[0]+=timedelta(seconds=1)
        self.assertEqual(60,len(diagnostics.events));self.assertEqual('2026-11-07T00:00:40+00:00',diagnostics.events[0][0])
        self.assertLess(len(diagnostics.report('0.10.0','linux-x64','6.10.0','none')),6000)

    def test_private_data_cannot_be_smuggled_in_environment_and_empty_report_is_useful(self):
        diagnostics=Diagnostics();self.assertIn('No recent failures recorded.',diagnostics.report('0.10.0','macos-arm64','6.10.0','none'))
        for args in [('0.10.0','https://private.test','6.10.0','none'),('0.10.0','linux-x64','Bearer: secret','none'),
                     ('0.10.0','linux-x64','6.10.0','a private song')]:
            with self.assertRaises(ValueError):diagnostics.report(*args)


if __name__=='__main__':unittest.main()
