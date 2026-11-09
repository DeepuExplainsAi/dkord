"""Fresh explicit authorization tests. Historical v0.9.1 metadata/guard stays unchanged."""
import hashlib
import json
from pathlib import Path
import unittest
from validate_release_request_v0101 import BRANCH, CODE, REPOSITORY, REQUEST, ROOT, TAG, app_version, validate, validate_changes

class NewCombinedReleaseRequestTest(unittest.TestCase):
    def setUp(self):
        self.before=hashlib.sha1(b'previous validated release source fixture').hexdigest()
        self.after=hashlib.sha1(b'one metadata-only publication child fixture').hexdigest()
        self.request={'tag':TAG,'versionCode':CODE,'desktopVersion':'0.10.1','branch':BRANCH,'validatedHead':self.before}
        self.event={'ref':'refs/heads/'+BRANCH,'before':self.before,'after':self.after,'repository':{'full_name':REPOSITORY},'forced':False,'deleted':False}
        self.context=dict(event_name='push',ref=self.event['ref'],repository=REPOSITORY,sha=self.after,tag=TAG,version_name=TAG[1:],version_code=CODE,desktop_version='0.10.1')
    def check(self, request=None, event=None, **context):
        return validate(self.request if request is None else request,self.event if event is None else event,**(self.context|context))
    def test_exact_new_authorization_and_prepared_version_agree(self):
        self.assertEqual(TAG,self.check())
        # This new authorization is independently scoped; no historical request is reused.
        self.assertEqual(('0.10.1',15),app_version('versionCode = 15\nversionName = "0.10.1"'))
        self.assertEqual('arena/a6a6bbda-dkord',BRANCH)
    def test_no_pr_dispatch_schedule_or_workflow_run_can_enter_the_push_route(self):
        for name in ('pull_request','pull_request_target','workflow_dispatch','workflow_run','schedule'):
            with self.subTest(name=name),self.assertRaises(ValueError):self.check(event_name=name)
    def test_other_refs_including_consumed_branch_and_main_are_refused(self):
        for ref in ('refs/heads/main','refs/heads/arena/59a2f745-dkord','refs/pull/8/merge','refs/heads/other'):
            with self.subTest(ref=ref),self.assertRaises(ValueError):self.check(ref=ref)
        with self.assertRaises(ValueError):self.check(event=self.event|{'ref':'refs/heads/main'})
    def test_wrong_repository_is_refused_in_both_context_and_event(self):
        with self.assertRaises(ValueError):self.check(repository='other/fork')
        with self.assertRaises(ValueError):self.check(event=self.event|{'repository':{'full_name':'other/fork'}})
    def test_consumed_requests_cannot_publish_old_or_new_version(self):
        for name in ('v0.8.2','v0.9.0','v0.9.1','v0.10.0'):
            request=json.loads((ROOT/f'.github/release-requests/{name}.json').read_text())
            with self.subTest(name=name),self.assertRaises(ValueError):self.check(request=request)
            with self.subTest(name=name),self.assertRaises(ValueError):self.check(request=request,tag=name,version_name=name[1:])
    def test_only_v0101_tag_branch_and_code15_are_accepted(self):
        for context in ({'tag':'v0.9.1'},{'tag':'v0.11.0'},{'version_name':'0.9.1'},{'version_code':13}):
            with self.subTest(context=context),self.assertRaises(ValueError):self.check(**context)
        for request in (self.request|{'tag':'v0.11.0'},self.request|{'branch':'main'}):
            with self.assertRaises(ValueError):self.check(request=request)
    def test_request_code_cannot_be_boolean_string_or_different_integer(self):
        for code in (True,'15',14,16):
            with self.subTest(code=code),self.assertRaises(ValueError):self.check(request=self.request|{'versionCode':code})
    def test_forced_deleted_or_underspecified_push_is_refused(self):
        for field in ('forced','deleted'):
            with self.assertRaises(ValueError):self.check(event=self.event|{field:True})
            event=dict(self.event);event.pop(field)
            with self.assertRaises(ValueError):self.check(event=event)
    def test_recorded_source_must_equal_push_before_and_be_nonzero_sha(self):
        with self.assertRaises(ValueError):self.check(event=self.event|{'before':self.after})
        for value in ('',None,'0'*40,'bad'):
            with self.subTest(value=value),self.assertRaises(ValueError):self.check(request=self.request|{'validatedHead':value})
    def test_release_target_must_be_the_new_push_commit(self):
        for value in (self.before,'0'*40,'bad'):
            with self.subTest(value=value),self.assertRaises(ValueError):self.check(sha=value)
        with self.assertRaises(ValueError):self.check(event=self.event|{'after':self.before})
    def test_unknown_schema_and_nonobject_inputs_are_refused(self):
        for value in ({},[],self.request|{'extra':'not authorized'}):
            with self.subTest(value=value),self.assertRaises(ValueError):self.check(request=value)
        with self.assertRaises(ValueError):self.check(event=[])
    def test_only_a_single_direct_metadata_child_can_request_publication(self):
        validate_changes(self.before,self.before,[REQUEST.as_posix()])
        for parent,changes in ((self.after,[REQUEST.as_posix()]),(self.before,[]),(self.before,[REQUEST.as_posix(),'app/build.gradle.kts']),(self.before,['.github/release-requests/v0.9.1.json'])):
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate_changes(self.before,parent,changes)
    def test_mismatched_phone_pc_versions_are_refused(self):
        with self.assertRaises(ValueError):self.check(desktop_version='0.10.0')
        with self.assertRaises(ValueError):self.check(request=self.request|{'desktopVersion':'0.10.0'})

    def test_publisher_is_a_fresh_route_with_all_identity_proof_gates(self):
        workflow=(ROOT/'.github/workflows/release-v0101.yml').read_text()
        for required in ('branches: [arena/a6a6bbda-dkord]','paths: [.github/release-requests/v0.10.1.json]',
                         'validate_release_request_v0101.py','verify_apk_update.py','verify_desktop_release_artifacts.py',
                         'sign_update_manifest.py','screenshot_proof.py','validate-pr.yml','validate-desktop.yml',
                         'DKORD_KEYSTORE_B64','DKORD_KEYSTORE_PASS','--draft','--latest','snapshot-release',
                         'verify-release','gh run watch','verify_android_install_over.py','assembleDebugAndroidTest'):
            self.assertIn(required,workflow)
        self.assertNotIn('--clobber',workflow);self.assertNotIn('keytool -genkey',workflow)
        self.assertNotIn('gh pr merge',workflow);self.assertNotIn('contents: write', (ROOT/'.github/workflows/validate-desktop.yml').read_text())
