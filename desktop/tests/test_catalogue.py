import unittest
from unittest.mock import patch
from dkord_desktop.catalogue import parse_page,parse_search,parse_continuation,watch_next
from dkord_desktop.provider import Provider,SearchCursor


def text(value):return {'runs':[{'text':value}]}

def item(video='abcdefghijk',title='संगवारी',artist='Artist'):
    return {'musicResponsiveListItemRenderer':{'playlistItemData':{'videoId':video},'flexColumns':[
        {'musicResponsiveListItemFlexColumnRenderer':{'text':text(title)}},
        {'musicResponsiveListItemFlexColumnRenderer':{'text':text(artist)}}],
        'fixedColumns':[{'musicResponsiveListItemFixedColumnRenderer':{'text':text('3:42')}}],
        'thumbnail':{'musicThumbnailRenderer':{'thumbnail':{'thumbnails':[{'url':'//i.ytimg.com/vi/'+video+'/hqdefault.jpg'}]}}}}}


def search(rows,token=None):
    shelf={'contents':rows,'title':text('Songs')}
    if token:shelf['continuations']=[{'nextContinuationData':{'continuation':token}}]
    return {'contents':{'tabbedSearchResultsRenderer':{'tabs':[{'tabRenderer':{'content':{
        'sectionListRenderer':{'contents':[{'musicShelfRenderer':shelf}]}}}}]}}}


class CatalogueTest(unittest.TestCase):
    def test_phone_search_rows_keep_unicode_real_id_artist_duration_thumbnail_and_order(self):
        page=parse_search(search([item(),item('lmnopqrstuv','Second')],'opaque_next'),'संगवारी','Songs','params')
        self.assertEqual(['abcdefghijk','lmnopqrstuv'],[entry.id for entry in page.entries])
        first=page.entries[0];self.assertEqual('संगवारी',first.title);self.assertEqual('Artist',first.track.artist)
        self.assertEqual(222,first.track.durationSec);self.assertTrue(first.thumbnail.startswith('https://i.ytimg.com/'))
        self.assertEqual(SearchCursor('संगवारी','Songs','opaque_next','params'),page.cursor)

    def test_search_suggestion_and_correction_are_not_silently_used_as_the_original_query(self):
        root=search([item()]);root['suggestion']={'didYouMeanRenderer':{'correctedQuery':text('Suggested')}}
        page=parse_search(root,'Original','Songs','params');self.assertEqual('Suggested',page.suggested_query);self.assertFalse(page.corrected)
        root['correction']={'showingResultsForRenderer':{'correctedQuery':text('Corrected')}}
        page=parse_search(root,'Original','Songs','params');self.assertTrue(page.corrected);self.assertEqual('Corrected',page.suggested_query)

    def test_real_music_search_continuation_not_repeated_first_page_and_empty_page_ends(self):
        root={'continuationContents':{'musicShelfContinuation':{'contents':[item('lmnopqrstuv')],
            'continuations':[{'nextContinuationData':{'continuation':'next_2'}}]}}}
        page=parse_search(root,'Original','Songs','params');self.assertEqual(['lmnopqrstuv'],[entry.id for entry in page.entries]);self.assertEqual('next_2',page.cursor.token)
        self.assertIsNone(parse_search({},'Original','Songs','params').cursor)
        self.assertIsNone(parse_search(search([], 'x'*8193),'Original','Songs','params').cursor)

    def test_provider_cursor_is_bound_to_original_scope_and_encodes_opaque_token_without_url_injection(self):
        class Client:
            def __init__(self):self.calls=[]
            def _send_request(self,*args):self.calls.append(args);return search([item()],'opaque +/=') if len(self.calls)==1 else {}
        client=Client()
        with patch.object(Provider,'music',return_value=client):
            first=Provider().search_page('  संगवारी  ','Songs');last=Provider().search_more(first.cursor)
        self.assertEqual('search',client.calls[0][0]);self.assertEqual('संगवारी',client.calls[1][1]['query'])
        self.assertIn('opaque%20%2B%2F%3D',client.calls[1][2]);self.assertEqual((),last.entries);self.assertIsNone(last.cursor)
        with self.assertRaises(ValueError):Provider().search_more(SearchCursor('a','Songs','token','unrecognized params'))
        with self.assertRaises(ValueError):Provider().search_page('query','All YouTube')

    def test_album_continuation_returns_real_tracks_and_next_token_not_guessed_titles(self):
        root={'continuationContents':{'musicPlaylistShelfContinuation':{'contents':[item()],
            'continuations':[{'nextContinuationData':{'continuation':'album_next'}}]}}}
        page=parse_continuation(root);self.assertEqual(['abcdefghijk'],[track.id for track in page.tracks]);self.assertEqual('album_next',page.continuation)

    def test_home_mood_browse_params_and_official_album_identity_survive_the_phone_parser(self):
        endpoint={'browseId':'MPREb_phone_album','params':'exact_params','browseEndpointContextSupportedConfigs':{'browseEndpointContextMusicConfig':{'pageType':'MUSIC_PAGE_TYPE_ALBUM'}}}
        album={'musicTwoRowItemRenderer':{'title':text('Album'),'subtitle':text('Artist'),'navigationEndpoint':{'browseEndpoint':endpoint},
            'thumbnailRenderer':{'musicThumbnailRenderer':{'thumbnail':{'thumbnails':[{'url':'//lh3.googleusercontent.com/album'}]}}}}}
        mood={'musicNavigationButtonRenderer':{'buttonText':text('Choliwood'),'clickCommand':{'browseEndpoint':{'browseId':'FEmusic_moods_and_genres_category','params':'opaque_mood'}}}}
        root={'contents':{'sectionListRenderer':{'contents':[{'musicCarouselShelfRenderer':{'header':{'musicCarouselShelfBasicHeaderRenderer':{'title':text('Recommended')}},'contents':[album,mood]}}]}}}
        page=parse_page(root);self.assertEqual('Recommended',page.shelves[0].title)
        a,m=page.shelves[0].items;self.assertEqual(('album','MPREb_phone_album','exact_params'),(a.kind,a.id,a.params));self.assertEqual('opaque_mood',m.params)

    def test_watch_next_never_promotes_vlogs_unplayable_videos_or_missing_music_classification(self):
        def row(video,kind,playable=True):return {'playlistPanelVideoRenderer':{'videoId':video,'title':text(video),'isPlayable':playable,
            'navigationEndpoint':{'watchEndpoint':{'watchEndpointMusicSupportedConfigs':{'watchEndpointMusicConfig':{'musicVideoType':kind}}}},'lengthText':text('3:00')}}
        root={'playlistPanelRenderer':{'contents':[row('abcdefghijk','MUSIC_VIDEO_TYPE_ATV'),row('lmnopqrstuv','MUSIC_VIDEO_TYPE_OMV'),
            row('aaaaaaaaaaa','MUSIC_VIDEO_TYPE_UGC'),row('bbbbbbbbbbb',None),row('ccccccccccc','MUSIC_VIDEO_TYPE_ATV',False)]}}
        self.assertEqual(['abcdefghijk','lmnopqrstuv'],[track.id for track in watch_next(root)])


if __name__=='__main__':unittest.main()
