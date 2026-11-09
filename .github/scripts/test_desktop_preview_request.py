"""Fresh desktop-preview authorization; never relabel a consumed Android release request."""
import hashlib
import json
import unittest
from validate_desktop_preview_request import BRANCH,REPO,REQUEST,ROOT,TAG,VERSION,validate,validate_changes

class DesktopPreviewRequestTest(unittest.TestCase):
    def setUp(self):
        self.before=hashlib.sha1(b'validated desktop source fixture').hexdigest();self.after=hashlib.sha1(b'preview metadata child fixture').hexdigest()
        self.request={'tag':TAG,'version':VERSION,'branch':BRANCH,'validatedHead':self.before}
        self.event={'ref':'refs/heads/'+BRANCH,'before':self.before,'after':self.after,'repository':{'full_name':REPO},'forced':False,'deleted':False}
        self.context={'event_name':'push','ref':self.event['ref'],'repository':REPO,'sha':self.after,'tag':TAG,'version':VERSION}
    def check(self,request=None,event=None,**changes):
        return validate(self.request if request is None else request,self.event if event is None else event,**(self.context|changes))
    def test_only_fresh_exact_version_branch_and_metadata_child_are_authorized(self):
        self.assertEqual(TAG,self.check());validate_changes(self.before,self.before,[REQUEST.as_posix()])
        self.assertEqual('arena/a6a6bbda-dkord',BRANCH)
    def test_consumed_android_requests_and_unknown_schemas_are_not_authorization(self):
        for version in ('v0.8.2','v0.9.0','v0.9.1','v0.10.0'):
            with self.subTest(version=version),self.assertRaises(ValueError):self.check(request=json.loads((ROOT/f'.github/release-requests/{version}.json').read_text()))
        for request in ([],{},self.request|{'versionCode':14}):
            with self.assertRaises(ValueError):self.check(request=request)
    def test_other_events_refs_repositories_and_tags_are_refused(self):
        for field,value in (('event_name','pull_request'),('event_name','workflow_dispatch'),('ref','refs/heads/main'),('repository','other/fork'),('tag','v0.10.0'),('version','0.10.1')):
            with self.subTest(field=field),self.assertRaises(ValueError):self.check(**{field:value})
        with self.assertRaises(ValueError):self.check(request=self.request|{'branch':'arena/a0209191-dkord'})
        with self.assertRaises(ValueError):self.check(event=self.event|{'repository':{'full_name':'other/fork'}})
    def test_force_delete_changed_parent_and_wrong_after_are_refused(self):
        for changes in ({'forced':True},{'deleted':True},{'before':self.after},{'after':self.before}):
            with self.assertRaises(ValueError):self.check(event=self.event|changes)
        with self.assertRaises(ValueError):self.check(sha='0'*40)
        with self.assertRaises(ValueError):self.check(request=self.request|{'validatedHead':'0'*40})
    def test_publication_push_cannot_include_unvalidated_source_edits(self):
        for parent,paths in ((self.after,[REQUEST.as_posix()]),(self.before,[REQUEST.as_posix(),'desktop/dkord_desktop/ui.py']),(self.before,[])):
            with self.assertRaises(ValueError):validate_changes(self.before,parent,paths)
    def test_native_pr_workflow_stays_read_only_and_publication_is_new_prerelease_only(self):
        native=(ROOT/'.github/workflows/validate-desktop.yml').read_text();flow=(ROOT/'.github/workflows/desktop-preview.yml').read_text()
        for forbidden in ('secrets.','contents: write','gh release'):self.assertNotIn(forbidden,native)
        for required in ('branches: [arena/a6a6bbda-dkord]','paths: [.github/release-requests/desktop-v0.10.0-preview.2.json]',
                         'validate_desktop_preview_request.py','head_sha="$GITHUB_SHA"','--exit-status --interval 30','--source "$GITHUB_SHA"',
                         '--prerelease --latest=false','--target "$GITHUB_SHA"'):
            self.assertIn(required,flow)
        for forbidden in ('secrets.','--clobber','gh release delete','gh release edit','gh run rerun','continue-on-error','pull_request_target:'):
            self.assertNotIn(forbidden,flow)

if __name__=='__main__':unittest.main()
