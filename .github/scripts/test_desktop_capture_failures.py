"""Only CLI error-report safety mocks; actual capture is exercised by native Qt tests."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'desktop'))
from dkord_desktop.__main__ import capture_ui

def fail(*args):raise RuntimeError('Isolated capture fixture failed')

class CaptureFailureSafetyTest(unittest.TestCase):
    def test_failure_report_is_created_only_for_fresh_capture_destination(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(sys.modules,{'dkord_desktop.capture':SimpleNamespace(capture=fail)}):
            folder=Path(temp)/'new-capture';self.assertEqual(1,capture_ui(None,folder))
            report=folder/'capture-error.txt';self.assertIn('Isolated capture fixture failed',report.read_text())
            report.write_text('KEEP prior user capture report');before={p.name:p.read_bytes() for p in folder.iterdir()}
            self.assertEqual(1,capture_ui(None,folder));self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir()})
    def test_nonempty_user_folder_and_non_directory_are_never_modified_to_report_errors(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(sys.modules,{'dkord_desktop.capture':SimpleNamespace(capture=fail)}):
            folder=Path(temp);file=folder/'original-user-file';file.write_bytes(b'KEEP')
            self.assertEqual(1,capture_ui(None,folder));self.assertEqual([file],list(folder.iterdir()));self.assertEqual(b'KEEP',file.read_bytes())
            self.assertEqual(1,capture_ui(None,file));self.assertEqual(b'KEEP',file.read_bytes())

if __name__=='__main__':unittest.main()
