"""Offline exact-link metadata contracts; no claim of live provider/audio acceptance."""
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from dkord_desktop.media import Cancelled
from dkord_desktop.provider import Provider
from dkord_desktop.youtube_links import (MAX_LINK_LENGTH, PROBLEM_KEYS, YouTubeLinkError,
                                         parse_youtube_link, link_track, extraction_problem)


class YouTubeLinkTest(unittest.TestCase):
    def setUp(self):
        self.link = parse_youtube_link('https://youtu.be/AbCdEf012_-?si=share&list=not-a-queue')
        self.info = {'id': self.link.video_id, 'title': 'Rare upload — audio flip (offline fixture)',
                     'uploader': 'Original uploader', 'duration': 19}

    def test_the_same_75_android_vectors_define_native_link_identity_and_invalid_input(self):
        path = Path(__file__).resolve().parents[2] / 'app/src/test/resources/youtube-links.json'
        vectors = json.loads(path.read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(vectors['valid']), 29); self.assertGreaterEqual(len(vectors['invalid']), 46)
        for item in vectors['valid']:
            with self.subTest(input=item['input']):
                link = parse_youtube_link(item['input'])
                self.assertEqual(item['id'], link.video_id)
                self.assertEqual('https://www.youtube.com/watch?v=' + item['id'], link.url)
        for item in vectors['invalid']:
            with self.subTest(input=item['input']):
                with self.assertRaises(YouTubeLinkError) as caught:
                    parse_youtube_link(item['input'])
                self.assertEqual(item['problem'], caught.exception.problem)
                self.assertNotIn('http', str(caught.exception))

    def test_length_limit_never_truncates_into_a_different_valid_request(self):
        prefix = 'https://youtu.be/AbCdEf012_-?si='
        value = prefix + 'x' * (MAX_LINK_LENGTH - len(prefix))
        self.assertEqual(self.link, parse_youtube_link(value))
        with self.assertRaises(YouTubeLinkError): parse_youtube_link(value + 'x')

    def test_video_playlist_and_timestamp_context_is_discarded_not_queued_or_forwarded(self):
        link = parse_youtube_link('https://music.youtube.com/watch?v=AbCdEf012_-&list=RDAMVMother&index=9&t=40')
        self.assertEqual(self.link.url, link.url); self.assertNotIn('list=', link.url); self.assertNotIn('t=', link.url)

    def test_direct_provider_extraction_receives_only_the_canonical_video_id_not_a_search_or_download(self):
        with patch('dkord_desktop.provider.YoutubeDL') as constructor, patch.object(Provider, 'search') as search, patch.object(Provider, 'music') as music:
            extractor = constructor.return_value.__enter__.return_value
            extractor.extract_info.return_value = self.info
            track = Provider().open_youtube_link(self.link, threading.Event())
            extractor.extract_info.assert_called_once_with(self.link.url, download=False)
            search.assert_not_called(); music.assert_not_called()
            options = constructor.call_args.args[0]
            self.assertIs(True, options['noplaylist']); self.assertIs(True, options['skip_download'])
            for key in ('cookiefile', 'cookiesfrombrowser', 'username', 'password'):
                self.assertNotIn(key, options)
        self.assertEqual(self.link.video_id, track.id); self.assertEqual(self.info['title'], track.title)
        self.assertEqual('Original uploader', track.artist); self.assertEqual(19, track.durationSec)

    def test_short_long_non_music_and_unknown_duration_uploads_are_manual_choices_not_radio_candidates(self):
        for duration in (0, 2, 7200):
            with self.subTest(duration=duration):
                info = {**self.info, 'duration': duration, 'categories': ['People & Blogs'], 'uploader': ''}
                track = link_track(self.link, info)
                self.assertEqual(duration, track.durationSec); self.assertEqual('', track.artist)

    def test_mismatched_or_empty_metadata_never_becomes_a_substitute_result(self):
        for extra in ({'id': 'ZyXwVu987_-'}, {'title': ''}, {'title': None}, {'_type': 'playlist'}, {'duration': -1},
                      {'duration': float('nan')}, {'duration': float('inf')}, {'duration': 10**500}, {'duration': True}):
            with self.subTest(extra=extra), self.assertRaises(YouTubeLinkError):
                link_track(self.link, {**self.info, **extra})
        for value in (None, {}, {'entries': [self.info]}):
            with self.assertRaises(YouTubeLinkError): link_track(self.link, value)

    def test_private_members_only_and_not_yet_started_videos_are_not_reported_as_playable_previews(self):
        for extra, expected in (({'availability': 'private'}, 'private'), ({'availability': 'premium_only'}, 'unavailable'),
                                ({'availability': 'subscriber_only'}, 'unavailable'), ({'live_status': 'is_upcoming'}, 'unavailable')):
            with self.subTest(extra=extra), self.assertRaises(YouTubeLinkError) as caught:
                link_track(self.link, {**self.info, **extra})
            self.assertEqual(expected, caught.exception.problem)

    def test_provider_restrictions_and_transport_errors_are_localizable_without_raw_urls(self):
        reasons = (
            ('This is a private video', 'private'), ('Sign in to confirm your age', 'age_restricted'),
            ('Video not available in your country', 'geo'), ('Sign in to confirm you are not a bot', 'bot_check'),
            ('HTTP Error 429: Too many requests', 'bot_check'), ('No video formats found', 'no_audio'),
            ('Unable to download webpage: connection timed out', 'network'), ('Video unavailable (deleted)', 'unavailable'),
        )
        for message, expected in reasons:
            with self.subTest(message=message), patch('dkord_desktop.provider.YoutubeDL') as constructor:
                constructor.return_value.__enter__.return_value.extract_info.side_effect = RuntimeError(message + ' https://provider.test/?token=secret')
                with self.assertRaises(YouTubeLinkError) as caught:
                    Provider().open_youtube_link(self.link, threading.Event())
                self.assertEqual(expected, caught.exception.problem)
                self.assertNotIn('secret', str(caught.exception)); self.assertNotIn('https', str(caught.exception))
        self.assertEqual('network', extraction_problem(OSError('offline')))

    def test_raw_strings_cannot_skip_validation_and_enter_the_provider(self):
        with patch('dkord_desktop.provider.YoutubeDL') as constructor, self.assertRaises(YouTubeLinkError):
            Provider().open_youtube_link('https://untrusted.test/never-fetched')
        constructor.assert_not_called()

    def test_cancellation_before_and_after_extraction_does_not_return_a_stale_preview(self):
        cancel = threading.Event(); cancel.set()
        with patch('dkord_desktop.provider.YoutubeDL') as constructor, self.assertRaises(Cancelled):
            Provider().open_youtube_link(self.link, cancel)
        constructor.assert_not_called(); cancel.clear()
        with patch('dkord_desktop.provider.YoutubeDL') as constructor:
            def delayed(url, download):
                cancel.set(); return self.info
            constructor.return_value.__enter__.return_value.extract_info.side_effect = delayed
            with self.assertRaises(Cancelled): Provider().open_youtube_link(self.link, cancel)

    def test_every_native_reason_uses_the_phone_owned_english_and_hindi_resource(self):
        from dkord_desktop.experience import contract, text
        for key in PROBLEM_KEYS.values():
            for language in ('en', 'hi'):
                self.assertIn(key, contract()['strings'][language]); self.assertTrue(text(key, language))
        self.assertNotEqual(text('youtube_link_open', 'en'), text('youtube_link_open', 'hi'))


if __name__ == '__main__':
    unittest.main()
