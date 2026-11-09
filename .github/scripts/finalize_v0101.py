"""Finish ONLY the existing, fully tested original-key 0.10.1 draft.

The original publisher completed Android14->15 persistence, signing, all-eight
native attestations and all uploads, then its REST by-tag draft lookup returned
404 before the tag existed. No rebuilding, resigning, asset upload/replacement,
old-release mutation or test retries are permitted here. Compare all20 original
bytes to original CI receipts before publishing this exact existing draft.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from publish_v0101 import (REPO,TAG,VERSION,api,digest,expected_names,historical_snapshot,
                          release_for_verification,verify_release)

ROOT=Path(__file__).resolve().parents[2]
BRANCH='arena/a6a6bbda-dkord'
SOURCE='e0e925a674f106f6291731f5b143d3800a476cd3'
VALIDATED_PARENT='f56c855af4fc0ba8aae9c0b945f8fbdef15dec2a'
RELEASE_ID=438891732
PUBLICATION_RUN=42585180858
PUBLICATION_JOB=129053183822
REQUEST='.github/release-finalizations/v0.10.1.json'
CHECKSUM_SHA256='e38e40a2abacc05f4b847e5e1bef8016563991bdeaab85d4aea5889a3ea147a7'
MANIFEST_SHA256='9a2cd1d494a458f32ce54b72b7b049ca146653284d05c6ed8d08f4b062c00d0e'
ASSET_IDS={726779097,726779098,726779101,726779094,726779102,726779479,726779828,
           726779852,726780020,726780044,726780155,726780185,726780222,726780229,
           726780233,726780253,726780118,726780265,726780268,726780290}
PROOF_RUNS=((42584009501,VALIDATED_PARENT,'validate-desktop.yml'),
            (42584009540,VALIDATED_PARENT,'validate-pr.yml'),
            (42585188990,SOURCE,'validate-desktop.yml'),
            (42585188975,SOURCE,'validate-pr.yml'))
ALLOWED_FINALIZATION_CHANGES={REQUEST,'.github/scripts/publish_v0101.py',
    '.github/scripts/test_publish_v0101.py','.github/scripts/finalize_v0101.py',
    '.github/scripts/test_finalize_v0101.py','.github/workflows/finalize-v0101.yml'}
FAILED_DRAFT_STEP='Create a fresh draft, verify uploaded bytes and preserve all historical releases'
REQUIRED_STEPS={
    'Validate the fresh direct-child Android and PC publication request',
    'Run safety regressions and require a brand-new version without historical mutation',
    'Require successful Android and six-host native validation at parent and this exact release source',
    'Download and verify all exact-source native packages and real frozen Windows32 captures',
    'Require the existing stable Android signing identity, never generate a key',
    'Test exact-source Android and build with the original signing identity',
    'Verify original APK certificate, package and increasing install-over versionCode',
    'Attest native updates with the existing pinned APK identity and verify all eight client update plans',
    'Remove the temporary keystore before any publication operation',
    'Actually install the original APK then install-over and verify its real data and downloads',
    'Stage complete checksums and truthful Android and PC release notes',
    'Upload public publication receipts, never private signing material',
}


def validate_request(request,event,env,parent,changes,source_changes):
    schema={'tag','source','releaseId','publisherRun','branch','safetyHead'}
    if not isinstance(request,dict) or set(request)!=schema:raise ValueError('Wrong finalization request schema')
    expected=dict(tag=TAG,source=SOURCE,releaseId=RELEASE_ID,publisherRun=PUBLICATION_RUN,branch=BRANCH)
    if any(request[key]!=value or type(request[key]) is not type(value) for key,value in expected.items()):
        raise ValueError('Only the existing tested 0.10.1 draft can be finalized')
    previous=request['safetyHead'];sha=env.get('GITHUB_SHA','')
    if not isinstance(previous,str) or not re.fullmatch('[0-9a-f]{40}',previous) or int(previous,16)==0 or not re.fullmatch('[0-9a-f]{40}',sha) or sha==previous:
        raise ValueError('Exact new verification-metadata commit required')
    if (env.get('GITHUB_REPOSITORY')!=REPO or env.get('GITHUB_EVENT_NAME')!='push'
        or env.get('GITHUB_REF')!='refs/heads/'+BRANCH or not isinstance(event,dict)
        or event.get('repository',{}).get('full_name')!=REPO or event.get('ref')!=env['GITHUB_REF']
        or event.get('forced') is not False or event.get('deleted') is not False
        or event.get('before')!=previous or event.get('after')!=sha or parent!=previous or changes!=[REQUEST]):
        raise ValueError('Only a fresh direct metadata-only assigned-branch push may finalize')
    if not set(source_changes)<=ALLOWED_FINALIZATION_CHANGES:
        raise ValueError('App/assets/version/signing source changed since the fully tested release; cannot reuse its draft')


def validate_publication_proof(run,jobs):
    if (run.get('id')!=PUBLICATION_RUN or run.get('head_sha')!=SOURCE or run.get('head_branch')!=BRANCH
        or run.get('event')!='push' or run.get('path')!='.github/workflows/release-v0101.yml'
        or run.get('status')!='completed' or run.get('conclusion')!='failure'):
        raise ValueError('Wrong original protected publication evidence')
    if len(jobs)!=1 or jobs[0].get('id')!=PUBLICATION_JOB or jobs[0].get('status')!='completed':
        raise ValueError('Wrong original protected publication job')
    steps=jobs[0].get('steps',[])
    names=[step.get('name') for step in steps]
    if len(names)!=len(set(names)):raise ValueError('Ambiguous original step evidence')
    completed={step['name']:step.get('conclusion') for step in steps if step.get('status')=='completed'}
    if any(completed.get(name)!='success' for name in REQUIRED_STEPS):raise ValueError('An original signing/test/upgrade/proof/upload gate did not pass')
    if {step['name'] for step in steps if step.get('conclusion')=='failure'}!={FAILED_DRAFT_STEP}:
        raise ValueError('Original run failed beyond its known draft-lookup step')
    if completed.get('Publish the verified new Android and PC update without replacing any old release')!='skipped':
        raise ValueError('This route is not permission to republish a completed release')


def prerequisites():
    for run_id,source,workflow in PROOF_RUNS:
        run=api(f'actions/runs/{run_id}')
        if (run.get('head_sha')!=source or run.get('head_branch')!=BRANCH or run.get('event')!='pull_request'
            or run.get('path')!='.github/workflows/'+workflow or run.get('status')!='completed' or run.get('conclusion')!='success'):
            raise ValueError('Exact original parent/child Android and six-host native validation required')
    validate_publication_proof(api(f'actions/runs/{PUBLICATION_RUN}'),api(f'actions/runs/{PUBLICATION_RUN}/jobs?per_page=100')['jobs'])
    release=release_for_verification(True)
    if (release.get('id')!=RELEASE_ID or release.get('tag_name')!=TAG or release.get('draft') is not True
        or release.get('prerelease') is not False or release.get('target_commitish')!=SOURCE
        or len(release.get('assets',[]))!=20 or {asset.get('id') for asset in release['assets']}!=ASSET_IDS
        or {asset.get('name') for asset in release['assets']}!=expected_names()
        or any(asset.get('state')!='uploaded' for asset in release['assets'])):
        raise ValueError('Existing draft identity/source/original20 asset IDs changed; no replacement allowed')
    if api('git/ref/tags/'+TAG,optional=True) is not None:raise ValueError('No pre-existing/newly reset Git tag is permitted before this draft publication')
    print('::notice title=Existing 0.10.1 evidence::Original parent/child Android and all6 native validations, protected original-key signing, real Android14-to15 persistence and all20 original uploaded asset IDs verified; no rebuild or asset replacement.')


def validate_upgrade_receipt(receipt):
    expected=dict(format=1,package='app.dkord',baselineTag='v0.10.0',fromVersionCode=14,toVersionCode=15,
        source=SOURCE,sameUid=True,noUninstall=True,noDataReset=True,realRoom=True,settings=True,queue=True,
        privateDownload=True,mediaStoreExport=True,studioProjectAndSourceBytes=True)
    if receipt!=expected or any(type(receipt[key]) is not type(value) for key,value in expected.items()):
        raise ValueError('Original real-Android persistence receipt is incomplete or belongs to a different source')


def verify_files(folder,receipts,*,published=False):
    validate_upgrade_receipt(json.loads((receipts/'android-install-over-proof.json').read_text()))
    baseline=json.loads((receipts/'previous-release-integrity.json').read_text())
    if historical_snapshot()!=baseline:raise ValueError('Historical releases/tags/assets changed')
    if digest(folder/'SHA256SUMS')!=CHECKSUM_SHA256 or digest(folder/f'Dkord-desktop-v{VERSION}-manifest.json')!=MANIFEST_SHA256:
        raise ValueError('These are not the exact original CI checksum and signed-manifest bytes')
    entries={}
    for line in (folder/'SHA256SUMS').read_text().splitlines():
        match=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        if not match or match[2] in entries:raise ValueError('Malformed/duplicate original checksum entry')
        entries[match[2]]=match[1]
    if set(entries)!=expected_names()-{'SHA256SUMS'} or any(digest(folder/name)!=value for name,value in entries.items()):
        raise ValueError('The original19 staged files no longer match their pre-upload CI checksums')
    sys.path.insert(0,str(ROOT/'desktop'))
    from dkord_desktop.updates import Updater,verify_manifest
    raw=(folder/f'Dkord-desktop-v{VERSION}-manifest.json').read_bytes()
    if json.loads(raw)['payload'].get('source')!=SOURCE:raise ValueError('Wrong original signed installer source')
    for target in ('windows-x64','windows-x86','macos-x64','macos-arm64','linux-x64','linux-arm64'):
        for image in ((False,True) if target.startswith('linux-') else (False,)):
            plan=verify_manifest(raw,Updater.production_keys(),installed='0.10.0',target=target,image=image)
            if plan is None or plan.version!=VERSION or plan.tag!=TAG or plan.sha256!=digest(folder/plan.name) or plan.size!=(folder/plan.name).stat().st_size:
                raise ValueError('Original protected signature/installed-client exact-platform update plan failed')
    release=verify_release(folder,SOURCE,baseline,not published)
    if release['id']!=RELEASE_ID or {asset['id'] for asset in release['assets']}!=ASSET_IDS:
        raise ValueError('Original release/asset IDs changed during finalization')
    print('::notice title=Original Android + PC bytes verified::'+str(RELEASE_ID)+' — all20 uploaded byte hashes/IDs, original19 CI checksums, original-key eight native update plans, original real Android persistence receipt and unchanged historical releases verified. Published='+str(published))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('validate-request','check-prerequisites','verify-staged','verify-published'))
    parser.add_argument('--folder',type=Path);parser.add_argument('--receipts',type=Path);args=parser.parse_args()
    if args.command=='validate-request':
        sha=os.environ['GITHUB_SHA'];request=json.loads((ROOT/REQUEST).read_text());event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        git=lambda *values:subprocess.check_output(['git',*values],cwd=ROOT,text=True).strip()
        validate_request(request,event,os.environ,git('rev-parse',sha+'^'),git('diff','--name-only',request['safetyHead'],sha).splitlines(),git('diff','--name-only',SOURCE,sha).splitlines())
        print('Existing-draft finalization request validated; only publication-verifier files changed since the unchanged fully tested app source.')
    elif args.command=='check-prerequisites':prerequisites()
    else:
        if args.folder is None or args.receipts is None:raise ValueError('Original files/receipts are required')
        verify_files(args.folder,args.receipts,published=args.command=='verify-published')


if __name__=='__main__':main()
