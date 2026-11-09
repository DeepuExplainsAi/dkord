import struct
import unittest
from apk_public_identity import apk_certificates,leaf_certificates,MAGIC


def lp(value):return struct.pack('<I',len(value))+value

def block(certificate=b'PUBLIC certificate fixture'):
    signed=lp(b'digests fixture')+lp(lp(certificate))+lp(b'attributes fixture')
    signer=lp(signed)+lp(b'signature fixture')+lp(b'public key fixture')
    return lp(lp(signer))

def apk(value=None,scheme=0x7109871a):
    value=block() if value is None else value
    pair=struct.pack('<I',scheme)+value;pair=struct.pack('<Q',len(pair))+pair
    size=len(pair)+24;signature=struct.pack('<Q',size)+pair+struct.pack('<Q',size)+MAGIC
    prefix=b'PK\x03\x04isolated parser fixture NOT a verified APK'
    central=len(prefix)+len(signature);directory=b'PK\x01\x02directory fixture'
    return prefix+signature+directory+struct.pack('<4s4H2IH',b'PK\x05\x06',0,0,1,1,len(directory),central,0)

class PublicApkIdentityReaderTest(unittest.TestCase):
    def test_v2_v3_and_v31_public_leaf_parsing_only_not_signature_verification(self):
        for scheme in (0x7109871a,0xf05368c0,0x1b93ad61):
            self.assertEqual([b'PUBLIC certificate fixture'],apk_certificates(apk(scheme=scheme)))
    def test_unknown_signature_schemes_or_missing_blocks_are_refused(self):
        for value in (b'',apk(scheme=1),apk().replace(MAGIC,b'not a valid sig!!')):
            with self.assertRaises(ValueError):apk_certificates(value)
    def test_truncated_nested_identity_lengths_empty_certificates_and_suffixes_are_refused(self):
        for value in (b'',b'\xff'*4,block()[:-1],block()+b'extra',block(b'')):
            with self.assertRaises(ValueError):leaf_certificates(value)
    def test_bounds_and_eocd_comments_are_checked(self):
        raw=apk()
        for value in (raw[:-1],raw+b'unexpected trailing bytes',raw[:-22]+b'PK\x05\x06'+b'\xff'*18):
            with self.assertRaises(ValueError):apk_certificates(value)
        comment=b'a PK\x05\x06 inside ZIP comment'
        self.assertEqual([b'PUBLIC certificate fixture'],apk_certificates(raw[:-2]+struct.pack('<H',len(comment))+comment))
