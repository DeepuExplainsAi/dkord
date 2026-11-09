"""Bounded 0.10.2 publication receipts; no historical release/tag mutation.

The caller must pass signing, exact-head Android + six-host native/screenshot,
installer and compatibility gates before creating the new draft. This helper
records public release metadata, checks exact uploaded bytes and preserves the
previous stable/preview release IDs, tags, descriptions and assets.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

REPO='DeepuExplainsAi/dkord'
TAG='v0.10.2'
VERSION='0.10.2'
HISTORICAL=('v0.9.1','v0.10.0','desktop-v0.10.0-preview.2','v0.10.1')
TARGETS=('windows-x64','windows-x86','macos-x64','macos-arm64','linux-x64','linux-arm64')


def api(path,optional=False):
    command=subprocess.run(['gh','api','repos/'+REPO+'/'+path],capture_output=True,text=True,check=False)
    if command.returncode:
        if optional and '(HTTP 404)' in command.stderr:return None
        raise RuntimeError('GitHub metadata read failed for '+path)
    return json.loads(command.stdout)


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def tag_commit(tag):
    value=api('git/ref/tags/'+tag)['object']
    if value['type']=='tag':value=api('git/tags/'+value['sha'])['object']
    if value['type']!='commit' or not re.fullmatch('[0-9a-f]{40}',value['sha']):raise ValueError('Unexpected Git tag target')
    return value['sha']


def historical_snapshot():
    result={}
    for tag in HISTORICAL:
        item=api('releases/tags/'+tag)
        assets=[{key:asset.get(key) for key in ('id','name','size','digest','created_at','updated_at','browser_download_url')} for asset in item['assets']]
        result[tag]=dict(id=item['id'],tag=item['tag_name'],commit=tag_commit(tag),name=item['name'],body=item.get('body'),
                         draft=item['draft'],prerelease=item['prerelease'],published_at=item['published_at'],assets=sorted(assets,key=lambda asset:asset['name']))
    return result


def expected_names():
    names={f'Dkord-{TAG}.apk',f'Dkord-desktop-v{VERSION}-manifest.json','SHA256SUMS',
           'windows-x86-player.png','windows-x86-studio.png','windows-x86-screenshot-proof.json',
           'Dkord-PC-screenshots-v0.10.2.zip','Dkord-PC-screenshots-v0.10.2.json'}
    for target in TARGETS:
        names.add('preview-'+target+'.json')
        for kind in (('deb','AppImage') if target.startswith('linux-') else (('exe',) if target.startswith('windows-') else ('pkg',))):
            names.add(f'Dkord-desktop-v{VERSION}-{target}.{kind}')
    return names


def checksums(folder):
    names=expected_names()-{'SHA256SUMS'}
    actual={file.name for file in folder.iterdir()}
    if actual!=names:raise ValueError('Incomplete or unexpected staged release files')
    for name in names:
        path=folder/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size<=0:raise ValueError('Invalid staged release file')
    output=folder/'SHA256SUMS'
    with output.open('x') as file:
        for name in sorted(names):file.write(digest(folder/name)+'  '+name+'\n')
    return output


def release_for_verification(draft):
    release=api('releases/tags/'+TAG,optional=draft)
    if release is not None:return release
    # GitHub's REST by-tag endpoint returns404 for an unpublished draft whose
    # tag does not exist yet, even though the authenticated releases list includes
    # it. Do not create/reset a tag or relax source/asset checks to work around it.
    matches=[]
    for page in range(1,4):
        items=api(f'releases?per_page=100&page={page}')
        if not isinstance(items,list):raise ValueError('Invalid authenticated releases list')
        matches.extend(item for item in items if item.get('tag_name')==TAG)
        if len(items)<100:break
    if len(matches)!=1 or matches[0].get('draft') is not True:
        raise ValueError('Exactly one authenticated unpublished 0.10.2 draft is required')
    return matches[0]


def verify_release(folder,source,baseline,draft):
    if not re.fullmatch('[0-9a-f]{40}',source) or int(source,16)==0:raise ValueError('Invalid exact release source')
    if historical_snapshot()!=baseline:raise ValueError('A historical release/tag/asset changed; publication refused')
    release=release_for_verification(draft)
    reference=api('git/ref/tags/'+TAG,optional=True) if draft else True
    target=tag_commit(TAG) if reference else release.get('target_commitish')
    if (release['tag_name']!=TAG or release['draft'] is not draft or release['prerelease'] is not False or target!=source):
        raise ValueError('Wrong new release state/source')
    names=expected_names()
    files={file.name:file for file in folder.iterdir()}
    assets=release['assets']
    if set(files)!=names or len(assets)!=len(names) or {asset['name'] for asset in assets}!=names:
        raise ValueError('The new Android/PC release assets are incomplete, unexpected or duplicated')
    for asset in assets:
        path=files[asset['name']]
        if path.is_symlink() or not path.is_file() or asset['size']!=path.stat().st_size or asset.get('digest')!='sha256:'+digest(path):
            raise ValueError('Uploaded release bytes/digest do not match verified staging')
        expected='https://github.com/'+REPO+'/releases/download/'+TAG+'/'+path.name
        # GitHub draft download URLs can use its temporary untagged draft route.
        if not draft and asset['browser_download_url']!=expected:raise ValueError('Unexpected published download URL')
    if not draft and api('releases/latest')['id']!=release['id']:raise ValueError('New common release is not latest')
    return release


def notes(source,android,native):
    if not re.fullmatch('[a-f0-9]{40}',source) or not android.isdigit() or not native.isdigit():raise ValueError('Exact-source validation receipt required')
    return f'''# Dkord v0.10.2 — Android & PC

A fresh Android and PC update. Earlier releases remain unchanged.

- **Android:** install `Dkord-v0.10.2.apk` over Dkord. Same `app.dkord` package,
  original signing certificate, versionCode16; no uninstall or data reset.
- **PC:** choose the package matching your installed app and CPU. Windows has
  separate genuine x86 (32-bit) and x64 installers; macOS has Intel/Apple Silicon
  packages; Linux has x64/arm64 `.deb` and `.AppImage` packages.
- New separate **Open YouTube link** in the global toolbar, Search and Library:
  **Paste link → Show video → Play** opens the exact accessible upload, even if
  Songs search does not index it. No title-search substitution/music-only gate.
  Preview does not change playback; ordinary queue/playlist/download/Studio
  actions are retained. Private/restricted/unavailable content is not bypassed.
- **180 actual native PC screenshots**:30 pages/dialogs/themes on each of all6
  OS/CPU builds. Download `Dkord-PC-screenshots-v0.10.2.zip`, extract and open
  `index.html`; full-resolution original PNGs and source/runtime/hashes included.
  All samples are explicitly OFFLINE DEMO, not live provider/playback proof.
- Phone-derived responsive native PC layout, artwork, Home, catalogue/search,
  New Releases, player/queue, sleep timer, Library and Mashup Studio. Catalogue
  songs can go directly into Studio without downloading manually first.
- Explicit **Download in Dkord** and **Download to device** destinations.
- Discoverable **Listen Together** for supported songs/playlists through the
  global player. Host-only default, selected-member/everyone permissions and
  listener opt-in; permissions never start playback automatically.
- Local playback diagnostics, with no issue/repository navigation or upload.
  Concise About with **© 2026 dKORD**.

## Update safely

Keep your existing app/data. **Do not uninstall or clear data.** PC libraries,
playlists, settings, downloads and Studio inputs are outside the installation
folder. Use the same installed CPU profile; do not mix the Windows32/64 runtimes.

Old PC previews had no trusted update key, so the first PC setup needs this
one-time manual **install-over**. This build pins the existing Android public
signing identity. Its desktop update manifest is attested with that original
protected identity and verified by the actual client for all six targets/eight
packages. Future compatible updates can be checked/downloaded in the app, without
being sent to the release page. No replacement production key was created.

The application update-manifest signature is **not** OS publisher signing:
Windows Authenticode and Apple Developer ID/notarization are not configured.
Do not bypass OS security warnings. Windows10+; macOS13+; Linux glibc2.39+.

## Validation and genuine screenshots

Exact source: `{source}`.

- [Android unit + emulator regressions](https://github.com/{REPO}/actions/runs/{android})
- [Six native OS/CPU builds, real codecs and Qt widget tests](https://github.com/{REPO}/actions/runs/{native})
- Attached Windows32 screenshots are captures of the actual frozen app using
  isolated, explicitly generated tones — not a browser, phone or AI mockup.
  Their source/bitness/Qt/image hashes are in the attached proof.
- Android458 JVM +50 emulator regressions and144 native cases per target are required, with no test failures/errors/skips.
- Original APK certificate/install-over compatibility and all asset digests are
  checked before publication. `SHA256SUMS` covers the complete release.

CI fixture/emulator checks are not a physical device, heard-audio or live-provider
acceptance claim. Live service availability, OS media keys and real multi-device
room sessions still need device acceptance. No cloud/audio syncing is claimed.
Build-origin `preview-*.json` files are unsigned build receipts; the separate
signed release manifest attests the exact native installer bytes.
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    command=commands.add_parser('snapshot-release');command.add_argument('--output',type=Path,required=True)
    commands.add_parser('ensure-new-release')
    command=commands.add_parser('checksums');command.add_argument('--folder',type=Path,required=True)
    command=commands.add_parser('notes');command.add_argument('--source',required=True);command.add_argument('--android-run',required=True);command.add_argument('--native-run',required=True);command.add_argument('--output',type=Path,required=True)
    command=commands.add_parser('verify-release');command.add_argument('--folder',type=Path,required=True);command.add_argument('--source',required=True);command.add_argument('--baseline',type=Path,required=True);command.add_argument('--draft',action='store_true')
    args=parser.parse_args()
    if args.command=='snapshot-release':
        with args.output.open('x') as file:json.dump(historical_snapshot(),file,indent=2)
    elif args.command=='ensure-new-release':
        if api('releases/tags/'+TAG,optional=True) is not None or api('git/ref/tags/'+TAG,optional=True) is not None:
            raise ValueError('0.10.2 already exists; no overwrite, replacement or historical mutation')
    elif args.command=='checksums':checksums(args.folder)
    elif args.command=='notes':
        with args.output.open('x') as file:file.write(notes(args.source,args.android_run,args.native_run))
    elif args.command=='verify-release':
        result=verify_release(args.folder,args.source,json.loads(args.baseline.read_text()),args.draft)
        print('::notice title=Android + PC release integrity::'+result['html_url']+' — exact uploaded bytes, source and previous releases preserved.')


if __name__=='__main__':main()
