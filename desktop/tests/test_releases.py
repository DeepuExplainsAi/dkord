import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dkord_desktop.models import Track
from dkord_desktop.media import Cancelled
from dkord_desktop.catalogue import Page,Shelf
from dkord_desktop.provider import Entry
from dkord_desktop.releases import (NewReleasesRepository,ReleaseDatesUnavailable,release_queries,
    releases_in_window,iso_date,published_at,WINDOWS,MAX_PAGE)


def track(index):return Track(f'{index:011d}',f'Song {index}','Artist')
NOW=iso_date('2026-11-07T12:00:00Z')


class NewReleasesTest(unittest.TestCase):
    def test_exact_elapsed_boundaries_unknown_future_and_old_dates_are_not_releases(self):
        for window,duration in WINDOWS.items():
            candidates=[(track(1),NOW),(track(2),NOW-duration),(track(3),NOW-duration-1),
                        (track(4),NOW+1),(track(5),None),(track(6),0),(track(7),-1),(track(8),True)]
            self.assertEqual([track(1),track(2)],releases_in_window(candidates,window,NOW))

    def test_newest_first_dedup_retains_most_recent_date_not_source_order(self):
        self.assertEqual([track(2),track(1)],releases_in_window([(track(1),NOW-200),(track(2),NOW-1),(track(1),NOW-100)],'LAST_7_DAYS',NOW))

    def test_phone_queries_have_exact_utc_dates_and_no_choliwood_display_rewrite(self):
        self.assertEqual(['new english songs November 2026 after:2026-10-28','new hindi songs November 2026 after:2026-10-28',
            'new bhojpuri songs November 2026 after:2026-10-28','new punjabi songs November 2026 after:2026-10-28'],release_queries('ALL',NOW))
        self.assertEqual(['new bhojpuri songs November 2026','latest bhojpuri songs after:2026-10-28','new bhojpuri songs this week November 2026'],release_queries('CHOLIWOOD',NOW))
        self.assertIn('after:2025-12-22',release_queries('TAMIL',iso_date('2026-01-01'))[1])

    def test_iso_dates_are_utc_and_timezone_offsets_are_respected_not_local_calendar_guesses(self):
        self.assertEqual(iso_date('2026-11-07T00:00:00Z'),iso_date('2026-11-07'))
        self.assertEqual(iso_date('2026-11-07T00:00:00Z'),iso_date('2026-11-07T05:30:00+05:30'))
        for value in (None,'today','2026-02-30','2026-11-07T00:00:00'):
            self.assertIsNone(iso_date(value))

    def test_publication_metadata_priority_matches_phone_not_recommendation_or_description_dates(self):
        html='''<script>{"recommendations":{"publishDate":"2026-11-07"},"playerMicroformatRenderer":{"publishDate":"2026-11-06","uploadDate":"2026-01-01","description":{"simpleText":"a } and \\\"quote\\\""}}}</script><meta itemprop="datePublished" content="2026-11-05">'''
        self.assertEqual(iso_date('2026-11-06'),published_at(html))
        self.assertEqual(iso_date('2026-11-05'),published_at('<META CONTENT="2026-11-05" ITEMPROP="datePublished"><meta itemprop="uploadDate" content="2026-01-01">'))
        self.assertIsNone(published_at('{"recommendations":{"publishDate":"2026-11-07"}}'))

    def test_upload_date_and_video_release_date_fallbacks_and_bounded_malformed_pages(self):
        self.assertEqual(iso_date('2026-11-04'),published_at('<meta property="video:release_date" content="2026-11-04"><meta itemprop="uploadDate" content="2026-01-01">'))
        self.assertEqual(iso_date('2026-11-03'),published_at('{"playerMicroformatRenderer":{"uploadDate":"2026-11-03"}}'))
        self.assertIsNone(published_at('x'*(MAX_PAGE+1)))
        self.assertIsNone(published_at('{"playerMicroformatRenderer":{"publishDate":"tomorrow"'))

    def repository(self,sources=None,dates=None):
        self.clock={'elapsed':0};self.calls=[]
        def source(category,cancel):self.calls.append(category);return [track(1)]
        return NewReleasesRepository(sources or [source],dates or (lambda t,c:NOW),now=lambda:NOW,elapsed=lambda:self.clock['elapsed'])

    def test_switching_window_reuses_verified_dates_but_switching_category_does_not(self):
        repo=self.repository();self.assertEqual([track(1)],repo.songs())
        repo.songs('LAST_24_HOURS');repo.songs('LAST_10_DAYS')
        self.assertEqual(['ALL'],self.calls)
        repo.songs(category='CHOLIWOOD');repo.songs(category='ALL')
        self.assertEqual(['ALL','CHOLIWOOD'],self.calls)

    def test_nonempty_cache_has_exact_thirty_minute_boundary_and_refresh_is_explicit(self):
        repo=self.repository();repo.songs();self.clock['elapsed']=1_799_999;repo.songs();self.assertEqual(1,len(self.calls))
        self.clock['elapsed']=1_800_000;repo.songs();self.assertEqual(2,len(self.calls))
        repo.songs(refresh=True);self.assertEqual(3,len(self.calls))
        self.clock['elapsed']=-1;repo.songs();self.assertEqual(4,len(self.calls))

    def test_verified_empty_cache_expires_after_one_minute_not_thirty(self):
        calls=[]
        def source(category,cancel):calls.append(category);return []
        repo=self.repository([source]);self.assertEqual([],repo.songs())
        self.clock['elapsed']=59_999;repo.songs();self.assertEqual(1,len(calls))
        self.clock['elapsed']=60_000;repo.songs();self.assertEqual(2,len(calls))

    def test_missing_date_metadata_is_an_error_never_a_cached_no_releases_result(self):
        repo=self.repository(dates=lambda t,c:None)
        with self.assertRaises(ReleaseDatesUnavailable):repo.songs()
        self.assertEqual({},repo.cache)
        repo.dates=lambda t,c:NOW;self.assertEqual([track(1)],repo.songs());self.assertEqual(2,len(self.calls))

    def test_one_date_failure_does_not_erase_other_verified_releases(self):
        def dates(t,c):
            if t.id==track(1).id:raise OSError('metadata unavailable')
            return NOW
        repo=self.repository([lambda cat,c:[track(1),track(2)]],dates)
        self.assertEqual([track(2)],repo.songs())

    def test_all_sources_failed_and_partial_failure_without_candidates_are_not_empty_success(self):
        def fail(category,cancel):raise OSError('source unavailable')
        for sources in ([fail,fail],[fail,lambda cat,c:[]]):
            repo=self.repository(sources)
            with self.assertRaisesRegex(ValueError,'sources unavailable'):repo.songs()
        repo=self.repository([fail,lambda cat,c:[track(2)]])
        self.assertEqual([track(2)],repo.songs())

    def test_forty_candidates_are_interleaved_across_sources_before_dating(self):
        sources=[lambda category,cancel,source=source:[track(source*100+index) for index in range(30)] for source in range(5)]
        repo=self.repository(sources)
        expected=[track(source*100+index) for index in range(8) for source in range(5)]
        self.assertEqual(expected,repo.songs());self.assertEqual(40,len(repo.cache['ALL'][1]))

    def test_metadata_parallelism_is_bounded_to_six(self):
        state={'active':0,'peak':0};lock=threading.Lock()
        def dates(t,c):
            with lock:state['active']+=1;state['peak']=max(state['peak'],state['active'])
            time.sleep(.01)
            with lock:state['active']-=1
            return NOW
        repo=self.repository([lambda cat,c:[track(i) for i in range(24)]],dates)
        self.assertEqual(24,len(repo.songs()));self.assertLessEqual(state['peak'],6);self.assertGreater(state['peak'],1)

    def test_future_and_over_ten_day_dates_are_verified_but_not_shown_as_new(self):
        repo=self.repository([lambda cat,c:[track(1),track(2)]],lambda t,c:NOW+1 if t.id==track(1).id else NOW-WINDOWS['LAST_10_DAYS']-1)
        self.assertEqual([],repo.songs());self.assertEqual([],repo.cache['ALL'][1])

    def test_cancel_before_work_does_not_contact_any_source_or_mutate_cache(self):
        repo=self.repository();cancel=threading.Event();cancel.set()
        with self.assertRaises(Cancelled):repo.songs(cancel=cancel)
        self.assertEqual([],self.calls);self.assertEqual({},repo.cache)
        for args in ({'category':'Bhojpuri'},{'window':'This week'}):
            with self.assertRaises(ValueError):repo.songs(**args)

    def test_album_discovery_expands_at_most_four_music_albums_not_regular_video_search(self):
        class Provider:
            def __init__(self):self.loaded=[];self.searches=[]
            def catalogue_page(self,entry=None,browse_id=None):
                if browse_id:
                    albums=tuple(Entry('album',f'album{i}',f'Album {i}') for i in range(8))
                    return Page(tracks=(track(99),),shelves=(Shelf('',albums),))
                self.loaded.append(entry.id);return Page(tracks=(track(int(entry.id[5:])),))
            def search(self,query,scope,limit):self.searches.append((query,scope,limit));return []
        provider=Provider();repo=NewReleasesRepository.from_provider(provider);repo.dates=lambda t,c:NOW;repo.now=lambda:NOW
        self.assertEqual([track(99)]+[track(i) for i in range(4)],repo.songs())
        self.assertEqual({f'album{i}' for i in range(4)},set(provider.loaded))
        self.assertTrue(all(scope=='Songs' for _,scope,_ in provider.searches))
        self.assertEqual(4,len(provider.searches))

    def test_category_uses_music_album_query_and_never_reuses_all_category_browse(self):
        class Provider:
            def __init__(self):self.searches=[]
            def catalogue_page(self,*args,**kwargs):raise AssertionError('Category cannot reuse generic release browse')
            def search(self,query,scope,limit):
                self.searches.append((query,scope));return [Entry('song',track(1).id,'Song','Artist',track(1))] if scope=='Songs' else []
        provider=Provider();repo=NewReleasesRepository.from_provider(provider);repo.dates=lambda t,c:NOW;repo.now=lambda:NOW
        self.assertEqual([track(1)],repo.songs(category='CHOLIWOOD'))
        self.assertEqual(4,len(provider.searches));self.assertTrue(all('bhojpuri' in query for query,_ in provider.searches))
        self.assertTrue(any('albums' in query and scope=='Albums' for query,scope in provider.searches))


if __name__=='__main__':unittest.main()
