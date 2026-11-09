"""Explicit installer QA fixtures, never used during normal application startup.

A seed is allowed only in EMPTY test storage. Verification requires that seed and
never resets data or opens a network provider. Production libraries without the
marker are refused untouched. Frozen-client verification uses the normal data
path/lock and the real Store and optional native audio probe.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import struct
from uuid import uuid4
import wave
from .models import Track
from .store import Store

MARKER='.dkord-installer-upgrade-fixture.json'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def seed(root:Path,device:Path):
    if root.is_symlink() or (root.exists() and any(root.iterdir())) or device.exists():
        raise ValueError('Only empty isolated installer QA storage can be seeded')
    store=Store(root);device.mkdir(parents=True)
    private=root/'offline/ci-generated.wav';private.parent.mkdir(parents=True)
    with wave.open(str(private),'wb') as audio:
        audio.setparams((1,2,8000,0,'NONE','not compressed'))
        import math
        audio.writeframes(b''.join(struct.pack('<h',int(2000*math.sin(2*math.pi*440*n/8000))) for n in range(16000)))
    exported=device/'ci-generated.wav';shutil.copyfile(private,exported)
    track=Track('upgrade0001','CI generated installer fixture — अपडेट','Generated tone',durationSec=2)
    store.like(track,True);store.history(track,375)
    playlist=store.save_playlist('CI installer persistence fixture',[track])
    store.queue_download(track,'device',str(device));store.update_download(track.id,state='DONE',path=str(private),device_path=str(exported),bytes=private.stat().st_size,total=private.stat().st_size)
    settings={'language':'hi','theme':'amoled','autoplay':False,'volume':37}
    for key,value in settings.items():store.set_setting(key,value)
    session={'version':1,'queue':[track.json()],'index':0,'position':375};store.set_setting('session',session)
    project=store.create_project('CI Studio source preservation');source_id=str(uuid4())
    source=root/'studio/sources'/f'{source_id}.audio';source.parent.mkdir(parents=True);shutil.copyfile(private,source)
    def add(value):
        value['sources']=[{'id':source_id,'fileName':source.name,'title':track.title,'durationMs':2000}]
        value['clips']=[{'id':str(uuid4()),'sourceId':source_id,'startMs':125,'endMs':1750}]
    expected_project=store.change_project(project,add)
    value=dict(format=1,track=track.json(),playlist=playlist,session=session,settings=settings,project=expected_project,
               device=str(exported),files={str(file.relative_to(root)):digest(file) for file in (private,source)},audioSha256=digest(private))
    with (root/MARKER).open('x',encoding='utf-8') as output:json.dump(value,output,ensure_ascii=False,indent=2)
    return value


def verify(root:Path,decode=False):
    marker=root/MARKER
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size>32768:
        raise ValueError('Installer QA seed absent; existing library was not opened/reset')
    value=json.loads(marker.read_text(encoding='utf-8'))
    if value['format']!=1:raise ValueError('Unknown installer QA fixture')
    store=Store(root);track=Track.parse(value['track'])
    if store.track(track.id)!=track or track not in store.library('liked') or track not in store.library('history'):
        raise ValueError('Track/like/history did not survive install-over')
    if not any(item['id']==value['playlist'] and item['data']==[track.json()] for item in store.playlists()):
        raise ValueError('Playlist did not survive install-over')
    if store.setting('session')!=value['session'] or any(store.setting(key)!=expected for key,expected in value['settings'].items()):
        raise ValueError('Settings/queue/position did not survive install-over')
    download=store.download(track.id)
    if not download or download['state']!='DONE' or download['device_path']!=value['device'] or digest(Path(download['path']))!=value['audioSha256'] or digest(Path(value['device']))!=value['audioSha256']:
        raise ValueError('Private/device download did not survive install-over')
    if store.project(value['project']['id'])!=value['project']:
        raise ValueError('Studio project/clip did not survive install-over')
    for name,expected in value['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or path.is_symlink() or digest(path)!=expected:
            raise ValueError('Private audio/Studio source bytes changed')
    if decode:
        from .media import probe
        if probe(Path(download['path']))!=2000:raise ValueError('Preserved private audio is not decodable')
    return dict(format=1,library=True,playlists=True,likes=True,history=True,settings=True,queue=True,
                privateDownload=True,deviceDownload=True,studioSources=True,studioClips=True,audioDecoded=bool(decode))


def run_probe(root:Path,output:Path):
    # Windowed Win32/macOS binaries need a file receipt, not stdout. Explicit x
    # mode prevents writing over anything the caller already owns.
    if not (root/MARKER).is_file() or output.exists():return 1
    from .qt import QLockFile
    from . import __version__
    from .platforms import platform_key
    import struct
    import sys
    lock=QLockFile(str(root/'application.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(0):return 1
    try:
        checked=verify(root,decode=True)
        with output.open('x') as file:json.dump(dict(version=__version__,target=platform_key(),frozen=bool(getattr(sys,'frozen',False)),pythonBits=struct.calcsize('P')*8,checks=checked),file,indent=2)
        return 0
    except Exception:return 1
    finally:lock.unlock()
