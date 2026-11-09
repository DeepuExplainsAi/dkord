"""Byte/metadata fixtures only; actual native packages/tests are verified separately in OS CI."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from verify_desktop_release_artifacts import TARGETS,KINDS,PARITY_CLASSES,digest,verify_and_stage

class NativeReleaseProofTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'input';self.output=Path(self.temp.name)/'output'
        self.sha=hashlib.sha1(b'exact release source fixture').hexdigest();self.version='0.10.0'
        for target in TARGETS:self.target(target)
    def target(self,target):
        folder=self.root/('desktop-preview-'+target);folder.mkdir(parents=True)
        entries=[]
        for kind in KINDS[target]:
            file=folder/f'Dkord-desktop-v{self.version}-{target}.{kind}'
            data=bytearray(256)
            if kind=='exe':data[:2]=b'MZ';struct.pack_into('<I',data,60,128);data[128:134]=b'PE\0\0'+struct.pack('<H',0x14c)
            elif kind=='pkg':data[:4]=b'xar!'
            elif kind=='deb':data[:8]=b'!<arch>\n'
            else:data[:6]=b'\x7fELF\x02\x01';data[8:11]=b'AI\x02';data[18:20]=(183 if target.endswith('arm64') else 62).to_bytes(2,'little')
            file.write_bytes(data);entries.append({'name':file.name,'bytes':len(data),'sha256':digest(file)})
        manifest={'channel':'development-preview','version':self.version,'target':target,'source':self.sha,
                  'trusted_signed_release':False,'notarized':False,'artifacts':entries}
        x86=target=='windows-x86'
        manifest['runtime']={'python_bits':32 if x86 else 64,'qt_binding':'PyQt5' if x86 else 'PyQt6','audio_probe':'ffmpeg' if x86 else 'pyav'}
        if target.startswith('windows-'):
            arch='x86' if x86 else 'x64';manifest['runtime']['verified_pe_payloads']={'application':arch,'node':arch,'ffmpeg':arch}
        if x86:manifest['runtime']['verified_pe_payloads']['ffprobe']='x86'
        if x86:manifest['codec_source']={'version':'8.1.3','source_commit':'1041abdc962f4cc4f394aa8de9dc5236c0c3b9e7','source_archive_sha256':'a406fe831cbb605f5fe50e43eb566e502ae63ff3b3206bfa744e4b31b8bb73ac','architecture':'x86'}
        if target.startswith('linux-'):manifest['minimum_glibc']='2.39'
        self.save(target,manifest)
        cases=''.join(f'<testcase classname="desktop.tests.{cls}" name="case{i}"/>' for cls in ('CoreTest','UpdateTest','NativeWidgetTest') for i in range(12))
        (folder/'test-results.xml').write_text('<testsuites><testsuite tests="36" failures="0" errors="0" skipped="0">'+cases+'</testsuite></testsuites>')
    def folder(self,target='windows-x64'):return self.root/('desktop-preview-'+target)
    def manifest(self,target='windows-x64'):return json.loads((self.folder(target)/f'preview-{target}.json').read_text())
    def save(self,target,data):
        (self.root/('desktop-preview-'+target)/f'preview-{target}.json').write_text(json.dumps(data))
    def verify(self):return verify_and_stage(self.root,self.output,self.sha,self.version)
    def current_fixture(self):
        # Synthetic validation envelope only, NOT real installer evidence. Real
        # installers run on all six native hosts before release promotion.
        self.version='0.10.1'
        for target in TARGETS:
            data=self.manifest(target);data['version']=self.version
            for entry in data['artifacts']:
                old=entry['name'];entry['name']=old.replace('v0.10.0-','v0.10.1-')
                (self.folder(target)/old).rename(self.folder(target)/entry['name'])
            checks={name:True for name in ('library','playlists','likes','history','settings','queue','privateDownload','deviceDownload','studioSources','studioClips','audioDecoded')}
            data['installOver']=dict(format=1,baselineTag='desktop-v0.10.0-preview.2',baselineSource='0d97e6413d999cdfbb562397cc230f1798f02606',toVersion=self.version,
                                     target=target,source=self.sha,noUninstall=True,standardUserData=True,frozenClient=True,
                                     packages=[dict(kind=kind,baselineName=f'Dkord-desktop-v0.10.0-{target}.{kind}',baselineSha256='1'*64,checks=checks) for kind in KINDS[target]])
            self.save(target,data)
            names=list(PARITY_CLASSES)+['CoreTest']*(121-len(PARITY_CLASSES))
            cases=''.join(f'<testcase classname="desktop.tests.{name}" name="synthetic{i}"/>' for i,name in enumerate(names))
            (self.folder(target)/'test-results.xml').write_text('<testsuites><testsuite tests="121" failures="0" errors="0" skipped="0">'+cases+'</testsuite></testsuites>')
    def test_current_release_requires_actual_new_minimum_classes_and_all_data_categories(self):
        self.current_fixture();files=self.verify();self.assertEqual(14,len(files))
    def test_old_36_case_execution_cannot_be_promoted_as_the_new_release(self):
        previous=(self.folder()/'test-results.xml').read_text();self.current_fixture()
        (self.folder()/'test-results.xml').write_text(previous)
        with self.assertRaises(ValueError):self.verify()
    def test_new_cases_without_signature_or_installer_regression_class_are_rejected(self):
        self.current_fixture();path=self.folder()/'test-results.xml';original=path.read_text()
        for name in ('ManifestSignerTest','UpgradeFixtureTest','NativeWidgetTest'):
            path.write_text(original.replace(name,'NotRequiredClass'))
            with self.subTest(name=name),self.assertRaises(ValueError):self.verify()
    def test_new_release_cannot_omit_install_over_or_claim_a_missing_persisted_category(self):
        self.current_fixture();original=self.manifest()
        for value in ({},original['installOver']|{'noUninstall':False},original['installOver']|{'source':'1'*40}):
            self.save('windows-x64',original|{'installOver':value})
            with self.assertRaises(ValueError):self.verify()
        broken=json.loads(json.dumps(original));broken['installOver']['packages'][0]['checks']['privateDownload']=False
        self.save('windows-x64',broken)
        with self.assertRaises(ValueError):self.verify()
    def test_linux_must_really_update_both_deb_and_appimage(self):
        self.current_fixture();data=self.manifest('linux-arm64');data['installOver']['packages']=data['installOver']['packages'][:1]
        self.save('linux-arm64',data)
        with self.assertRaises(ValueError):self.verify()
    def test_all_six_targets_stage_eight_packages_and_six_honest_preview_manifests(self):
        files=self.verify();self.assertEqual(14,len(files));self.assertEqual(8,sum(p.suffix in ('.exe','.pkg','.deb','.AppImage') for p in files))
        self.assertEqual(6,sum(p.suffix=='.json' for p in files))
    def test_an_old_source_version_target_or_signing_claim_is_rejected(self):
        original=self.manifest()
        for key,value in (('source',hashlib.sha1(b'old').hexdigest()),('version','0.9.1'),('target','linux-x64'),('channel','production'),('trusted_signed_release',True),('notarized',True)):
            self.save('windows-x64',original|{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify()
        self.assertFalse(self.output.exists())
    def test_missing_platform_or_package_is_not_silently_omitted(self):
        file=next(self.folder('macos-arm64').glob('*.pkg'));file.unlink()
        with self.assertRaises(ValueError):self.verify()
    def test_tampered_bytes_even_with_unchanged_size_are_rejected(self):
        file=next(self.folder().glob('*.exe'));data=bytearray(file.read_bytes());data[-1]^=1;file.write_bytes(data)
        with self.assertRaises(ValueError):self.verify()
    def test_wrong_size_duplicate_name_or_traversal_entry_is_rejected(self):
        original=self.manifest()
        for changed in ({'bytes':True},{'bytes':255},{'name':'../escape.exe'}):
            data=json.loads(json.dumps(original));data['artifacts'][0].update(changed);self.save('windows-x64',data)
            with self.assertRaises(ValueError):self.verify()
        data=json.loads(json.dumps(original));data['artifacts']*=2;self.save('windows-x64',data)
        with self.assertRaises(ValueError):self.verify()
    def test_correct_hash_does_not_allow_an_apk_renamed_as_native_package(self):
        file=next(self.folder().glob('*.exe'));file.write_bytes(b'PK\x03\x04'+bytes(252))
        data=self.manifest();data['artifacts'][0]['sha256']=digest(file);self.save('windows-x64',data)
        with self.assertRaises(ValueError):self.verify()
    def test_appimage_architecture_is_checked_beyond_filename_and_hash(self):
        target='linux-arm64';file=next(self.folder(target).glob('*.AppImage'));data=bytearray(file.read_bytes());data[18:20]=(62).to_bytes(2,'little');file.write_bytes(data)
        meta=self.manifest(target)
        for entry in meta['artifacts']:
            if entry['name']==file.name:entry['sha256']=digest(file)
        self.save(target,meta)
        with self.assertRaises(ValueError):self.verify()
    def test_no_skipped_failed_or_missing_native_test_class_can_be_promoted(self):
        file=self.folder()/'test-results.xml';original=file.read_text()
        for content in (original.replace('/>','><skipped/></testcase>',1),original.replace('failures="0"','failures="1"'),original.replace('NativeWidgetTest','NotTheRequiredClass')):
            file.write_text(content)
            with self.assertRaises(ValueError):self.verify()
    def test_inconsistent_native_junit_totals_are_rejected(self):
        file=self.folder()/'test-results.xml';file.write_text(file.read_text().replace('tests="36"','tests="37"'))
        with self.assertRaises(ValueError):self.verify()
    def test_preview_symlinks_and_unexpected_extra_files_are_rejected(self):
        file=self.folder()/'unexpected.txt';file.write_text('not an approved asset')
        with self.assertRaises(ValueError):self.verify()
        file.unlink();native=next(self.folder().glob('*.exe'));original=self.root/'binary';native.rename(original);native.symlink_to(original)
        with self.assertRaises(ValueError):self.verify()
    def test_no_existing_output_or_duplicate_json_fields_can_be_overwritten(self):
        self.output.mkdir();(self.output/'old').write_text('keep')
        with self.assertRaises(ValueError):self.verify()
        (self.output/'old').unlink();self.output.rmdir()
        file=self.folder()/'preview-windows-x64.json';text=file.read_text();file.write_text(text[:-1]+',"source":"different"}')
        with self.assertRaises(ValueError):self.verify()
    def test_linux_minimum_glibc_is_not_misrepresented(self):
        data=self.manifest('linux-x64');data['minimum_glibc']='2.34';self.save('linux-x64',data)
        with self.assertRaises(ValueError):self.verify()
    def test_nonzero_full_source_sha_and_exact_version_are_required(self):
        for sha in ('bad','0'*40):
            with self.assertRaises(ValueError):verify_and_stage(self.root,self.output,sha,self.version)

if __name__=='__main__':unittest.main()
