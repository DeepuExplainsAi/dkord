"""Offline byte/schema contracts, not a substitute for executed Windows32 CI."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'desktop'))
from dkord_desktop.platforms import platform_key
from dkord_desktop.binaries import pe_architecture,require_pe_architecture

class DesktopX86Test(unittest.TestCase):
    def test_wow64_uses_installed_pointer_width_not_host_machine(self):
        for cpu in ('AMD64','x86','i386','arm64'):
            self.assertEqual('windows-x86',platform_key('Windows',cpu,32))
        self.assertEqual('windows-x64',platform_key('Windows','AMD64',64))
    def test_unbuilt_platforms_and_pointer_widths_are_never_silently_substituted(self):
        for os,cpu,bits in (('Linux','x86_64',32),('Windows','arm64',64),('Darwin','x86',32),('Windows','AMD64',16)):
            with self.assertRaises(ValueError):platform_key(os,cpu,bits)
    def test_real_pe_machine_header_not_file_name_decides_the_architecture(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'claimed-windows-x86.exe'
            for machine,expected in ((0x14c,'x86'),(0x8664,'x64'),(0xaa64,'arm64')):
                data=bytearray(256);data[:2]=b'MZ';struct.pack_into('<I',data,60,128);data[128:134]=b'PE\0\0'+struct.pack('<H',machine);file.write_bytes(data)
                self.assertEqual(expected,pe_architecture(file));require_pe_architecture(file,expected)
                if expected!='x86':
                    with self.assertRaises(ValueError):require_pe_architecture(file,'x86')
    def test_an_apk_or_malformed_pe_cannot_pass_native_architecture_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'Dkord.exe'
            for data in (b'PK\3\4'+bytes(100),b'MZ'+bytes(100),b'MZ'+bytes(58)+struct.pack('<I',2**31)+bytes(100)):
                file.write_bytes(data)
                with self.assertRaises(ValueError):pe_architecture(file)
    def test_modern_win32_codec_is_source_pinned_and_does_not_fetch_a_2019_binary(self):
        text=(ROOT/'desktop/packaging/build_ffmpeg_x86.py').read_text()
        self.assertIn("VERSION='8.1.3'",text)
        self.assertIn("ARCHIVE_SHA256='a406fe831cbb605f5fe50e43eb566e502ae63ff3b3206bfa744e4b31b8bb73ac'",text)
        for required in ('--toolchain=msvc','--arch=x86','--disable-network','--enable-protocol=file,pipe','--enable-bsf=av1_metadata','pcm_s16be','require_pe_architecture(binary,\'x86\')','COPYING.GPLv3'):
            self.assertIn(required,text)
        self.assertNotIn('ffmpeg-win32-v4.2.2.exe',text)
    def test_x86_shortcuts_and_install_payload_do_not_overwrite_existing_x64(self):
        text=(ROOT/'desktop/packaging/windows.iss').read_text()
        for expected in ('AppId=app.dkord.desktop.x86','AppId=app.dkord.desktop\n','Dkord-x86','ShortcutName "Dkord (32-bit)"','ShortcutName "Dkord"','ArchitecturesAllowed=x86compatible'):
            self.assertIn(expected,text)
        self.assertNotIn('[UninstallDelete]',text)

if __name__=='__main__':unittest.main()
