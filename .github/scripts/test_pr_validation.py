"""Offline safety checks for automatic PR validation and its real-JUnit report summary.

Fixtures exercise the Python reporter, not Android. Actual Kotlin tests still run only in Actions.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / '.github/workflows/validate-pr.yml').read_text(encoding='utf-8')
REPORTER = textwrap.dedent(WORKFLOW.split("python3 - <<'PY'\n", 1)[1].split('\n          PY', 1)[0])


class PrValidationSafetyTest(unittest.TestCase):
    def test_pr_validation_runs_for_draft_pr_updates_with_read_only_permissions(self):
        self.assertIn('  pull_request:\n    branches: [main]', WORKFLOW)
        self.assertIn('types: [opened, synchronize, reopened, ready_for_review]', WORKFLOW)
        self.assertIn('permissions:\n  contents: read\n', WORKFLOW)
        self.assertIn('persist-credentials: false', WORKFLOW)
        self.assertIn('group: pr-android-${{ github.event.pull_request.number }}', WORKFLOW)
        self.assertIn('cancel-in-progress: true', WORKFLOW)
        self.assertNotIn('github.event.pull_request.draft', WORKFLOW)
        self.assertNotRegex(WORKFLOW, r'(?m)^\s+(?:push|pull_request_target|schedule):')

    def test_pr_validation_cannot_use_signing_secrets_or_publish_an_installer(self):
        for forbidden in ('secrets.', 'DKORD_KEYSTORE', 'GH_TOKEN', 'contents: write',
                          'gh release', 'git push', 'app/build/outputs/apk', 'pull_request_target'):
            self.assertNotIn(forbidden, WORKFLOW)
        self.assertIn('name: pr-android-unit-test-reports', WORKFLOW)
        self.assertIn('app/build/test-results/testDebugUnitTest/', WORKFLOW)
        self.assertIn('app/build/reports/tests/testDebugUnitTest/', WORKFLOW)
        self.assertIn('if: always()', WORKFLOW)

    def test_full_android_suite_and_apk_compile_are_mandatory_not_a_static_check_substitute(self):
        self.assertIn("python3 -B -m unittest discover -s .github/scripts -p 'test_*.py' -v", WORKFLOW)
        self.assertIn('id: android_build\n        run: |\n          set -o pipefail\n          ./gradlew testDebugUnitTest assembleDebug --stacktrace', WORKFLOW)
        self.assertIn('2>&1 | tee "$RUNNER_TEMP/dkord-android-build.log"', WORKFLOW)
        self.assertNotIn('|| true', WORKFLOW)
        self.assertNotIn('continue-on-error:', WORKFLOW)
        self.assertNotIn('-x test', WORKFLOW)
        self.assertIn("ANDROID_BUILD_OUTCOME: ${{ steps.android_build.outcome }}", WORKFLOW)
        self.assertIn("glob('TEST-*.xml')", REPORTER)
        self.assertNotIn('@Test', REPORTER)
        self.assertNotIn('src/test', REPORTER)


class AndroidReportSummaryTest(unittest.TestCase):
    def report(self, outcome='success', reports=()):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xml = root / 'app/build/test-results/testDebugUnitTest'
            xml.mkdir(parents=True)
            for index, report in enumerate(reports):
                (xml / f'TEST-Fixture{index}.xml').write_text(report, encoding='utf-8')
            summary = root / 'summary.md'
            result = subprocess.run([sys.executable, '-B', '-c', REPORTER], cwd=root,
                                    env={'ANDROID_BUILD_OUTCOME': outcome,
                                         'GITHUB_STEP_SUMMARY': str(summary),
                                         'PR_HEAD_SHA': 'fixture-pr-head',
                                         'GITHUB_SHA': 'fixture-merge-commit'},
                                    text=True, capture_output=True, timeout=10)
            return result, summary.read_text(encoding='utf-8') if summary.exists() else ''

    def test_counts_are_actual_junit_xml_totals_not_source_declarations(self):
        result, summary = self.report(reports=(
            '<testsuite tests="6" failures="0" errors="0" skipped="1"/>',
            '<testsuite tests="4" failures="0" errors="0" skipped="1"/>',
        ))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('10 JUnit test cases: 8 passed, 0 failed, 0 errors, 2 skipped', result.stdout)
        self.assertIn('2 JUnit XML reports', summary)
        self.assertIn('`fixture-pr-head`', summary)
        self.assertIn('`fixture-merge-commit`', summary)
        self.assertIn('No release/tag or installable APK artifact is published.', summary)

    def test_a_successful_build_without_junit_reports_is_rejected(self):
        result, summary = self.report()
        self.assertNotEqual(0, result.returncode)
        self.assertIn('validation is not established', summary)

    def test_failed_compilation_without_reports_is_not_reported_as_passing_tests(self):
        result, summary = self.report(outcome='failure')
        self.assertEqual(0, result.returncode)
        self.assertIn('No Android unit-test reports generated', summary)
        self.assertNotIn('passed', summary)

    def test_test_failures_cannot_be_hidden_by_a_successful_build_status(self):
        result, summary = self.report(reports=('<testsuite tests="4" failures="1" errors="0" skipped="0"/>',))
        self.assertNotEqual(0, result.returncode)
        self.assertIn('1 failed', summary)

    def test_test_errors_cannot_be_hidden_by_a_successful_build_status(self):
        result, summary = self.report(reports=('<testsuite tests="4" failures="0" errors="1" skipped="0"/>',))
        self.assertNotEqual(0, result.returncode)
        self.assertIn('1 errors', summary)

    def test_all_skipped_tests_cannot_establish_android_validation(self):
        result, _ = self.report(reports=('<testsuite tests="4" failures="0" errors="0" skipped="4"/>',))
        self.assertNotEqual(0, result.returncode)

    def test_malformed_reports_are_not_counted_as_success(self):
        result, _ = self.report(reports=('<testsuite',))
        self.assertNotEqual(0, result.returncode)


if __name__ == '__main__':
    unittest.main()
