"""Synthetic, ephemeral TEST keys only; real signing exists only in protected CI.

Fixture bytes are NOT distributable native installers. The independent six-host
format/runtime/provenance gate is required before production attestation.
"""
import base64
import datetime
import importlib.util
from pathlib import Path
import tempfile
import unittest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,ec
from cryptography.hazmat.primitives.serialization import pkcs12
from dkord_desktop.updates import verify_manifest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_manifest_signer',ROOT/'scripts/sign_update_manifest.py')
signer=importlib.util.module_from_spec(spec);spec.loader.exec_module(signer)

class ManifestSignerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);self.version='0.10.1';self.source='7'*40
        for target,kinds in signer.KINDS.items():
            for _,extension in kinds:(self.folder/f'Dkord-desktop-v{self.version}-{target}.{extension}').write_bytes(b'EXPLICIT TEST ONLY - NONDISTRIBUTABLE\n'*64)
    def tearDown(self):self.temp.cleanup()
    def identity(self,elliptic=False):
        # This key is test-only, generated in RAM; its encrypted fixture file is
        # temporary and deleted by tearDown. No production key is created/exported.
        key=ec.generate_private_key(ec.SECP256R1()) if elliptic else rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Dkord SYNTHETIC UNIT TEST, NEVER PRODUCTION')])
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(12345)
              .not_valid_before(datetime.datetime(2025,1,1,tzinfo=datetime.timezone.utc)).not_valid_after(datetime.datetime(2045,1,1,tzinfo=datetime.timezone.utc)).sign(key,hashes.SHA256()))
        password='synthetic-fixture-only';path=self.folder/'test-only.p12'
        path.write_bytes(pkcs12.serialize_key_and_certificates(b'test-only',key,cert,None,serialization.BestAvailableEncryption(password.encode())))
        root=dict(algorithm='ecdsa-p256-sha256' if elliptic else 'rsa-pkcs1-sha256',certificateSha256=cert.fingerprint(hashes.SHA256()).hex(),
                  publicKey=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).decode())
        return path,password,{'synthetic-test-only':root}
    def test_original_identity_algorithm_rsa_all_six_targets_and_eight_kinds_verify_in_actual_client(self):
        path,password,keys=self.identity();output=signer.sign(self.folder,self.version,'v'+self.version,self.source,path,password,keys)
        names=[]
        for target in signer.KINDS:
            for image in ((False,True) if target.startswith('linux-') else (False,)):
                update=verify_manifest(output.read_bytes(),keys,installed='0.10.0',target=target,image=image)
                self.assertEqual(self.version,update.version);self.assertEqual('v'+self.version,update.tag);names.append(update.name)
        self.assertEqual(8,len(set(names)))
    def test_p256_manifest_is_domain_separated_and_supported_by_actual_updater(self):
        path,password,keys=self.identity(True);output=signer.sign(self.folder,self.version,'v'+self.version,self.source,path,password,keys)
        self.assertIsNotNone(verify_manifest(output.read_bytes(),keys,installed='0.10.0',target='windows-x86'))
        import json
        raw=json.loads(output.read_bytes());raw['payload']['source']='8'*40
        with self.assertRaises(InvalidSignature):verify_manifest(json.dumps(raw).encode(),keys,installed='0.10.0',target='windows-x86')
    def test_unpinned_identity_cannot_sign_and_already_attested_manifest_is_never_replaced(self):
        path,password,keys=self.identity()
        with self.assertRaises(ValueError):signer.sign(self.folder,self.version,'v'+self.version,self.source,path,password,{})
        output=signer.sign(self.folder,self.version,'v'+self.version,self.source,path,password,keys);before=output.read_bytes()
        with self.assertRaises(FileExistsError):signer.sign(self.folder,self.version,'v'+self.version,self.source,path,password,keys)
        self.assertEqual(before,output.read_bytes())
    def test_wrong_channel_tag_missing_target_and_unbounded_package_are_refused(self):
        for tag in ('v0.10.0','desktop-v0.10.1','../v0.10.1'):
            with self.assertRaises(ValueError):signer.payload(self.folder,self.version,tag,self.source)
        file=self.folder/f'Dkord-desktop-v{self.version}-windows-x86.exe';file.write_bytes(b'too small')
        with self.assertRaises(ValueError):signer.payload(self.folder,self.version,'v'+self.version,self.source)
        file.unlink()
        with self.assertRaises(ValueError):signer.payload(self.folder,self.version,'v'+self.version,self.source)
