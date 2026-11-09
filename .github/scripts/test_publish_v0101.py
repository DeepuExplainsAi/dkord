"""Synthetic metadata/byte fixtures only; no network, installer or publication."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import publish_v0101 as publisher

class PublicationReceiptTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        self.source='7'*40;self.baseline={'synthetic historical receipt':'unchanged'}
        for name in publisher.expected_names()-{'SHA256SUMS'}:(self.folder/name).write_bytes(('EXPLICIT UNIT FIXTURE '+name).encode())
        publisher.checksums(self.folder)
        self.release=dict(id=123456,tag_name=publisher.TAG,target_commitish=self.source,draft=False,prerelease=False,html_url='https://github.com/DeepuExplainsAi/dkord/releases/tag/v0.10.1',
                          assets=[dict(name=file.name,size=file.stat().st_size,digest='sha256:'+publisher.digest(file),browser_download_url='https://github.com/'+publisher.REPO+'/releases/download/'+publisher.TAG+'/'+file.name) for file in self.folder.iterdir()])
    def api(self,path,optional=False):
        if path=='git/ref/tags/'+publisher.TAG:return dict(object=dict(type='commit',sha='7'*40))
        if path=='releases/tags/'+publisher.TAG:return self.release
        if path=='releases/latest':return dict(id=self.release['id'])
        raise AssertionError('Unmocked fixture API path '+path)
    def verify(self,draft=False):
        with patch.object(publisher,'api',side_effect=self.api),patch.object(publisher,'historical_snapshot',return_value=self.baseline):
            return publisher.verify_release(self.folder,self.source,self.baseline,draft)
    def test_exact_twenty_assets_have_nineteen_checksum_entries_and_verify(self):
        self.assertEqual(20,len(publisher.expected_names()));self.assertEqual(19,len((self.folder/'SHA256SUMS').read_text().splitlines()))
        self.assertEqual(self.release,self.verify())
    def test_checksum_stage_never_overwrites_or_accepts_missing_or_extra_files(self):
        with self.assertRaises(ValueError):publisher.checksums(self.folder)
        (self.folder/'unapproved.txt').write_text('not a release asset')
        with self.assertRaises(ValueError):self.verify()
    def test_wrong_uploaded_bytes_duplicates_missing_asset_or_wrong_source_are_refused(self):
        original=copy.deepcopy(self.release)
        for change in ('size','digest','duplicate','source'):
            self.release=copy.deepcopy(original)
            if change=='size':self.release['assets'][0]['size']+=1
            elif change=='digest':self.release['assets'][0]['digest']='sha256:'+'0'*64
            elif change=='duplicate':self.release['assets'][0]=self.release['assets'][1]
            else:self.source='8'*40;self.release['target_commitish']='7'*40
            with self.subTest(change=change),self.assertRaises(ValueError):self.verify()
            self.source='7'*40
    def test_any_change_to_an_old_release_or_asset_refuses_promotion(self):
        with patch.object(publisher,'historical_snapshot',return_value={'changed':'refused'}),self.assertRaises(ValueError):
            publisher.verify_release(self.folder,self.source,self.baseline,False)
    def test_a_github_draft_without_its_yet_published_git_tag_is_bound_to_exact_commitish(self):
        self.release['draft']=True
        def draft_api(path,optional=False):
            if path=='git/ref/tags/'+publisher.TAG:return None
            return self.api(path,optional)
        with patch.object(publisher,'api',side_effect=draft_api),patch.object(publisher,'historical_snapshot',return_value=self.baseline):
            publisher.verify_release(self.folder,self.source,self.baseline,True)
            self.release['target_commitish']='8'*40
            with self.assertRaises(ValueError):publisher.verify_release(self.folder,self.source,self.baseline,True)
    def test_published_draft_prerelease_wrong_latest_or_external_download_are_refused(self):
        for field in ('draft','prerelease'):
            self.release[field]=True
            with self.assertRaises(ValueError):self.verify()
            self.release[field]=False
        self.release['assets'][0]['browser_download_url']='https://untrusted.invalid/download'
        with self.assertRaises(ValueError):self.verify()
    def test_notes_state_the_one_time_bootstrap_and_os_signing_limits_without_physical_claims(self):
        notes=publisher.notes(self.source,'1234','5678')
        for text in ('Do not uninstall','one-time manual','original','not','physical','No cloud'):
            self.assertIn(text,notes)
        with self.assertRaises(ValueError):publisher.notes('not-a-sha','1234','5678')
