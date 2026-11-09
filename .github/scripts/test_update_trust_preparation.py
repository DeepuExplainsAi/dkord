import hashlib
from pathlib import Path
import unittest
from validate_update_trust_preparation import BRANCH, REPO, REQUEST, PURPOSE, validate, validate_changes

ROOT=Path(__file__).resolve().parents[2]
class PublicUpdateTrustPreparationTest(unittest.TestCase):
    def setUp(self):
        self.before=hashlib.sha1(b'public preparation parent fixture').hexdigest();self.after=hashlib.sha1(b'public preparation child fixture').hexdigest()
        self.request=dict(purpose=PURPOSE,version='0.10.1',branch=BRANCH,preparedHead=self.before)
        self.event=dict(ref='refs/heads/'+BRANCH,before=self.before,after=self.after,repository={'full_name':REPO},forced=False,deleted=False)
        self.context=dict(event_name='push',ref=self.event['ref'],repository=REPO,sha=self.after)
    def check(self,request=None,event=None,**kwargs):
        return validate(self.request if request is None else request,self.event if event is None else event,**(self.context|kwargs))
    def test_exact_fresh_public_only_request_and_single_metadata_child(self):
        self.assertEqual(self.before,self.check());validate_changes(self.before,self.before,[str(REQUEST)])
    def test_no_pr_dispatch_other_repo_branch_or_replay_can_read_the_identity(self):
        for change in ({'event_name':'pull_request'},{'event_name':'workflow_dispatch'},{'ref':'refs/heads/main'},{'repository':'other/fork'},{'sha':self.before}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.check(**change)
        for change in ({'forced':True},{'deleted':True},{'before':self.after},{'after':self.before}):
            with self.assertRaises(ValueError):self.check(event=self.event|change)
    def test_wrong_purpose_version_schema_or_key_export_is_refused(self):
        for request in (self.request|{'purpose':'export-private-key'},self.request|{'version':'0.10.0'},self.request|{'includePrivateKey':True},{},[]):
            with self.assertRaises(ValueError):self.check(request=request)
    def test_preparation_cannot_smuggle_code_changes_or_an_older_parent(self):
        for parent,changes in ((self.after,[str(REQUEST)]),(self.before,[str(REQUEST),'app/build.gradle.kts']),(self.before,[])):
            with self.assertRaises(ValueError):validate_changes(self.before,parent,changes)
    def test_workflow_is_read_only_and_exports_no_private_key_or_new_credentials(self):
        flow=(ROOT/'.github/workflows/prepare-update-trust.yml').read_text()
        self.assertIn('contents: read',flow);self.assertIn('validate_update_trust_preparation.py',flow)
        self.assertIn('public-output/',flow);self.assertNotIn('contents: write',flow);self.assertNotIn('secrets.',flow)
        for forbidden in ('gh release create','gh secret set','-genkeypair','continue-on-error','workflow_dispatch:'):
            self.assertNotIn(forbidden,flow)
        source=(ROOT/'.github/scripts/export_existing_update_trust.py').read_text()
        self.assertIn('certificates(apksigner, apk)',source);self.assertIn('apk_certificates(apk_bytes)',source)
        self.assertIn("'privateKeyExported': False",source);self.assertNotIn('load_key_and_certificates',source)
