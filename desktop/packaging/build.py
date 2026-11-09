"""Native host packaging only, read-only preview output. No release writes or signing secrets."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dkord_desktop import __version__
from dkord_desktop.platforms import platform_key, WINDOWS_X86
from dkord_desktop.binaries import require_pe_architecture
from pinned_assets import download_asset

OUT=ROOT/'.artifacts'
DIST=OUT/'bundle'
NODE_VERSION='22.22.3'
NODE_LICENSE_SHA256='c738ae413cf561f174e34f6961f8ca458aae2369a73640dda6234c629b98bcc4'
APPIMAGE={
 'x64':('x86_64','e8c1169c4af66c3184d7ee110713d4be04befe671fa358e2c1591ee840553b03'),
 'arm64':('aarch64','d6a061996de690434996c2a523eafedd0a23780aaf02d69ce364537e71607e94'),
}
APPIMAGE_TOOL_IDS={'x64':715388534,'arm64':715388203}
# Public asset API receipts at AppImage/type2-runtime commit below. No mutable,
# unchecked runtime download is delegated to appimagetool during the build.
APPIMAGE_RUNTIME_SOURCE='fedfad51acc2860b2916a1eef32ba4a500ff31ef'
APPIMAGE_RUNTIME={
 'x64':(657374641,'617aa77314d57c8b8e4fae9c3f0b35af7b30d5529cb69e98f64f92510ed98a46'),
 'arm64':(657373827,'9a72a744d221576c9347ec074243acc5c3c7568896b12714e0e82e9f0bf47900'),
}

def call(args,**kwargs):
    print('+', ' '.join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),check=True,**kwargs)


def resources():
    from dkord_desktop.qt import QApplication,QSvgRenderer,QImage,QPainter
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
    expected='ia32' if WINDOWS_X86 else ('arm64' if platform_key().endswith('arm64') else 'x64')
    if subprocess.check_output([node,'-p','process.arch'],text=True).strip()!=expected:raise RuntimeError('JS runtime architecture mismatch')
    if os.name=='nt':require_pe_architecture(Path(node),'x86' if WINDOWS_X86 else 'x64')
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
         '--collect-submodules','yt_dlp']
    if WINDOWS_X86:
        cmd+=['--exclude-module','av','--exclude-module','imageio_ffmpeg',
              '--add-binary',str(ROOT/'.runtime/ffmpeg.exe')+os.pathsep+'runtime',
              '--add-binary',str(ROOT/'.runtime/ffprobe.exe')+os.pathsep+'runtime',
              '--add-data',str(ROOT/'.runtime/FFmpeg-COPYING.GPLv3')+os.pathsep+'licenses',
              '--add-data',str(ROOT/'.runtime/FFmpeg-source.json')+os.pathsep+'licenses']
    else:cmd+=['--collect-all','av','--collect-all','imageio_ffmpeg']
    if sys.platform=='darwin':cmd+=['--osx-bundle-identifier','app.dkord.desktop']
    cmd+=[str(ROOT/'packaging/entry.py')];call(cmd,cwd=ROOT)
    if sys.platform=='darwin':
        import plistlib
        path=DIST/'Dkord.app/Contents/Info.plist'
        with path.open('rb') as file:info=plistlib.load(file)
        info.update(CFBundleShortVersionString=__version__,CFBundleVersion=__version__,LSMinimumSystemVersion='13.0',CFBundleDisplayName='Dkord')
        with path.open('wb') as file:plistlib.dump(info,file)
        # Ad-hoc local preview signature only, NOT Developer ID / notarization / a trusted public release.
        call(['codesign','--force','--deep','--sign','-',DIST/'Dkord.app'])
        exe=DIST/'Dkord.app/Contents/MacOS/Dkord'
    else:exe=DIST/'Dkord'/('Dkord.exe' if os.name=='nt' else 'Dkord')
    if os.name=='nt':require_pe_architecture(exe,'x86' if WINDOWS_X86 else 'x64')
    call([exe,'--self-test'])
    bundled_node=(DIST/'Dkord.app/Contents/Frameworks/runtime/node' if sys.platform=='darwin' else DIST/'Dkord/_internal/runtime'/node.name)
    if bundled_node.exists():
        if os.name=='nt':require_pe_architecture(bundled_node,'x86' if WINDOWS_X86 else 'x64')
        call([bundled_node,'-e','console.log("Bundled JS runtime native smoke PASS", process.arch)'])
    else:raise RuntimeError('Bundled JS runtime is missing; do not ship an app relying on the build machine PATH')
    if WINDOWS_X86:
        require_pe_architecture(DIST/'Dkord/_internal/runtime/ffmpeg.exe','x86')
        require_pe_architecture(DIST/'Dkord/_internal/runtime/ffprobe.exe','x86')
    return exe


def windows(target):
    compiler=shutil.which('ISCC.exe') or r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
    if not Path(compiler).is_file():raise RuntimeError('Inno Setup native compiler was not found')
    # windows.iss expects the icon adjacent to the source directory.
    shutil.copy2(OUT/'dkord.ico',DIST/'dkord.ico')
    call([compiler,f'/DVersion={__version__}',f'/DTarget={target}',f'/DSource={DIST / "Dkord"}',f'/DOutput={OUT}',ROOT/'packaging/windows.iss'])


def macos(target):
    import plistlib
    with tempfile.TemporaryDirectory() as temporary:
        stage=Path(temporary);root=stage/'root';root.mkdir();shutil.copytree(DIST/'Dkord.app',root/'Dkord.app',symlinks=True)
        components=stage/'components.plist'
        call(['pkgbuild','--analyze','--root',root,components])
        with components.open('rb') as file:entries=plistlib.load(file)
        for entry in entries:
            entry['BundleIsRelocatable']=False;entry['BundleOverwriteAction']='upgrade'
        with components.open('wb') as file:plistlib.dump(entries,file)
        call(['pkgbuild','--root',root,'--component-plist',components,'--identifier','app.dkord.desktop','--version',__version__,
              '--install-location','/Applications',OUT/f'Dkord-desktop-v{__version__}-{target}.pkg'])


def linux(target):
    arch='arm64' if target.endswith('arm64') else 'amd64'
    with tempfile.TemporaryDirectory() as temp:
        stage=Path(temp)/'deb';install=stage/'opt/Dkord';install.parent.mkdir(parents=True);shutil.copytree(DIST/'Dkord',install)
        control=stage/'DEBIAN';control.mkdir()
        glibc='2.39' # Both binaries are built on Ubuntu24.04, never promise an untested older libc.
        (control/'control').write_text(f'Package: dkord\nVersion: {__version__}\nSection: sound\nPriority: optional\nArchitecture: {arch}\nMaintainer: DeepuGupta\nDepends: libc6 (>= {glibc}), libgl1, libegl1, libdbus-1-3, libxkbcommon0, libxcb-cursor0, libxcb-shape0, libx11-xcb1, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, libxcb-xinerama0, libxcb-xkb1, libxcb-randr0, libxcb-sync1, libxcb-xfixes0, libxcb-shm0, libpulse0\nDescription: Dkord music and Mashup Studio\n')
        binary=stage/'usr/bin';binary.mkdir(parents=True);launcher=binary/'dkord';launcher.write_text('#!/bin/sh\nexec /opt/Dkord/Dkord "$@"\n');launcher.chmod(0o755)
        desktop=stage/'usr/share/applications';desktop.mkdir(parents=True)
        text='[Desktop Entry]\nType=Application\nName=Dkord\nComment=Music, private offline audio and Mashup Studio\nExec=dkord\nIcon=dkord\nTerminal=false\nCategories=AudioVideo;Audio;Music;\nKeywords=Music;YouTube Music;Offline;Audio editor;Mashup;Choliwood;\n'
        (desktop/'app.dkord.desktop').write_text(text)
        icons=stage/'usr/share/icons/hicolor/256x256/apps';icons.mkdir(parents=True);shutil.copy2(OUT/'dkord.png',icons/'dkord.png')
        deb=OUT/f'Dkord-desktop-v{__version__}-{target}.deb'
        call(['dpkg-deb','--root-owner-group','--build',stage,deb])
        dependencies=subprocess.check_output(['dpkg-deb','--field',deb,'Depends'],text=True)
        if 'libc6 (>= 2.39)' not in dependencies:raise RuntimeError('Native Debian package must declare the actual conservative glibc2.39 build baseline')
        appdir=Path(temp)/'Dkord.AppDir';appdir.mkdir();shutil.copytree(DIST/'Dkord',appdir/'usr/lib/Dkord')
        run=appdir/'AppRun';run.write_text('#!/bin/sh\nHERE=$(dirname "$(readlink -f "$0")")\nexec "$HERE/usr/lib/Dkord/Dkord" "$@"\n');run.chmod(0o755)
        (appdir/'app.dkord.desktop').write_text(text);shutil.copy2(OUT/'dkord.png',appdir/'dkord.png')
        profile=target.split('-')[1];native_arch,digest=APPIMAGE[profile];tool=Path(temp)/'appimagetool.AppImage'
        download_asset('AppImage/appimagetool',APPIMAGE_TOOL_IDS[profile],tool,digest)
        runtime_id,runtime_digest=APPIMAGE_RUNTIME[profile];runtime=Path(temp)/('runtime-'+native_arch)
        download_asset('AppImage/type2-runtime',runtime_id,runtime,runtime_digest)
        tool.chmod(0o755);call([tool,'--appimage-extract'],cwd=temp)
        image=OUT/f'Dkord-desktop-v{__version__}-{target}.AppImage'
        env=dict(os.environ,ARCH=native_arch)
        call([Path(temp)/'squashfs-root/AppRun','--runtime-file',runtime,'-n',appdir,image],env=env)
        image.chmod(0o755)
        call([image,'--appimage-extract-and-run','--self-test'],env=env)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',default=platform_key());args=parser.parse_args()
    if args.target!=platform_key():raise RuntimeError('Native package target must match the actual build host OS/CPU')
    from install_over import baseline_session
    with baseline_session(args.target) if os.environ.get('GITHUB_ACTIONS')=='true' else nullcontext() as upgrade:
        OUT.mkdir(parents=True,exist_ok=True);node=resources();freeze(node)
        if os.name=='nt':windows(args.target)
        elif sys.platform=='darwin':macos(args.target)
        else:linux(args.target)
        artifacts=[]
        for file in OUT.iterdir():
            if file.suffix in {'.exe','.pkg','.deb','.AppImage'}:
                artifacts.append({'name':file.name,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
        if not artifacts:raise RuntimeError('No real native packages were produced')
        from dkord_desktop.qt import BINDING, QtCore
        if os.name=='nt':
            from dkord_desktop.codec import ffmpeg_exe
            require_pe_architecture(Path(ffmpeg_exe()),'x86' if WINDOWS_X86 else 'x64')
        preview={'channel':'development-preview','version':__version__,'target':args.target,'source':os.environ.get('DKORD_SOURCE_SHA','local'),
                 'trusted_signed_release':False,'notarized':False,'artifacts':artifacts}
        preview['installOver']=upgrade([OUT/item['name'] for item in artifacts]) if upgrade else None
        preview['runtime']={'python_bits':struct.calcsize('P')*8,'qt_binding':BINDING,'qt_version':QtCore.QT_VERSION_STR,
                            'audio_probe':'ffmpeg' if WINDOWS_X86 else 'pyav'}
        if os.name=='nt':preview['runtime']['verified_pe_payloads']={'application':'x86' if WINDOWS_X86 else 'x64','node':'x86' if WINDOWS_X86 else 'x64','ffmpeg':'x86' if WINDOWS_X86 else 'x64'}
        if WINDOWS_X86:
            preview['codec_source']=json.loads((ROOT/'.runtime/FFmpeg-source.json').read_text(encoding='utf-8'))
            preview['runtime']['verified_pe_payloads']['ffprobe']='x86'
        if args.target.startswith('linux-'):preview['minimum_glibc']='2.39'
        (OUT/f'preview-{args.target}.json').write_text(json.dumps(preview,indent=2)+'\n')
        print(json.dumps(preview,indent=2))

if __name__=='__main__':main()
