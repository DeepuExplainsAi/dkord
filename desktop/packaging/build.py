"""Native host packaging only, read-only preview output. No release writes or signing secrets."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dkord_desktop import __version__
from dkord_desktop.updates import platform_key

OUT=ROOT/'.artifacts'
DIST=OUT/'bundle'
NODE_VERSION='22.22.3'
NODE_LICENSE_SHA256='c738ae413cf561f174e34f6961f8ca458aae2369a73640dda6234c629b98bcc4'
APPIMAGE={
 'x64':('x86_64','e8c1169c4af66c3184d7ee110713d4be04befe671fa358e2c1591ee840553b03'),
 'arm64':('aarch64','d6a061996de690434996c2a523eafedd0a23780aaf02d69ce364537e71607e94'),
}

def call(args,**kwargs):
    print('+', ' '.join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),check=True,**kwargs)


def resources():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtGui import QImage,QPainter
    from PIL import Image
    app=QApplication.instance() or QApplication([])
    image=QImage(1024,1024,QImage.Format.Format_ARGB32);image.fill(0)
    painter=QPainter(image);QSvgRenderer(str(ROOT/'assets/dkord.svg')).render(painter);painter.end()
    assert image.save(str(OUT/'dkord.png'))
    pil=Image.open(OUT/'dkord.png');pil.save(OUT/'dkord.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]);pil.save(OUT/'dkord.icns')
    node=shutil.which('node')
    if not node:raise RuntimeError('A matching Node runtime must be bundled, not assumed installed on the user PC')
    reported=subprocess.check_output([node,'--version'],text=True).strip()
    if reported!='v'+NODE_VERSION:raise RuntimeError(f'Need Node{NODE_VERSION}, got{reported}')
    expected='arm64' if platform.machine().casefold() in {'arm64','aarch64'} else 'x64'
    if subprocess.check_output([node,'-p','process.arch'],text=True).strip()!=expected:raise RuntimeError('JS runtime architecture mismatch')
    runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
    target=runtime/('node.exe' if os.name=='nt' else 'node');shutil.copy2(node,target)
    # Matching upstream license, vendored and digest pinned. Parallel hosted builds
    # must not depend on unauthenticated GitHub API quota for mandatory attribution.
    license=(ROOT/'assets/Node-LICENSE.txt').read_bytes()
    if hashlib.sha256(license).hexdigest()!=NODE_LICENSE_SHA256:raise RuntimeError('Bundled Node license differs from the pinned upstream22.22.3 text')
    (runtime/'NODE-LICENSE.txt').write_bytes(license)
    return target


def freeze(node):
    icon=OUT/('dkord.icns' if sys.platform=='darwin' else 'dkord.ico' if os.name=='nt' else 'dkord.png')
    cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--name','Dkord','--windowed','--onedir',
         '--distpath',str(DIST),'--workpath',str(OUT/'work'),'--specpath',str(OUT), '--paths',str(ROOT), '--icon',str(icon),
         '--add-data',str(ROOT/'assets')+os.pathsep+'assets', '--add-data',str(ROOT.parent/'LICENSE')+os.pathsep+'licenses',
         '--add-data',str(ROOT/'THIRD_PARTY.md')+os.pathsep+'licenses','--add-data',str(ROOT/'.runtime/NODE-LICENSE.txt')+os.pathsep+'licenses',
         '--add-binary',str(node)+os.pathsep+'runtime', '--collect-all','yt_dlp', '--collect-all','yt_dlp_ejs',
         '--collect-all','imageio_ffmpeg','--collect-all','av']
    if sys.platform=='darwin':cmd+=['--osx-bundle-identifier','app.dkord.desktop']
    cmd+=[str(ROOT/'packaging/entry.py')];call(cmd,cwd=ROOT)
    if sys.platform=='darwin':
        import plistlib
        path=DIST/'Dkord.app/Contents/Info.plist'
        with path.open('rb') as file:info=plistlib.load(file)
        info.update(CFBundleShortVersionString=__version__,CFBundleVersion=__version__,LSMinimumSystemVersion='13.0',CFBundleDisplayName='Dkord Desktop Preview')
        with path.open('wb') as file:plistlib.dump(info,file)
        # Ad-hoc local preview signature only, NOT Developer ID / notarization / a trusted public release.
        call(['codesign','--force','--deep','--sign','-',DIST/'Dkord.app'])
        exe=DIST/'Dkord.app/Contents/MacOS/Dkord'
    else:exe=DIST/'Dkord'/('Dkord.exe' if os.name=='nt' else 'Dkord')
    call([exe,'--self-test'])
    bundled_node=(DIST/'Dkord.app/Contents/Frameworks/runtime/node' if sys.platform=='darwin' else DIST/'Dkord/_internal/runtime'/node.name)
    if bundled_node.exists():call([bundled_node,'-e','console.log("Bundled JS runtime native smoke PASS", process.arch)'])
    else:raise RuntimeError('Bundled JS runtime is missing; do not ship an app relying on the build machine PATH')
    return exe


def windows():
    compiler=shutil.which('ISCC.exe') or r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
    if not Path(compiler).is_file():raise RuntimeError('Inno Setup native compiler was not found')
    # windows.iss expects the icon adjacent to the source directory.
    shutil.copy2(OUT/'dkord.ico',DIST/'dkord.ico')
    call([compiler,f'/DVersion={__version__}',f'/DSource={DIST / "Dkord"}',f'/DOutput={OUT}',ROOT/'packaging/windows.iss'])


def macos(target):
    call(['pkgbuild','--component',DIST/'Dkord.app','--identifier','app.dkord.desktop','--version',__version__,
          '--install-location','/Applications',OUT/f'Dkord-desktop-v{__version__}-{target}.pkg'])


def linux(target):
    arch='arm64' if target.endswith('arm64') else 'amd64'
    with tempfile.TemporaryDirectory() as temp:
        stage=Path(temp)/'deb';install=stage/'opt/Dkord';install.parent.mkdir(parents=True);shutil.copytree(DIST/'Dkord',install)
        control=stage/'DEBIAN';control.mkdir()
        glibc='2.39' if arch=='arm64' else '2.34'
        (control/'control').write_text(f'Package: dkord\nVersion: {__version__}\nSection: sound\nPriority: optional\nArchitecture: {arch}\nMaintainer: DeepuGupta\nDepends: libc6 (>= {glibc}), libgl1, libegl1, libdbus-1-3, libxkbcommon0, libxcb-cursor0, libpulse0\nDescription: Dkord native desktop music and Mashup Studio preview\n')
        binary=stage/'usr/bin';binary.mkdir(parents=True);launcher=binary/'dkord';launcher.write_text('#!/bin/sh\nexec /opt/Dkord/Dkord "$@"\n');launcher.chmod(0o755)
        desktop=stage/'usr/share/applications';desktop.mkdir(parents=True)
        text='[Desktop Entry]\nType=Application\nName=Dkord Desktop Preview\nComment=Music, private offline audio and Mashup Studio\nExec=dkord\nIcon=dkord\nTerminal=false\nCategories=AudioVideo;Audio;Music;\nKeywords=Music;YouTube Music;Offline;Audio editor;Mashup;Choliwood;\n'
        (desktop/'app.dkord.desktop').write_text(text)
        icons=stage/'usr/share/icons/hicolor/256x256/apps';icons.mkdir(parents=True);shutil.copy2(OUT/'dkord.png',icons/'dkord.png')
        call(['dpkg-deb','--root-owner-group','--build',stage,OUT/f'Dkord-desktop-v{__version__}-{target}.deb'])
        appdir=Path(temp)/'Dkord.AppDir';appdir.mkdir();shutil.copytree(DIST/'Dkord',appdir/'usr/lib/Dkord')
        run=appdir/'AppRun';run.write_text('#!/bin/sh\nHERE=$(dirname "$(readlink -f "$0")")\nexec "$HERE/usr/lib/Dkord/Dkord" "$@"\n');run.chmod(0o755)
        (appdir/'app.dkord.desktop').write_text(text);shutil.copy2(OUT/'dkord.png',appdir/'dkord.png')
        native_arch,digest=APPIMAGE[target.split('-')[1]];tool=Path(temp)/'appimagetool.AppImage'
        url=f'https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-{native_arch}.AppImage'
        urllib.request.urlretrieve(url,tool)
        if hashlib.sha256(tool.read_bytes()).hexdigest()!=digest:raise RuntimeError('Pinned AppImage tool changed; review upstream before updating the digest')
        tool.chmod(0o755);call([tool,'--appimage-extract'],cwd=temp)
        image=OUT/f'Dkord-desktop-v{__version__}-{target}.AppImage'
        env=dict(os.environ,ARCH=native_arch)
        call([Path(temp)/'squashfs-root/AppRun','-n',appdir,image],env=env)
        image.chmod(0o755)
        call([image,'--appimage-extract-and-run','--self-test'],env=env)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',default=platform_key());args=parser.parse_args()
    if args.target!=platform_key():raise RuntimeError('Native package target must match the actual build host OS/CPU')
    OUT.mkdir(parents=True,exist_ok=True);node=resources();freeze(node)
    if os.name=='nt':windows()
    elif sys.platform=='darwin':macos(args.target)
    else:linux(args.target)
    artifacts=[]
    for file in OUT.iterdir():
        if file.suffix in {'.exe','.pkg','.deb','.AppImage'}:
            artifacts.append({'name':file.name,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    if not artifacts:raise RuntimeError('No real native packages were produced')
    preview={'channel':'development-preview','version':__version__,'target':args.target,'source':os.environ.get('DKORD_SOURCE_SHA','local'),
             'trusted_signed_release':False,'notarized':False,'artifacts':artifacts}
    (OUT/f'preview-{args.target}.json').write_text(json.dumps(preview,indent=2)+'\n')
    print(json.dumps(preview,indent=2))

if __name__=='__main__':main()
