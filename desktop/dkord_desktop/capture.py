"""Capture this actual app, not an illustration. Only isolated generated audio; never user data."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import struct
import sys
import tempfile
import threading
import time
from uuid import uuid4
import wave

from . import __version__
from .platforms import platform_key
from .qt import BINDING, QtCore
from .media import MediaLibrary
from .models import Track
from .provider import Provider
from .store import Store
from .ui import MainWindow


class NoNetwork(Provider):
    def unavailable(self,*args,**kwargs):
        raise AssertionError('Screenshot mode cannot fetch or invent live catalogue results')
    search=home=browse=related=resolve=home_page=catalogue_page=suggestions=resolve_video=search_page=search_more=open_youtube_link=unavailable


def tone(path, hz):
    with wave.open(str(path),'wb') as out:
        out.setparams((1,2,22050,0,'NONE','not compressed'))
        out.writeframes(b''.join(struct.pack('<h',round(6000*math.sin(i*2*math.pi*hz/22050))) for i in range(12*22050)))


def capture(app, output: Path):
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):raise ValueError('Screenshot output must be empty; never overwrite existing files')
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dkord-offline-screenshot-') as temp:
        root=Path(temp);store=Store(root/'isolated-data');media=MediaLibrary(store,NoNetwork());tracks=[];files=[]
        for title,hz in [('Warm glow',220),('Midnight pulse',440),('First light',880)]:
            path=media.offline/(title+'.wav');tone(path,hz);files.append(path)
            track=Track('studio:'+str(uuid4()),title+' · audio sample','Dkord generated tones','Offline showcase',12)
            store.put_track(track);store.queue_download(track,'app')
            store.update_download(track.id,state='DONE',path=str(path),bytes=path.stat().st_size,total=path.stat().st_size)
            store.like(track,True);store.history(track,3200);tracks.append(track)
        store.save_playlist('Offline showcase',tracks)
        store.set_setting('session',{'version':1,'queue':[track.json() for track in tracks],'index':0,'position':3200})
        project=store.create_project('Nightfall · offline demo mix')
        for file in files[:2]:media.import_source(project,file,threading.Event())
        def edit(data):
            data['clips'][0]['startMs']=1000;data['clips'][0]['endMs']=5500
            data['clips'][1]['startMs']=2000;data['clips'][1]['endMs']=9000
        store.change_project(project,edit)
        window=MainWindow(store,NoNetwork(),autoload=False);window.resize(1360,850);window.show()
        def settle():
            deadline=time.monotonic()+.5
            while time.monotonic()<deadline:
                app.processEvents()
                # This CLI intentionally does not start app.exec(). Flush deletions
                # queued by real page navigation, not old rows behind the next page.
                QtCore.QCoreApplication.sendPostedEvents(None,QtCore.QEvent.Type.DeferredDelete)
                time.sleep(.01)
        records=[]
        for page,name in [('Liked songs','windows-x86-player.png'),('Mashup Studio','windows-x86-studio.png')]:
            window.studio_id=project;window.navigate(page,fetch=False)
            window.notify('Offline showcase · generated audio samples, not live search results')
            settle();assert window.isVisible() and window.width()>=940
            path=output/name;image=window.grab()
            if not image.save(str(path),'PNG'):raise ValueError('Could not capture the actual Qt window')
            data=path.read_bytes()
            records.append({'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'width':image.width(),'height':image.height(),'page':page})
        window.close()
        for pool in (window.pool,window.download_pool,window.home_pool,window.artwork_cache.pool):pool.waitForDone()
        app.processEvents()
    proof={'format':1,'application':'Dkord','version':__version__,'source':os.environ.get('DKORD_SOURCE_SHA','local'),
           'platform':platform_key(),'os':platform.system(),'python_bits':struct.calcsize('P')*8,
           'qt_binding':BINDING,'qt_version':QtCore.QT_VERSION_STR,'frozen':bool(getattr(sys,'frozen',False)),
           'capture':'actual QMainWindow.grab; window contents, not an OS-desktop montage',
           'data':'isolated locally generated sine tones; no user files, provider calls or invented search results',
           'images':records}
    (output/'windows-x86-screenshot-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    return 0
