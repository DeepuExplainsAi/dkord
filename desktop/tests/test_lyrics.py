from contextlib import contextmanager
import json
import threading
import unittest
from dkord_desktop.lyrics import LyricsRepository, LyricLine, parse_lrc, index_at, clean_title
from dkord_desktop.models import Track


class LyricsTest(unittest.TestCase):
    def test_android_lrc_fraction_repeated_stamp_sort_and_rightmost_highlight(self):
        lines = parse_lrc('[01:02.4][00:01.01]पहली पंक्ति\n[00:00.123]Start\n[00:01.010]Same time\n[ar:Artist]')
        self.assertEqual([123, 1010, 1010, 62400], [line.time_ms for line in lines])
        self.assertEqual('पहली पंक्ति', lines[1].text)
        self.assertEqual(-1, index_at(lines, 0)); self.assertEqual(2, index_at(lines, 1010)); self.assertEqual(3, index_at(lines, 90000))
        self.assertEqual((), parse_lrc('plain lyrics only'))

    def test_phone_title_cleaning_preserves_actual_song_identity(self):
        self.assertEqual('संगवारी', clean_title('संगवारी (Official Audio) [4K Video]'))
        self.assertEqual('Original Remix', clean_title('Original Remix'))

    def service(self, payloads):
        calls = []
        class Response:
            status_code = 200
            def __init__(self, payload): self.payload = payload
            def raise_for_status(self): pass
            def iter_content(self, size): yield json.dumps(self.payload).encode()
            def __enter__(self): return self
            def __exit__(self, *args): pass
        def get(url, **kwargs):
            calls.append((url, kwargs)); return Response(payloads[len(calls)-1])
        return LyricsRepository(get), calls

    def test_real_metadata_request_exact_lyrics_cache_and_no_embedded_timestamp_text(self):
        repository, calls = self.service([dict(syncedLyrics='[00:01.23]Hello', plainLyrics='Hello')])
        track = Track('abcdefghijk', 'Song (Official Audio)', 'Singer - Topic', 'Album', 210)
        result = repository.load(track)
        self.assertEqual((LyricLine(1230, 'Hello'),), result.synced)
        self.assertEqual('Singer', calls[0][1]['params']['artist_name']); self.assertEqual('Song', calls[0][1]['params']['track_name'])
        self.assertIs(result, repository.load(track)); self.assertEqual(1, len(calls))

    def test_missing_exact_lyrics_falls_back_to_synced_search_not_random_plain_text(self):
        repository, calls = self.service([{}, [dict(plainLyrics='Wrong plain'), dict(syncedLyrics='[00:02]Found')]])
        self.assertEqual('Found', repository.load(Track('abcdefghijk', 'Song', 'Artist')).synced[0].text)
        self.assertEqual('https://lrclib.net/api/search', calls[-1][0])

    def test_private_local_audio_and_cancelled_requests_do_not_call_provider(self):
        repository, calls = self.service([])
        self.assertIsNone(repository.load(Track('studio:00000000-0000-0000-0000-000000000001', 'Private', 'Me')))
        cancel = threading.Event(); cancel.set()
        self.assertIsNone(repository.load(Track('abcdefghijk', 'Song', 'Artist'), cancel))
        self.assertEqual([], calls)

    def test_plain_lyrics_remain_plain_and_empty_result_has_no_fake_lines(self):
        repository, calls = self.service([dict(plainLyrics='First\nSecond')])
        result = repository.load(Track('abcdefghijk', 'Song', 'Artist'))
        self.assertEqual((), result.synced); self.assertEqual('First\nSecond', result.plain)
        self.assertEqual(1, len(calls))
