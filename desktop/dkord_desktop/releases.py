"""Phone NewReleasesRepository/ReleaseDiscovery/MusicUploadDates on desktop.

Date/category decisions are metadata-based, never guessed from a 'new' title or
an extraction failure. Same UTC queries, 40 interleaved candidates, six metadata
workers, exact elapsed windows, category-specific 30-minute/empty 60-second cache.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
import json
import re
import threading
import time
from typing import Callable

from .media import Cancelled, check_cancel
from .models import VIDEO_ID

CATEGORIES = {'ALL': '', 'HOLLYWOOD': 'english', 'BOLLYWOOD': 'hindi', 'CHOLIWOOD': 'bhojpuri',
              'PUNJABI': 'punjabi', 'TAMIL': 'tamil', 'TELUGU': 'telugu'}
WINDOWS = {'LAST_24_HOURS': 24*3600*1000, 'LAST_7_DAYS': 7*24*3600*1000, 'LAST_10_DAYS': 10*24*3600*1000}
MONTHS = ('January','February','March','April','May','June','July','August','September','October','November','December')
MAX_CANDIDATES = 40
CACHE_MS = 30*60*1000
EMPTY_CACHE_MS = 60_000
MAX_PAGE = 3*1024*1024


class ReleaseDatesUnavailable(ValueError):
    pass


def release_queries(category, now_ms):
    language = CATEGORIES[category]
    date = datetime.fromtimestamp(now_ms/1000, timezone.utc).date()
    month = f'{MONTHS[date.month-1]} {date.year}'
    after = (date-timedelta(days=10)).isoformat()
    if category == 'ALL':
        return [f'new {lang} songs {month} after:{after}' for lang in ('english','hindi','bhojpuri','punjabi')]
    return [f'new {language} songs {month}', f'latest {language} songs after:{after}', f'new {language} songs this week {month}']


def releases_in_window(candidates, window, now_ms):
    duration = WINDOWS[window]
    dated = sorted(((track, date) for track, date in candidates if isinstance(date, (int,float)) and not isinstance(date,bool)
                    and date > 0 and date <= now_ms and now_ms-date <= duration), key=lambda item:-item[1])
    result, seen = [], set()
    for track, _ in dated:
        if track.id not in seen:
            seen.add(track.id); result.append(track)
    return result


def iso_date(value):
    if not isinstance(value,str):
        return None
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            date = datetime.strptime(value,'%Y-%m-%d').replace(tzinfo=timezone.utc)
        else:
            date = datetime.fromisoformat(value.replace('Z','+00:00'))
            if date.tzinfo is None:
                return None
        return int(date.timestamp()*1000)
    except (ValueError,OverflowError,OSError):
        return None


class _Dates(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.dates={}
    def handle_starttag(self,tag,attrs):
        if tag.lower()!='meta':
            return
        attrs=dict((key.lower(),value) for key,value in attrs)
        name=(attrs.get('itemprop') or attrs.get('property') or attrs.get('name') or '').lower()
        if name in ('datepublished','uploaddate','video:release_date'):
            date=iso_date(attrs.get('content'))
            if date is not None:
                self.dates.setdefault(name,date)


def published_at(html):
    if not isinstance(html,str) or len(html)>MAX_PAGE:
        return None
    marker=re.search(r'"playerMicroformatRenderer"\s*:\s*\{',html)
    micro={}
    if marker:
        try:
            value,_=json.JSONDecoder().raw_decode(html[marker.end()-1:marker.end()-1+256*1024])
            if isinstance(value,dict):
                micro=value
        except (ValueError,RecursionError):
            pass
    date=iso_date(micro.get('publishDate'))
    if date is not None:
        return date
    parser=_Dates()
    try:
        parser.feed(html)
    except (ValueError,RecursionError):
        pass
    return (parser.dates.get('datepublished') or parser.dates.get('video:release_date')
            or iso_date(micro.get('uploadDate')) or parser.dates.get('uploaddate'))


def upload_date(track,cancel):
    import requests
    if not VIDEO_ID.fullmatch(track.id):
        return None
    check_cancel(cancel)
    # Main-video publication metadata only. No account, cookies, audio extraction,
    # authenticated fallback, recommendation dates or access-restriction bypass.
    session=requests.Session();session.trust_env=False
    try:
        with session.get('https://www.youtube.com/watch',params={'v':track.id},
                         headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
                                  'Accept-Language':'en-US,en;q=0.9'},timeout=(5,10),stream=True,allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code!=200:
                raise ValueError('Release metadata unavailable')
            data=bytearray();deadline=time.monotonic()+15
            for chunk in response.iter_content(16_384):
                check_cancel(cancel)
                if time.monotonic()>deadline:
                    raise TimeoutError('Release metadata timed out')
                data.extend(chunk[:MAX_PAGE-len(data)])
                if len(data)>=MAX_PAGE:
                    break
            check_cancel(cancel)
            return published_at(bytes(data).decode('utf-8','replace'))
    finally:
        session.close()


class NewReleasesRepository:
    def __init__(self,sources,dates=upload_date,now=lambda:int(time.time()*1000),elapsed=lambda:int(time.monotonic()*1000)):
        self.sources,self.dates,self.now,self.elapsed=sources,dates,now,elapsed
        self.cache={};self.lock=threading.Lock()

    def songs(self,window='LAST_7_DAYS',category='ALL',refresh=False,cancel=None):
        if window not in WINDOWS or category not in CATEGORIES:
            raise ValueError('Unsupported release window/category')
        cancel=cancel or threading.Event()
        while not self.lock.acquire(timeout=.1):
            check_cancel(cancel)
        try:
            check_cancel(cancel);stored=self.cache.get(category)
            if stored and not refresh and 0<=self.elapsed()-stored[0]<(CACHE_MS if stored[1] else EMPTY_CACHE_MS):
                dated=stored[1]
            else:
                dated=self.fetch(category,cancel);check_cancel(cancel)
                self.cache[category]=(self.elapsed(),dated)
            return releases_in_window(dated,window,self.now())
        finally:
            self.lock.release()

    def fetch(self,category,cancel):
        def source(call):
            check_cancel(cancel)
            try:
                return (call(category,cancel),None)
            except Cancelled:
                raise
            except Exception as error:
                return ([],error)
        with ThreadPoolExecutor(max_workers=5,thread_name_prefix='dkord-release-source') as pool:
            results=list(pool.map(source,self.sources))
        check_cancel(cancel)
        if results and all(error is not None for _,error in results):
            raise ValueError('New release sources unavailable')
        lists=[tracks for tracks,_ in results];candidates={}
        for index in range(max((len(tracks) for tracks in lists),default=0)):
            for tracks in lists:
                if index<len(tracks):
                    track=tracks[index]
                    if track.id.strip() and track.title.strip():
                        candidates.setdefault(track.id,track)
                if len(candidates)>=MAX_CANDIDATES:
                    break
            if len(candidates)>=MAX_CANDIDATES:
                break
        if not candidates and any(error is not None for _,error in results):
            raise ValueError('New release sources unavailable')
        def date(track):
            check_cancel(cancel)
            try:
                value=self.dates(track,cancel)
                return (track,value) if value is not None and value>0 else None
            except Cancelled:
                raise
            except Exception:
                return None
        with ThreadPoolExecutor(max_workers=6,thread_name_prefix='dkord-release-date') as pool:
            dated=[item for item in pool.map(date,candidates.values()) if item is not None]
        check_cancel(cancel)
        if candidates and not dated:
            raise ReleaseDatesUnavailable('Release dates could not be verified')
        now=self.now()
        return [(track,value) for track,value in dated if value<=now and now-value<=WINDOWS['LAST_10_DAYS']]

    @classmethod
    def from_provider(cls,provider):
        def expand(page,cancel):
            direct=list(page.tracks)+[entry.track for shelf in page.shelves for entry in shelf.items if entry.track]
            albums={entry.id:entry for shelf in page.shelves for entry in shelf.items if entry.kind in ('album','albums')}
            def load(entry):
                check_cancel(cancel)
                try:
                    result=provider.catalogue_page(entry)
                    return (list(result.tracks)+[entry.track for shelf in result.shelves for entry in shelf.items if entry.track],None)
                except Cancelled:
                    raise
                except Exception as error:
                    return ([],error)
            with ThreadPoolExecutor(max_workers=3,thread_name_prefix='dkord-release-album') as pool:
                results=list(pool.map(load,list(albums.values())[:4]))
            if not direct and results and all(error is not None for _,error in results):
                raise ValueError('New release albums unavailable')
            return direct+[track for tracks,_ in results for track in tracks]
        def browse(category,cancel):
            if category=='ALL':
                page=provider.catalogue_page(browse_id='FEmusic_new_releases')
            else:
                from .catalogue import Page,Shelf
                query=release_queries(category,int(time.time()*1000))[0].replace('songs','albums')
                page=Page(shelves=(Shelf('',tuple(provider.search(query,'Albums',40))),))
            return expand(page,cancel)
        def search(index):
            def call(category,cancel):
                check_cancel(cancel);queries=release_queries(category,int(time.time()*1000))
                return [entry.track for entry in provider.search(queries[index],'Songs',40) if entry.track] if index<len(queries) else []
            return call
        return cls([browse]+[search(index) for index in range(4)])
