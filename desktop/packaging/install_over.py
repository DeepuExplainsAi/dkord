"""Execute actual old -> new native installers on disposable hosted CI only.

No uninstall/reset. Seeded real Store state and generated audio are read/decoded
by the NEW installed frozen app, at the unchanged normal per-user location.
Linux verifies BOTH deb install-over and portable AppImage replacement. This is
virtual-host fixture acceptance, not a claim about a physical user's computer.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from platformdirs import user_data_path
from dkord_desktop import __version__
from dkord_desktop.platforms import platform_key
from dkord_desktop.upgrade_fixture import seed

BASELINE='desktop-v0.10.0-preview.2'
REPO='DeepuExplainsAi/dkord'
BASELINE_SOURCE='0d97e6413d999cdfbb562397cc230f1798f02606'


def call(command,**kwargs):return subprocess.run([str(arg) for arg in command],check=True,timeout=240,**kwargs)


def api(path):return json.loads(subprocess.check_output(['gh','api','repos/'+REPO+'/'+path],text=True))


def file_digest(path):
    value=hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def install(path,target):
    if target.startswith('windows-'):
        call([path,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER'])
        folder=Path(os.environ['LOCALAPPDATA'])/'Programs'/('Dkord-x86' if target=='windows-x86' else 'Dkord')
        return folder/'Dkord.exe'
    if target.startswith('macos-'):
        call(['sudo','installer','-pkg',path,'-target','/'])
        return Path('/Applications/Dkord.app/Contents/MacOS/Dkord')
    call(['sudo','dpkg','-i',path]);return Path('/opt/Dkord/Dkord')


def verify_installed(executable,folder,target,*,image=False):
    report=folder/('appimage-installed-read.json' if image else 'installed-read.json')
    command=[executable]+(['--appimage-extract-and-run'] if image else [])+['--verify-upgrade-fixture',report]
    call(command)
    data=json.loads(report.read_text())
    if data.get('version')!=__version__ or data.get('target')!=target or data.get('frozen') is not True or data.get('pythonBits')!=(32 if target=='windows-x86' else 64):
        raise ValueError('The actual installed app has wrong version/profile/bitness or is not frozen')
    checks=data.get('checks',{})
    required=('library','playlists','likes','history','settings','queue','privateDownload','deviceDownload','studioSources','studioClips','audioDecoded')
    if any(checks.get(key) is not True for key in required):raise ValueError('Installed app did not retain every fixture category/byte')
    return data


def verify_install_over(target,packages):
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!=REPO or target!=platform_key():
        raise ValueError('Real installer execution is restricted to the exact native disposable CI profile')
    release=api('releases/tags/'+BASELINE)
    ref=api('git/ref/tags/'+BASELINE)['object']
    if release['id']!=438483769 or release['tag_name']!=BASELINE or release['draft'] or ref['type']!='commit' or ref['sha']!=BASELINE_SOURCE:
        raise ValueError('Historical baseline identity changed; never substitute an arbitrary old installer')
    assets={item['name']:item for item in release['assets']}
    kinds=('deb','AppImage') if target.startswith('linux-') else ('exe',) if target.startswith('windows-') else ('pkg',)
    checked=[]
    root=user_data_path('Dkord','Dkord',roaming=False)
    with tempfile.TemporaryDirectory(prefix='dkord-real-install-over-',dir=os.environ['RUNNER_TEMP']) as temporary:
        folder=Path(temporary);old_folder=folder/'baseline';old_folder.mkdir()
        for kind in kinds:
            name=f'Dkord-desktop-v0.10.0-{target}.{kind}'
            item=assets[name]
            if not isinstance(item.get('digest'),str) or not item['digest'].startswith('sha256:') or item['size']<=0:
                raise ValueError('Original baseline requires its GitHub byte digest')
            call(['gh','release','download',BASELINE,'--repo',REPO,'--pattern',name,'--dir',old_folder])
            old=old_folder/name
            if old.stat().st_size!=item['size'] or 'sha256:'+file_digest(old)!=item['digest']:
                raise ValueError('Original installer bytes differ from immutable release asset')
            new=next(path for path in packages if path.suffix=='.'+kind)
            if kind=='AppImage':
                portable=folder/'Dkord.AppImage';shutil.copyfile(old,portable);portable.chmod(0o755)
                call([portable,'--appimage-extract-and-run','--self-test'])
                # Actual same-path portable replacement, not an extracted relabelled build.
                shutil.copyfile(new,portable);portable.chmod(0o755)
                data=verify_installed(portable,folder,target,image=True)
            else:
                old_exe=install(old,target);call([old_exe,'--self-test'])
                seed(root,folder/'accessible-device')
                new_exe=install(new,target)
                if old_exe!=new_exe:raise ValueError('Install-over moved the existing executable path')
                data=verify_installed(new_exe,folder,target)
            checked.append(dict(kind=kind,baselineName=name,baselineSha256=item['digest'][7:],checks=data['checks']))
    return dict(format=1,baselineTag=BASELINE,baselineSource=BASELINE_SOURCE,toVersion=__version__,target=target,
                source=os.environ['DKORD_SOURCE_SHA'],noUninstall=True,standardUserData=True,frozenClient=True,packages=checked)
