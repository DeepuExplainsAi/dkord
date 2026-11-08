"""Schema/hash corruption fixtures, explicitly NOT screenshots or executed Windows proof."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('screenshot_proof',ROOT/'desktop/packaging/screenshot_proof.py')
proof_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof_module)

def png():
    def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',940,640,8,0,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes(940))*640))+chunk(b'IEND',b'')

class DesktopScreenshotProofTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=hashlib.sha1(b'UNIT TEST ONLY; not Windows screenshot provenance').hexdigest();data=png()
        self.proof={'format':1,'application':'Dkord','version':'0.10.0','platform':'windows-x86','os':'Windows','python_bits':32,'qt_binding':'PyQt5','qt_version':'5.15.2','frozen':True,'source':self.source,'images':[]}
        for name in ('windows-x86-player.png','windows-x86-studio.png'):
            (self.root/name).write_bytes(data);self.proof['images'].append({'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'width':940,'height':640})
    def tearDown(self):self.temp.cleanup()
    def run_proof(self,proof=None,source=None):
        (self.root/'windows-x86-screenshot-proof.json').write_text(json.dumps(self.proof if proof is None else proof))
        with contextlib.redirect_stdout(io.StringIO()) as out:proof_module.main(self.root,self.source if source is None else source,False)
        self.assertEqual('',out.getvalue())
    def test_valid_synthetic_unit_fixture_checks_silently_without_encoding_private_files(self):self.run_proof()
    def test_wrong_source_version_os_process_binding_and_unfrozen_app_are_rejected(self):
        for key,value in (('source','0'*40),('version','9.0.0'),('os','Linux'),('python_bits',64),('platform','windows-x64'),('qt_binding','PyQt6'),('qt_version','6.10.2'),('frozen',False)):
            with self.subTest(key=key),self.assertRaises(AssertionError):self.run_proof(self.proof|{key:value})
        with self.assertRaises(AssertionError):self.run_proof(source='f'*40)
    def test_missing_duplicate_and_traversal_image_names_are_rejected(self):
        for names in ([],['windows-x86-player.png']*2,['../../private.png','windows-x86-studio.png']):
            altered=copy.deepcopy(self.proof);altered['images']=[dict(self.proof['images'][0],name=x) for x in names]
            with self.assertRaises(AssertionError):self.run_proof(altered)
    def test_image_hash_size_and_recorded_dimensions_are_enforced(self):
        for key,value in (('sha256','f'*64),('bytes',1),('width',0),('height',641)):
            altered=copy.deepcopy(self.proof);altered['images'][0][key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):self.run_proof(altered)
        file=self.root/'windows-x86-player.png';file.write_bytes(file.read_bytes()+b'CORRUPT')
        with self.assertRaises(AssertionError):self.run_proof()

if __name__=='__main__':unittest.main()
