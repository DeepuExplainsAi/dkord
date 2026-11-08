import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('device_summary', Path(__file__).with_name('summarize_device_tests.py'))
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)

class DeviceTestSummaryTest(unittest.TestCase):
    def test_no_reports_cannot_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertFalse(summary.summarize(root, ["Required"])[3])
    def test_missing_required_class_cannot_pass(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'TEST-one.xml').write_text('<testsuite tests="1"><testcase classname="Other" name="ok"/></testsuite>')
            self.assertFalse(summary.summarize(root, ["Required"])[3])
    def test_real_pass_counts_and_required_classes(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'TEST-one.xml').write_text('<testsuite tests="1"><testcase classname="Required" name="ok"/></testsuite>')
            result = summary.summarize(root, ["Required"])
            self.assertTrue(result[3]); self.assertIn("1 passed", result[0])
    def test_failures_are_visible_and_never_pass(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'TEST-one.xml').write_text('<testsuite tests="1" failures="1"><testcase classname="Required" name="broken"><failure message="expected actual AAC"/></testcase></testsuite>')
            result = summary.summarize(root, ["Required"])
            self.assertFalse(result[3]); self.assertIn("Required.broken", result[1][0])
    def test_skipped_device_cases_cannot_pass(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'TEST-one.xml').write_text('<testsuite tests="2" skipped="1"><testcase classname="Required" name="skipped"><skipped/></testcase><testcase classname="Required" name="ok"/></testsuite>')
            self.assertFalse(summary.summarize(root, ["Required"])[3])
