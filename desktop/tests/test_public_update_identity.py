"""Execute the public-certificate exporter with synthetic TEST certs, never a real signing key."""
import base64
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT=Path(__file__).resolve().parents[2]

class PublicUpdateIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Pinned certificate-receipt tooling is not part of the application's API.
        sys.path.insert(0,str(ROOT/'.github/scripts'))
        try:
            import export_existing_update_trust
            cls.exporter=export_existing_update_trust
        finally:sys.path.pop(0)
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)  # test-only, in-memory
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Ephemeral public-root test')])
        cls.certificate=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1)
            .not_valid_before(datetime(2026,1,1,tzinfo=timezone.utc)).not_valid_after(datetime(2030,1,1,tzinfo=timezone.utc))
            .sign(key,hashes.SHA256()).public_bytes(serialization.Encoding.DER))
        lp=lambda data:struct.pack('<I',len(data))+data
        signed=lp(b'digests NOT a real APK')+lp(lp(cls.certificate))+lp(b'attributes')
        value=lp(lp(lp(signed)+lp(b'NOT a real signature')+lp(b'public key fixture')))
        pair=struct.pack('<I',0x7109871a)+value;pair=struct.pack('<Q',len(pair))+pair;size=len(pair)+24
        signature=struct.pack('<Q',size)+pair+struct.pack('<Q',size)+b'APK Sig Block 42'
        prefix=b'PK\x03\x04synthetic parser fixture';directory=b'PK\x01\x02fixture'
        cls.apk=prefix+signature+directory+struct.pack('<4s4H2IH',b'PK\x05\x06',0,0,1,1,len(directory),len(prefix)+len(signature),0)

    def test_public_root_export_uses_the_actual_crypto_api_and_only_a_verified_leaf(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);apk=root/'SYNTHETIC.apk';apk.write_bytes(self.apk);output=root/'public.json'
            digest=hashlib.sha256(self.certificate).hexdigest()
            with patch.object(self.exporter,'APK_SHA256',hashlib.sha256(self.apk).hexdigest()),patch.object(self.exporter,'certificates',return_value=(digest,)) as verifier:
                self.exporter.export(apk,root/'mock-apksigner',output)
            verifier.assert_called_once();receipt=json.loads(output.read_text())
            self.assertIs(False,receipt['privateKeyExported']);self.assertEqual(digest,receipt['verifiedAgainst']['certificateSha256'])
            key=next(iter(receipt['keys'].values()));self.assertEqual('rsa-pkcs1-sha256',key['algorithm'])
            self.assertIsInstance(serialization.load_der_public_key(base64.b64decode(key['publicKey'],validate=True)),rsa.RSAPublicKey)
            self.assertEqual({'SYNTHETIC.apk','public.json'},{path.name for path in root.iterdir()})

    def test_wrong_immutable_apk_hash_or_signer_cannot_export_an_update_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);apk=root/'SYNTHETIC.apk';apk.write_bytes(self.apk);output=root/'must-not-exist.json'
            with patch.object(self.exporter,'certificates',return_value=('invalid certificate digest',)):
                with self.assertRaises(ValueError):self.exporter.export(apk,root/'mock-apksigner',output)
                with patch.object(self.exporter,'APK_SHA256',hashlib.sha256(self.apk).hexdigest()):
                    with self.assertRaises(ValueError):self.exporter.export(apk,root/'mock-apksigner',output)
            self.assertFalse(output.exists())
