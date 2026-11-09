"""Synthetic finalization guards only; no network, signing, emulator or publication."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import finalize_v0101 as finish


class ExistingDraftFinalizationTest(unittest.TestCase):
    def setUp(self):
        self.before='6'*40;self.after='7'*40
        self.request=dict(tag=finish.TAG,source=finish.SOURCE,releaseId=finish.RELEASE_ID,publisherRun=finish.PUBLICATION_RUN,branch=finish.BRANCH,safetyHead=self.before)
        self.env=dict(GITHUB_REPOSITORY=finish.REPO,GITHUB_EVENT_NAME='push',GITHUB_REF='refs/heads/'+finish.BRANCH,GITHUB_SHA=self.after)
        self.event=dict(ref=self.env['GITHUB_REF'],before=self.before,after=self.after,forced=False,deleted=False,repository=dict(full_name=finish.REPO))
        self.run=dict(id=finish.PUBLICATION_RUN,head_sha=finish.SOURCE,head_branch=finish.BRANCH,event='push',path='.github/workflows/release-v0101.yml',status='completed',conclusion='failure')
        self.steps=[dict(name=name,status='completed',conclusion='success') for name in sorted(finish.REQUIRED_STEPS)]
        self.steps.extend([dict(name=finish.FAILED_DRAFT_STEP,status='completed',conclusion='failure'),dict(name='Publish the verified new Android and PC update without replacing any old release',status='completed',conclusion='skipped')])
        self.jobs=[dict(id=finish.PUBLICATION_JOB,status='completed',steps=self.steps)]
        self.receipt=dict(format=1,package='app.dkord',baselineTag='v0.10.0',fromVersionCode=14,toVersionCode=15,source=finish.SOURCE,sameUid=True,noUninstall=True,noDataReset=True,realRoom=True,settings=True,queue=True,privateDownload=True,mediaStoreExport=True,studioProjectAndSourceBytes=True)

    def check(self,request=None,event=None,env=None,parent=None,changes=None,source_changes=None):
        finish.validate_request(self.request if request is None else request,self.event if event is None else event,self.env if env is None else env,
            self.before if parent is None else parent,[finish.REQUEST] if changes is None else changes,
            list(finish.ALLOWED_FINALIZATION_CHANGES) if source_changes is None else source_changes)

    def test_exact_existing_draft_direct_metadata_child_and_publication_only_fix_are_allowed(self):
        self.check();finish.validate_publication_proof(self.run,self.jobs);finish.validate_upgrade_receipt(self.receipt)
        self.assertEqual(20,len(finish.ASSET_IDS));self.assertEqual(20,len(finish.expected_names()))
        self.assertEqual('e0e925a674f106f6291731f5b143d3800a476cd3',finish.SOURCE)

    def test_other_drafts_sources_repositories_refs_events_and_forced_pushes_are_refused(self):
        for request in (self.request|{'releaseId':True},self.request|{'releaseId':123},self.request|{'source':'8'*40},self.request|{'tag':'v0.10.0'},self.request|{'extra':'not authorized'}):
            with self.subTest(request=request),self.assertRaises(ValueError):self.check(request=request)
        for env in (self.env|{'GITHUB_EVENT_NAME':'pull_request'},self.env|{'GITHUB_EVENT_NAME':'workflow_dispatch'},self.env|{'GITHUB_REF':'refs/heads/main'},self.env|{'GITHUB_REPOSITORY':'other/fork'}):
            with self.subTest(env=env),self.assertRaises(ValueError):self.check(env=env)
        for field in ('forced','deleted'):
            with self.assertRaises(ValueError):self.check(event=self.event|{field:True})

    def test_code_changes_non_direct_children_and_any_product_change_since_original_source_refuse_reuse(self):
        for parent,changes in (('8'*40,[finish.REQUEST]),(self.before,[]),(self.before,[finish.REQUEST,'README.md'])):
            with self.subTest(parent=parent,changes=changes),self.assertRaises(ValueError):self.check(parent=parent,changes=changes)
        for path in ('app/build.gradle.kts','app/src/main/java/app/dkord/ui/App.kt','desktop/assets/update-keys.json','desktop/dkord_desktop/ui.py','desktop/packaging/build.py'):
            with self.subTest(path=path),self.assertRaises(ValueError):self.check(source_changes=[finish.REQUEST,path])

    def test_every_original_signing_test_install_over_and_upload_gate_must_have_passed(self):
        for name in finish.REQUIRED_STEPS:
            jobs=copy.deepcopy(self.jobs)
            next(step for step in jobs[0]['steps'] if step['name']==name)['conclusion']='skipped'
            with self.subTest(name=name),self.assertRaises(ValueError):finish.validate_publication_proof(self.run,jobs)
        for change in ({'head_sha':'8'*40},{'id':123},{'event':'pull_request'},{'conclusion':'success'}):
            with self.subTest(change=change),self.assertRaises(ValueError):finish.validate_publication_proof(self.run|change,self.jobs)

    def test_unexplained_failure_or_already_published_run_or_duplicate_steps_cannot_finalize(self):
        jobs=copy.deepcopy(self.jobs);jobs[0]['steps'].append(dict(name='An unrelated failing step',status='completed',conclusion='failure'))
        with self.assertRaises(ValueError):finish.validate_publication_proof(self.run,jobs)
        jobs=copy.deepcopy(self.jobs);jobs[0]['steps'][-1]['conclusion']='success'
        with self.assertRaises(ValueError):finish.validate_publication_proof(self.run,jobs)
        jobs=copy.deepcopy(self.jobs);jobs[0]['steps'].append(copy.deepcopy(jobs[0]['steps'][0]))
        with self.assertRaises(ValueError):finish.validate_publication_proof(self.run,jobs)

    def test_all_original_real_upgrade_receipt_checks_are_required_with_exact_types_and_source(self):
        for key in self.receipt:
            changed=dict(self.receipt);changed.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):finish.validate_upgrade_receipt(changed)
        for change in ({'sameUid':False},{'sameUid':1},{'format':True},{'fromVersionCode':15},{'toVersionCode':16},{'source':'8'*40},{'noDataReset':False}):
            with self.subTest(change=change),self.assertRaises(ValueError):finish.validate_upgrade_receipt(self.receipt|change)

    def test_changed_original_checksum_receipt_is_rejected_before_signature_or_promotion(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'assets';folder.mkdir();receipts=root/'receipts';receipts.mkdir()
            (receipts/'android-install-over-proof.json').write_text(json.dumps(self.receipt));(receipts/'previous-release-integrity.json').write_text('{}')
            (folder/'SHA256SUMS').write_text('explicitly synthetic wrong checksum fixture')
            with patch.object(finish,'historical_snapshot',return_value={}),self.assertRaises(ValueError):finish.verify_files(folder,receipts)

    def test_finalization_retrieves_original_artifacts_and_verifies_before_publishing_without_new_signing_or_uploads(self):
        workflow=(finish.ROOT/'.github/workflows/finalize-v0101.yml').read_text()
        for text in (finish.REQUEST,str(finish.PUBLICATION_RUN),str(finish.RELEASE_ID),finish.SOURCE):
            # Release ID is bound by the helper; the workflow must use that helper.
            if text==str(finish.RELEASE_ID):self.assertIn('finalize_v0101.py',workflow)
            else:self.assertIn(text,workflow)
        for text in ('gh release create','gh release upload','gh release delete','--clobber','DKORD_KEYSTORE','assembleDebug','gradlew','sign_update_manifest.py'):
            self.assertNotIn(text,workflow)
        self.assertLess(workflow.index('verify-staged'),workflow.index('gh release edit v0.10.1'))
        self.assertLess(workflow.index('verify_apk_update.py'),workflow.index('gh release edit v0.10.1'))
        self.assertGreater(workflow.index('verify-published'),workflow.index('gh release edit v0.10.1'))
        self.assertIn('--draft=false --latest',workflow)
        self.assertIn('v0.10.1-publication-receipts',workflow)
        self.assertIn('verify_desktop_release_artifacts.py',workflow)


if __name__=='__main__':unittest.main()
