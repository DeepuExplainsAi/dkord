import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from dkord_desktop.updates import canonical, platform_key, verify_manifest, Updater
from dkord_desktop.streaming import valid_audio_url


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.signer=Ed25519PrivateKey.generate()  # test-only; never a production or replacement Android key
        public=self.signer.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.keys={'test':base64.b64encode(public).decode()}
        self.body=b'!<arch>\n'+b'fixture package bytes'*100
        self.payload={'format':1,'channel':'desktop','version':'0.11.0','tag':'desktop-v0.11.0','assets':{}}
        for target,ext,kind in [('windows-x64','.exe','exe'),('windows-x86','.exe','exe'),('macos-x64','.pkg','pkg'),('macos-arm64','.pkg','pkg'),('linux-x64','.deb','deb'),('linux-arm64','.deb','deb')]:
            name=f'Dkord-desktop-v0.11.0-{target}{ext}'
            artifact={'name':name,'kind':kind,'url':f'https://github.com/DeepuExplainsAi/dkord/releases/download/desktop-v0.11.0/{name}','size':len(self.body),'sha256':hashlib.sha256(self.body).hexdigest()}
            self.payload['assets'][target]={'deb':artifact} if target.startswith('linux') else artifact
    def signed(self):
        return json.dumps({'payload':self.payload,'keyId':'test','signature':base64.b64encode(self.signer.sign(canonical(self.payload))).decode()}).encode()
    def test_platform_and_cpu_are_exact_never_android_or_another_architecture(self):
        for system,machine,key in [('Windows','AMD64','windows-x64'),('Darwin','arm64','macos-arm64'),('Darwin','x86_64','macos-x64'),('Linux','aarch64','linux-arm64')]:
            self.assertEqual(key,platform_key(system,machine,pointer_bits=64))
            update=verify_manifest(self.signed(),self.keys,target=key,image=False)
            self.assertEqual(key,update.platform);self.assertIn(key,update.name);self.assertNotIn('.apk',update.name)
    def test_missing_platform_is_not_substituted(self):
        self.assertIsNone(verify_manifest(self.signed(),self.keys,target='windows-arm64'))
    def test_equal_or_older_version_is_not_offered(self):
        for installed in ('0.11.0','0.12.0','1.0.0'):
            self.assertIsNone(verify_manifest(self.signed(),self.keys,installed=installed,target='windows-x64'))
    def test_unsigned_unknown_key_tampered_and_duplicate_fields_are_refused(self):
        raw=self.signed()
        with self.assertRaises(Exception):verify_manifest(raw,{},target='windows-x64')
        doc=json.loads(raw);doc['payload']['version']='9.0.0'
        with self.assertRaises(Exception):verify_manifest(json.dumps(doc).encode(),self.keys,target='windows-x64')
        with self.assertRaises(Exception):verify_manifest(b'{"payload":{},"payload":{}}',self.keys)
    def test_wrong_channel_tag_host_type_or_size_cannot_be_offered(self):
        mutations=[lambda:self.payload.update(channel='android'),lambda:self.payload.update(tag='v0.11.0'),
          lambda:self.payload['assets']['windows-x64'].update(url='https://attacker.test/Dkord.exe'),
          lambda:self.payload['assets']['windows-x64'].update(name='Dkord-v0.11.0.apk'),
          lambda:self.payload['assets']['windows-x64'].update(size=2**40)]
        original=json.loads(json.dumps(self.payload))
        for mutate in mutations:
            self.payload=json.loads(json.dumps(original));mutate()
            with self.assertRaises(Exception):verify_manifest(self.signed(),self.keys,target='windows-x64')
    def test_compatible_appimage_and_deb_are_selected_separately(self):
        target='linux-x64';name='Dkord-desktop-v0.11.0-linux-x64.AppImage'
        self.payload['assets'][target]['appimage']=dict(self.payload['assets'][target]['deb'],name=name,kind='appimage',url=f'https://github.com/DeepuExplainsAi/dkord/releases/download/desktop-v0.11.0/{name}')
        self.assertEqual('appimage',verify_manifest(self.signed(),self.keys,target=target,image=True).kind)
        self.assertEqual('deb',verify_manifest(self.signed(),self.keys,target=target,image=False).kind)
    def test_download_verifies_size_hash_native_magic_and_keeps_library_files(self):
        update=verify_manifest(self.signed(),self.keys,target='linux-x64',image=False)
        class Response:
            def __enter__(inner):return inner
            def __exit__(inner,*args):pass
            def raise_for_status(inner):pass
            def iter_content(inner,size):yield self.body
        with tempfile.TemporaryDirectory() as temp,patch('dkord_desktop.updates.platform_key',return_value='linux-x64'),patch.dict('os.environ',{},clear=True):
            root=Path(temp);library=root/'library.sqlite3';library.write_text('keep actual user data')
            updater=Updater(root/'updates',self.keys)
            with patch('dkord_desktop.updates.requests.get',return_value=Response()):file=updater.download(update,threading.Event())
            self.assertEqual(self.body,file.read_bytes());self.assertEqual('keep actual user data',library.read_text())
            file.write_bytes(b'X'*len(self.body))
            with self.assertRaises(ValueError):updater.validate_file(file,update)
    def test_mutating_verified_plan_or_unsigned_preview_cannot_launch_native_installer(self):
        update=verify_manifest(self.signed(),self.keys,target='linux-x64',image=False)
        with tempfile.TemporaryDirectory() as temp,patch('dkord_desktop.updates.platform_key',return_value='linux-x64'),patch.dict('os.environ',{},clear=True):
            updater=Updater(Path(temp),self.keys)
            with self.assertRaises(Exception):updater.verify_plan(replace(update,sha256='0'*64))
            with self.assertRaises(Exception):Updater(Path(temp),{}).install(update,Path(temp)/update.name)
            self.assertEqual([],list(Path(temp).iterdir()))
    def test_renamed_apk_is_not_a_native_desktop_installer_even_with_matching_digest(self):
        body=b'PK\x03\x04'+b'not a desktop installer'*100
        self.payload['assets']['windows-x64'].update(size=len(body),sha256=hashlib.sha256(body).hexdigest())
        update=verify_manifest(self.signed(),self.keys,target='windows-x64')
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/update.name;file.write_bytes(body)
            with self.assertRaises(ValueError):Updater.validate_file(file,update)
    def test_loopback_proxy_only_accepts_provider_https_audio_not_arbitrary_urls(self):
        self.assertTrue(valid_audio_url('https://rr1---test.googlevideo.com/videoplayback?itag=140'))
        for url in ('http://rr.googlevideo.com/a','https://googlevideo.com.attacker.test/a','https://localhost/a','file:///etc/passwd','https://user:pass@rr.googlevideo.com/a','https://rr.googlevideo.com:444/a'):
            self.assertFalse(valid_audio_url(url),url)

    def test_appimage_replacement_defers_relaunch_until_release_and_rechecks_bytes(self):
        header=bytearray(64);header[:6]=b'\x7fELF\x02\x01';header[18:20]=(62).to_bytes(2,'little')
        body=bytes(header)+b'native signed fixture'*100
        name='Dkord-desktop-v0.11.0-linux-x64.AppImage'
        self.payload['assets']['linux-x64']['appimage']={'name':name,'kind':'appimage','url':f'https://github.com/DeepuExplainsAi/dkord/releases/download/desktop-v0.11.0/{name}','size':len(body),'sha256':hashlib.sha256(body).hexdigest()}
        update=verify_manifest(self.signed(),self.keys,target='linux-x64',image=True)
        with tempfile.TemporaryDirectory() as tmp,patch('dkord_desktop.updates.platform_key',return_value='linux-x64'):
            root=Path(tmp);target=root/'Installed-Dkord.AppImage';target.write_bytes(b'old app bytes')
            data=root/'user-data';data.mkdir();sentinel=data/'library.sqlite3';sentinel.write_bytes(b'existing user database')
            file=root/name;file.write_bytes(body);updater=Updater(root/'updates',self.keys)
            with patch.dict('os.environ',{'APPIMAGE':str(target)}),patch('dkord_desktop.updates.subprocess.Popen') as launch:
                after_release=updater.install(update,file)
                launch.assert_not_called();self.assertTrue(callable(after_release))
                self.assertEqual(body,target.read_bytes());self.assertEqual(b'existing user database',sentinel.read_bytes())
                # Represents main's post-event-loop / worker-drain / QLockFile-unlock callback.
                after_release();launch.assert_called_once()
                self.assertEqual([str(target.resolve())],launch.call_args.args[0]);self.assertEqual('1',launch.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'])
                target.write_bytes(b'corrupt replacement')
                with self.assertRaises(ValueError):after_release()
                launch.assert_called_once();self.assertEqual(b'existing user database',sentinel.read_bytes())

    def test_windows32_process_on_a_64bit_host_selects_x86_not_host_cpu(self):
        self.assertEqual('windows-x86',platform_key('Windows','AMD64',pointer_bits=32))
        self.assertEqual('windows-x86',platform_key('Windows','x86',pointer_bits=32))
        self.assertEqual('windows-x64',platform_key('Windows','AMD64',pointer_bits=64))
        update=verify_manifest(self.signed(),self.keys,target='windows-x86')
        self.assertEqual('windows-x86',update.platform);self.assertIn('windows-x86.exe',update.name)
        with self.assertRaises(ValueError):platform_key('Linux','x86_64',pointer_bits=32)

    def test_missing_or_wrong_windows32_asset_is_never_replaced_with_x64(self):
        self.payload['assets'].pop('windows-x86')
        self.assertIsNone(verify_manifest(self.signed(),self.keys,target='windows-x86'))
        self.payload['assets']['windows-x86']=self.payload['assets']['windows-x64']
        with self.assertRaises(ValueError):verify_manifest(self.signed(),self.keys,target='windows-x86')

if __name__=='__main__':unittest.main()

class ModernUpdateIdentityTest(unittest.TestCase):
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        from dkord_desktop.updates import UPDATE_DOMAIN
        self.domain=UPDATE_DOMAIN;self.signer=rsa.generate_private_key(public_exponent=65537,key_size=2048)  # ephemeral TEST identity only
        self.keys={'fixture-rsa':{'algorithm':'rsa-pkcs1-sha256','publicKey':base64.b64encode(self.signer.public_key().public_bytes(
            serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).decode(),
            'certificateSha256':hashlib.sha256(b'public certificate fixture only').hexdigest()}}
        self.payload={'format':2,'channel':'desktop','version':'0.11.0','tag':'v0.11.0','assets':{}}
        for target,ext,kind in [('windows-x64','.exe','exe'),('windows-x86','.exe','exe'),('macos-x64','.pkg','pkg'),('macos-arm64','.pkg','pkg'),('linux-x64','.deb','deb'),('linux-arm64','.deb','deb')]:
            name=f'Dkord-desktop-v0.11.0-{target}{ext}'
            artifact={'name':name,'kind':kind,'url':f'https://github.com/DeepuExplainsAi/dkord/releases/download/v0.11.0/{name}','size':2048,'sha256':hashlib.sha256(b'installer fixture').hexdigest()}
            self.payload['assets'][target]={'deb':artifact} if target.startswith('linux') else artifact

    def signed(self,domain=None):
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes
        signature=self.signer.sign((self.domain if domain is None else domain)+canonical(self.payload),padding.PKCS1v15(),hashes.SHA256())
        return json.dumps({'payload':self.payload,'keyId':'fixture-rsa','signature':base64.b64encode(signature).decode()}).encode()

    def test_one_common_android_pc_release_is_still_cpu_os_and_package_exact(self):
        for target in self.payload['assets']:
            update=verify_manifest(self.signed(),self.keys,target=target,image=False)
            self.assertEqual('v0.11.0',update.tag);self.assertEqual(target,update.platform);self.assertNotIn('.apk',update.name)
        self.assertIsNone(verify_manifest(self.signed(),self.keys,target='windows-arm64'))

    def test_signature_is_domain_separated_not_a_raw_android_room_or_generic_signature(self):
        for domain in (b'',b'DKORD-ROOM',b'APK Signature Scheme v2'):
            with self.assertRaises(Exception):verify_manifest(self.signed(domain),self.keys,target='windows-x86')
        raw=json.loads(self.signed());raw['payload']['version']='9.0.0'
        with self.assertRaises(Exception):verify_manifest(json.dumps(raw).encode(),self.keys,target='windows-x86')
        with self.assertRaises(Exception):verify_manifest(self.signed(),{},target='windows-x86')

    def test_algorithm_downgrade_wrong_root_or_format_cannot_be_used(self):
        for algorithm in ('none','ed25519','ecdsa-p256-sha256'):
            keys={'fixture-rsa':dict(self.keys['fixture-rsa'],algorithm=algorithm)}
            with self.assertRaises(Exception):verify_manifest(self.signed(),keys,target='windows-x64')
        self.payload['format']=1
        with self.assertRaises(Exception):verify_manifest(self.signed(),self.keys,target='windows-x64')
        self.payload['format']=2;self.payload['tag']='desktop-v0.11.0'
        with self.assertRaises(Exception):verify_manifest(self.signed(),self.keys,target='windows-x64')

    def test_apk_wrong_cpu_host_or_oversized_package_is_refused_even_with_valid_identity(self):
        original=json.loads(json.dumps(self.payload['assets']['windows-x86']))
        for patching in ({'name':'Dkord-v0.11.0.apk'},{'url':'https://attacker.test/installer.exe'},
                         {'name':'Dkord-desktop-v0.11.0-windows-x64.exe'},{'size':2**40}):
            self.payload['assets']['windows-x86']=original|patching
            with self.assertRaises(Exception):verify_manifest(self.signed(),self.keys,target='windows-x86')

    def test_installed_public_root_is_the_verified_original_apk_identity_not_a_generated_key(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        root=Path(__file__).resolve().parents[1]/'assets'
        receipt=json.loads((root/'update-trust-provenance.json').read_text())
        expected='5e6e923094761325e1ba251ebd8058077934131ed89f293215ce5876da211a61'
        self.assertIs(False,receipt['privateKeyExported']);self.assertEqual('v0.10.0',receipt['verifiedAgainst']['tag'])
        self.assertEqual(expected,receipt['verifiedAgainst']['certificateSha256']);self.assertEqual(receipt['keys'],Updater.production_keys())
        self.assertEqual(1,len(receipt['keys']))
        for key in receipt['keys'].values():
            self.assertEqual(expected,key['certificateSha256']);self.assertEqual('rsa-pkcs1-sha256',key['algorithm'])
            public=serialization.load_der_public_key(base64.b64decode(key['publicKey'],validate=True))
            self.assertIsInstance(public,rsa.RSAPublicKey);self.assertGreaterEqual(public.key_size,2048)

    def test_discovery_finds_the_signed_desktop_manifest_inside_the_common_release_not_the_apk(self):
        raw=self.signed();name='Dkord-desktop-v0.11.0-manifest.json';url='https://github.com/DeepuExplainsAi/dkord/releases/download/v0.11.0/'+name
        releases=[{'tag_name':'v0.11.0','draft':False,'prerelease':False,'assets':[
            {'name':'Dkord-v0.11.0.apk','browser_download_url':url.replace(name,'Dkord-v0.11.0.apk'),'size':10000},
            {'name':name,'browser_download_url':url,'size':len(raw)}]}]
        calls=[]
        class Response:
            def __init__(self,manifest=False):self.manifest=manifest
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def raise_for_status(self):pass
            def json(self):return releases
            def iter_content(self,size):yield raw
        class Session:
            def __init__(self):self.headers={}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def get(self,location,**kwargs):calls.append(location);return Response(location==url)
        with tempfile.TemporaryDirectory() as temp,patch('dkord_desktop.updates.requests.Session',Session):
            update=Updater(Path(temp),self.keys).check()
        self.assertEqual('v0.11.0',update.tag);self.assertEqual(platform_key(),update.platform);self.assertEqual(2,len(calls));self.assertEqual(url,calls[-1])
