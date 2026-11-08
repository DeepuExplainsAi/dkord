import json
import math
import struct
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import av
from dkord_desktop.models import Track, milliseconds, owned_path, safe_name
from dkord_desktop.store import Store
from dkord_desktop.media import MediaLibrary, Cancelled, atomic_copy, probe, publish_device
from dkord_desktop.library_json import export_library, import_library
from dkord_desktop.provider import provider_track


def tone(path, rate=44100, stereo=False):
    with wave.open(str(path), 'wb') as file:
        file.setnchannels(2 if stereo else 1);file.setsampwidth(2);file.setframerate(rate)
        data=bytearray()
        for index in range(rate*2):
            hz=440 if stereo else (220 if index<rate else 880)
            value=round(10000*math.sin(index*2*math.pi*hz/rate))
            data.extend(struct.pack('<h',value)*(2 if stereo else 1))
        file.writeframes(bytes(data))


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'data');self.media=MediaLibrary(self.store)
        self.track=Track('online00001','संगवारी — Choliwood','Singer')
        self.input=self.root/'original.wav';tone(self.input)
    def tearDown(self):self.temp.cleanup()
    def test_library_and_session_survive_reopen_without_moving_audio(self):
        self.store.like(self.track,True);self.store.history(self.track,12345);self.store.save_playlist('Local',[self.track,self.track]);self.store.remember_query('  Choliwood  2026 ','Songs')
        self.store.set_setting('session',{'queue':[self.track.json()],'position':12345})
        other=Store(self.store.root)
        self.assertEqual([self.track],other.library('liked'));self.assertEqual([self.track],other.library('history'))
        self.assertEqual(2,len(other.playlists()[0]['data']));self.assertEqual(12345,other.setting('session')['position']);self.assertTrue(self.input.exists())
    def test_unknown_database_version_is_refused_without_reset(self):
        self.store.like(self.track,True)
        with self.store.connect() as db:db.execute('PRAGMA user_version=999')
        with self.assertRaises(ValueError):Store(self.store.root)
        with self.store.connect() as db:self.assertEqual(1,db.execute('SELECT COUNT(*) FROM likes').fetchone()[0])
    def test_private_completed_song_exports_offline_without_refetch_or_overwrite_and_device_copy_survives_removal(self):
        private=self.media.offline/'source.wav';atomic_copy(self.input,private)
        self.store.queue_download(self.track,'app');self.store.update_download(self.track.id,state='DONE',path=str(private))
        folder=self.root/'Music';folder.mkdir();old=folder/safe_name(self.track,'wav');old.write_text('original user file')
        self.store.queue_download(self.track,'device',str(folder))
        with patch.object(self.media,'fetch',side_effect=AssertionError('No network for a completed private source')):
            self.media.process_download(self.track.id)
        row=self.store.download(self.track.id);public=Path(row['device_path'])
        self.assertEqual('DONE',row['state']);self.assertNotEqual(old,public);self.assertEqual('original user file',old.read_text());self.assertEqual(private.read_bytes(),public.read_bytes())
        self.media.remove(self.track.id);self.assertFalse(private.exists());self.assertTrue(public.exists());self.assertTrue(self.input.exists())
    def test_failed_device_copy_keeps_private_bytes_and_retries_with_no_network(self):
        private=self.media.offline/'source.wav';atomic_copy(self.input,private)
        self.store.queue_download(self.track,'app');self.store.update_download(self.track.id,state='DONE',path=str(private))
        blocker=self.root/'not-a-directory';blocker.write_text('user file')
        self.store.queue_download(self.track,'device',str(blocker/'music'))
        with self.assertRaises(OSError):self.media.process_download(self.track.id)
        self.assertEqual('FAILED',self.store.download(self.track.id)['state']);self.assertTrue(private.exists());self.assertEqual('user file',blocker.read_text())
        self.store.queue_download(self.track,'device',str(self.root/'Music'))
        with patch.object(self.media,'fetch',side_effect=AssertionError('retry must not refetch')):self.media.process_download(self.track.id)
        self.assertEqual('DONE',self.store.download(self.track.id)['state'])
    def test_online_studio_preparation_creates_durable_source_not_a_download_or_url(self):
        project=self.store.create_project('Online mix')
        def fetched(track,target,event,progress):
            file=target/'fixture.wav';atomic_copy(self.input,file);progress(file.stat().st_size,file.stat().st_size);return file
        with patch.object(self.media,'fetch',side_effect=fetched):self.media.import_source(project,self.track,threading.Event())
        p=self.store.project(project);self.assertEqual(1,len(p['sources']));self.assertEqual(1,len(p['clips']));self.assertEqual(2000,p['sources'][0]['durationMs'])
        self.assertIsNone(self.store.download(self.track.id));self.assertNotIn('https:',json.dumps(p));self.assertTrue(self.media.source_file(p['sources'][0]).is_file());self.assertEqual([],list(self.media.temporary.iterdir()))
    def test_cancel_before_source_commit_leaves_no_source_clip_or_staging_and_original_is_kept(self):
        project=self.store.create_project('Kept');event=threading.Event();real=atomic_copy
        def cancel_after_copy(src,target,token=None):real(src,target,token);event.set()
        with patch('dkord_desktop.media.atomic_copy',side_effect=cancel_after_copy):
            with self.assertRaises(Cancelled):self.media.import_source(project,self.input,event)
        self.assertEqual([],self.store.project(project)['sources']);self.assertEqual([],list(self.media.sources.iterdir()));self.assertTrue(self.input.is_file())
    def test_invalid_audio_and_bad_clip_bounds_are_not_committed(self):
        project=self.store.create_project('Kept');bad=self.root/'invalid.m4a';bad.write_bytes(b'not audio')
        with self.assertRaises(Exception):self.media.import_source(project,bad,threading.Event())
        self.assertEqual([],self.store.project(project)['sources'])
        self.media.import_source(project,self.input,threading.Event());p=self.store.project(project);p['clips'][0]['endMs']=2001
        with self.assertRaises(ValueError):self.media.validate_project(p)
    def test_actual_ffmpeg_merges_mixed_rate_clips_in_order_and_decodes_expected_tones(self):
        project=self.store.create_project('Real mix');second=self.root/'other.wav';tone(second,48000,True)
        self.media.import_source(project,self.input,threading.Event());self.media.import_source(project,second,threading.Event())
        def clips(p):
            a,b=p['sources'];p['clips']=[{'id':'a','sourceId':a['id'],'startMs':1100,'endMs':1500},{'id':'b','sourceId':b['id'],'startMs':200,'endMs':1000},{'id':'c','sourceId':a['id'],'startMs':100,'endMs':400}]
        self.store.change_project(project,clips);track=self.media.export(project,threading.Event());file=self.media.local_file(track)
        self.assertLess(abs(probe(file)-1500),100)
        samples=[];resample=av.AudioResampler(format='s16',layout='mono',rate=48000)
        with av.open(str(file)) as audio:
            for frame in audio.decode(audio=0):
                for out in resample.resample(frame):samples.extend(struct.unpack('<'+'h'*out.samples,bytes(out.planes[0])[:out.samples*2]))
        def peak(start,end):
            window=samples[round(start*48000):round(end*48000)]
            def energy(hz):
                real=sum(v*math.cos(2*math.pi*hz*i/48000) for i,v in enumerate(window));imag=sum(v*math.sin(2*math.pi*hz*i/48000) for i,v in enumerate(window));return real*real+imag*imag
            return max((220,440,880),key=energy)
        self.assertEqual(880,peak(.12,.28));self.assertEqual(440,peak(.6,.9));self.assertEqual(220,peak(1.3,1.4))
    def test_export_snapshot_pins_sources_even_when_project_deleted_during_render(self):
        project=self.store.create_project('Snapshot');self.media.import_source(project,self.input,threading.Event());source=self.media.source_file(self.store.project(project)['sources'][0])
        started=threading.Event();go=threading.Event();result=[];render=self.media.render
        def wait(*args):started.set();self.assertTrue(go.wait(10));return render(*args)
        def work():
            try:result.append(self.media.export(project,threading.Event()))
            except BaseException as e:result.append(e)
        with patch.object(self.media,'render',side_effect=wait):
            thread=threading.Thread(target=work);thread.start();self.assertTrue(started.wait(10));self.media.delete_project(project);self.assertTrue(source.exists());go.set();thread.join(20)
        self.assertFalse(thread.is_alive());self.assertIsInstance(result[0],Track);self.assertTrue(self.media.local_file(result[0]).is_file());self.media.gc_sources();self.assertFalse(source.exists())
    def test_json_round_trip_uses_android_app_version_playlists_liked_contract(self):
        self.store.like(self.track,True);self.store.save_playlist('दोस्त',[self.track,self.track]);file=self.root/'library.json';export_library(self.store,file)
        data=json.loads(file.read_text());self.assertEqual('dkord',data['app']);self.assertEqual(1,data['version']);self.assertEqual('दोस्त',data['playlists'][0]['name'])
        other=Store(self.root/'other');import_library(other,file);self.assertEqual([self.track],other.library('liked'));self.assertEqual(2,len(other.playlists()[0]['data']))
    def test_bad_json_import_is_atomic_and_history_clear_does_not_delete_likes_or_tracks(self):
        self.store.like(self.track,True);self.store.history(self.track,1)
        file=self.root/'bad.json';file.write_text(json.dumps({'app':'dkord','version':1,'playlists':[{'name':'Good','tracks':[self.track.json()]},{'name':'Bad','tracks':[{'id':'../escape'}]}]}))
        with self.assertRaises(Exception):import_library(self.store,file)
        self.assertEqual([],self.store.playlists());self.store.remove_history();self.assertEqual([self.track],self.store.library('liked'));self.assertIsNotNone(self.store.track(self.track.id))
    def test_millisecond_parser_paths_names_and_provider_identity(self):
        self.assertEqual(62123,milliseconds('1:02.123'));self.assertEqual(62123,milliseconds('१:०२.१२३'))
        for value in ('-1','NaN','1:60','0.0001'):
            with self.assertRaises(ValueError):milliseconds(value)
        with self.assertRaises(ValueError):owned_path(self.root,'../outside')
        self.assertNotIn('/',safe_name(self.track,'m4a'))
        self.assertIsNone(provider_track({'videoId':'../bad','title':'No'}));self.assertEqual(self.track.id,provider_track({'videoId':self.track.id,'title':'Real','artists':[{'name':'Singer'}]}).id)

if __name__=='__main__':unittest.main()
