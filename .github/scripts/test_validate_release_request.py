"""Offline metadata/trigger tests; never access a signing key or dispatch a workflow."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from validate_release_request import BRANCH, CODE, REPOSITORY, REQUEST, ROOT, TAG, app_version, validate


class ReleaseRequestTest(unittest.TestCase):
    def setUp(self):
        self.before = '174750b1cfcf7aa578d2190d0838d276d80b0cb2'
        self.after = hashlib.sha1(b'new release-request commit fixture').hexdigest()
        self.request = {'tag': TAG, 'versionCode': CODE, 'branch': BRANCH, 'validatedHead': self.before}
        self.event = {'ref': f'refs/heads/{BRANCH}', 'before': self.before, 'after': self.after,
                      'repository': {'full_name': REPOSITORY}, 'forced': False, 'deleted': False}
        self.context = dict(event_name='push', ref=self.event['ref'], repository=REPOSITORY,
                            sha=self.after, tag=TAG, version_name='0.8.2', version_code=CODE)

    def check(self, request=None, event=None, **context):
        return validate(self.request if request is None else request, self.event if event is None else event,
                        **(self.context | context))

    def test_exact_authorized_request_is_valid_without_touching_signing_or_network(self):
        self.assertEqual(TAG, self.check())

    def test_pr_or_other_event_cannot_enter_the_trusted_push_release_route(self):
        for event in ('pull_request', 'pull_request_target', 'workflow_run', 'workflow_dispatch'):
            with self.subTest(event=event), self.assertRaises(ValueError):
                self.check(event_name=event)

    def test_main_and_other_branches_are_rejected(self):
        for ref in ('refs/heads/main', 'refs/heads/another', 'refs/pull/7/merge'):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                self.check(ref=ref)
        event = self.event | {'ref': 'refs/heads/main'}
        with self.assertRaises(ValueError):
            self.check(event=event)

    def test_other_repository_or_fork_cannot_request_a_release(self):
        with self.assertRaises(ValueError):
            self.check(repository='other/repository')
        event = self.event | {'repository': {'full_name': 'other/repository'}}
        with self.assertRaises(ValueError):
            self.check(event=event)

    def test_only_the_authorized_tag_and_application_version_are_accepted(self):
        for context in ({'tag': 'v0.8.1'}, {'tag': 'v0.8.3'}, {'version_name': '0.8.3'}, {'version_code': 10}):
            with self.subTest(context=context), self.assertRaises(ValueError):
                self.check(**context)
        request = self.request | {'tag': 'v0.8.3'}
        with self.assertRaises(ValueError):
            self.check(request=request)

    def test_request_code_must_be_the_authorized_integer_not_a_string_or_boolean(self):
        for code in (10, 12, '11', True):
            with self.subTest(code=code), self.assertRaises(ValueError):
                self.check(request=self.request | {'versionCode': code})

    def test_force_push_or_deletion_cannot_trigger_publication(self):
        for flag in ('forced', 'deleted'):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.check(event=self.event | {flag: True})
        event = copy.deepcopy(self.event); event.pop('forced')
        with self.assertRaises(ValueError):
            self.check(event=event)

    def test_push_must_start_from_the_recorded_validated_head(self):
        with self.assertRaises(ValueError):
            self.check(event=self.event | {'before': self.after})
        for sha in ('', 'not-a-sha', '0' * 40):
            with self.subTest(sha=sha), self.assertRaises(ValueError):
                self.check(request=self.request | {'validatedHead': sha})

    def test_target_must_be_the_new_push_commit_not_an_old_or_different_revision(self):
        for sha in (self.before, '0' * 40, 'not-a-sha'):
            with self.subTest(sha=sha), self.assertRaises(ValueError):
                self.check(sha=sha)
        with self.assertRaises(ValueError):
            self.check(event=self.event | {'after': self.before})

    def test_metadata_schema_refuses_missing_extra_or_non_object_fields(self):
        for request in ({}, [], self.request | {'unexpected': 'metadata'}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.check(request=request)
        with self.assertRaises(ValueError):
            self.check(event=[])

    def test_app_version_is_parsed_from_real_gradle_assignments(self):
        self.assertEqual(('0.8.2', 11), app_version('versionCode = 11\nversionName = "0.8.2"\n'))
        for source in ('', 'versionCode = 11', 'versionName = "0.8.2"',
                       'versionCode = 11\nversionCode = 12\nversionName = "0.8.2"'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                app_version(source)

    def test_committed_request_is_only_the_narrow_authorized_metadata(self):
        request = json.loads((ROOT / REQUEST).read_text(encoding='utf-8'))
        self.assertEqual(self.request, request)


if __name__ == '__main__':
    unittest.main()
