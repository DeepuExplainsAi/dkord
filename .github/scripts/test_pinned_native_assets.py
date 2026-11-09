"""Transport/hash fixtures only; no dependency downloads, tests or installers retried."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('pinned_native_assets',ROOT/'desktop/packaging/pinned_assets.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)

class PinnedNativeAssetTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name);self.output=self.folder/'runtime';self.content=b'EXPLICIT SYNTHETIC DEPENDENCY BYTES\n'*64;self.sha=hashlib.sha256(self.content).hexdigest()
    def success(self,command,**kwargs):
        self.assertIn('Accept: application/octet-stream',command)
        kwargs['stdout'].write(self.content);return SimpleNamespace(returncode=0,stderr=b'')
    def download(self):return assets.download_asset('AppImage/type2-runtime',657374641,self.output,self.sha)
    def test_exact_asset_identity_and_digest_required_without_overwrite(self):
        with patch.object(assets.subprocess,'run',side_effect=self.success) as run:self.assertEqual(self.output,self.download())
        self.assertEqual(self.content,self.output.read_bytes());self.assertEqual(1,run.call_count)
        with patch.object(assets.subprocess,'run') as run,self.assertRaises(ValueError):self.download()
        run.assert_not_called()
    def test_only_bounded_transient_transport_errors_retry(self):
        calls=[]
        def run(command,**kwargs):
            calls.append(command)
            if len(calls)==1:return SimpleNamespace(returncode=1,stderr=b'HTTP 504 Gateway Time-out')
            return self.success(command,**kwargs)
        with patch.object(assets.subprocess,'run',side_effect=run),patch.object(assets.time,'sleep') as sleep:self.download()
        self.assertEqual(2,len(calls));sleep.assert_called_once_with(2)
    def test_hash_mismatch_auth_or_not_found_never_retry_or_leave_a_promoted_file(self):
        with patch.object(assets.subprocess,'run',side_effect=self.success) as run,self.assertRaises(ValueError):
            assets.download_asset('AppImage/type2-runtime',657374641,self.output,'1'*64)
        self.assertEqual(1,run.call_count);self.assertFalse(self.output.exists())
        for error in (b'HTTP 403 Forbidden',b'HTTP 404 Not Found'):
            with patch.object(assets.subprocess,'run',return_value=SimpleNamespace(returncode=1,stderr=error)) as run,self.assertRaises(RuntimeError):self.download()
            self.assertEqual(1,run.call_count);self.assertFalse(self.output.exists())
    def test_transient_failures_stop_after_three_attempts(self):
        with patch.object(assets.subprocess,'run',side_effect=subprocess.TimeoutExpired('synthetic-download',90)) as run,patch.object(assets.time,'sleep'),self.assertRaises(RuntimeError):self.download()
        self.assertEqual(3,run.call_count);self.assertFalse(self.output.exists())
    def test_native_packages_use_pinned_runtime_and_fixed_mac_install_location(self):
        source=(ROOT/'desktop/packaging/build.py').read_text()
        for text in ('--runtime-file','APPIMAGE_RUNTIME_SOURCE','fedfad51acc2860b2916a1eef32ba4a500ff31ef','BundleIsRelocatable','--component-plist'):
            self.assertIn(text,source)
        main=source.split('def main():')[1]
        self.assertLess(main.index('with baseline_session'),main.index('freeze(node)'))
        self.assertIn("entry['BundleIsRelocatable']=False",source)
        self.assertNotIn('urlretrieve',source)
