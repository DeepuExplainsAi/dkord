"""Current Win32 audio FFmpeg, built with the real MSVC x86 toolchain, not the 2019 wheel codec."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dkord_desktop.binaries import require_pe_architecture
from dkord_desktop.platforms import platform_key

VERSION='8.1.3'
COMMIT='1041abdc962f4cc4f394aa8de9dc5236c0c3b9e7'
ARCHIVE_SHA256='a406fe831cbb605f5fe50e43eb566e502ae63ff3b3206bfa744e4b31b8bb73ac'
URL='https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/'+COMMIT
FLAGS=[
    '--toolchain=msvc','--arch=x86','--target-os=win32','--cc=cl','--ld=link','--ar=lib',
    '--disable-autodetect','--disable-doc','--disable-debug','--disable-asm','--disable-x86asm',
    '--disable-network','--disable-shared','--enable-static','--enable-gpl','--enable-version3',
    '--disable-everything','--enable-ffmpeg','--disable-ffplay','--enable-ffprobe',
    '--enable-avformat','--enable-avcodec','--enable-avfilter','--enable-swresample',
    '--enable-protocol=file,pipe',
    '--enable-demuxer=mov,mp3,wav,matroska,ogg,flac,aac,ape,asf,aiff',
    '--enable-muxer=mp4,mov,wav,pcm_s16le,null',
    '--enable-decoder=aac,aac_fixed,mp3,mp3float,pcm_s16le,pcm_s24le,pcm_s32le,pcm_f32le,pcm_f64le,pcm_u8,flac,vorbis,opus,alac,wmav2',
    '--enable-encoder=aac,pcm_s16le','--enable-parser=aac,mpegaudio,flac,opus,vorbis',
    '--enable-filter=atrim,asetpts,aresample,aformat,concat,anull,abuffer,abuffersink',
    '--extra-cflags=-D_WIN32_WINNT=0x0A00',
]


def main():
    if platform_key()!='windows-x86':raise RuntimeError('This codec build must use genuine Windows32 Python')
    compiler=shutil.which('cl.exe') or shutil.which('cl')
    if not compiler:raise RuntimeError('Initialize the MSVC x86 developer environment first')
    runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dkord-ffmpeg32-') as temporary:
        temp=Path(temporary);archive=temp/'source.tar.gz';urllib.request.urlretrieve(URL,archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=ARCHIVE_SHA256:raise RuntimeError('Pinned FFmpeg source digest mismatch')
        with tarfile.open(archive,'r:gz') as bundle:
            for member in bundle.getmembers():
                path=(temp/member.name).resolve()
                if temp.resolve() not in path.parents or not (member.isfile() or member.isdir()):raise RuntimeError('Unexpected source archive path/type')
            bundle.extractall(temp)
        source=temp/('FFmpeg-'+COMMIT)
        env={**os.environ,'DKORD_MSVC_BIN':str(Path(compiler).parent),'DKORD_FFMPEG_SOURCE':str(source),
             'DKORD_FFMPEG_FLAGS':json.dumps(FLAGS),'MSYS2_ARG_CONV_EXCL':'*','MSYS_NO_PATHCONV':'1'}
        # Use the inherited MSYS2 environment supplied by CI. Prepend the actual MSVC
        # x86 bin directory so Unix coreutils/link cannot shadow Microsoft's linker.
        script='''set -euo pipefail
export PATH="$(cygpath -u "$DKORD_MSVC_BIN"):$PATH"
cd "$(cygpath -u "$DKORD_FFMPEG_SOURCE")"
which cl; which link; which make
'''
        import shlex
        script+='sh ./configure '+ ' '.join(shlex.quote(flag) for flag in FLAGS)+'\nmake -j4\n'
        result=subprocess.run(['bash','--noprofile','--norc','-c',script],env=env)
        if result.returncode:
            config=source/'ffbuild/config.log'
            if config.exists():print(config.read_text(errors='replace')[-14000:],flush=True)
            raise RuntimeError('Current native FFmpeg x86 compilation failed')
        binary=source/'ffmpeg.exe';require_pe_architecture(binary,'x86')
        shutil.copy2(binary,runtime/'ffmpeg.exe')
        probe=source/'ffprobe.exe';require_pe_architecture(probe,'x86');shutil.copy2(probe,runtime/'ffprobe.exe')
        shutil.copy2(source/'COPYING.GPLv3',runtime/'FFmpeg-COPYING.GPLv3')
        reported=subprocess.check_output([str(binary),'-version'],text=True,errors='replace')
        if 'ffmpeg version '+VERSION not in reported.splitlines()[0]:raise RuntimeError('Unexpected FFmpeg version')
        record={'version':VERSION,'source_commit':COMMIT,'source_archive':URL,'source_archive_sha256':ARCHIVE_SHA256,
                'configure':FLAGS,'architecture':'x86','binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'probe_sha256':hashlib.sha256(probe.read_bytes()).hexdigest(),
                'license':'GPL-3.0-or-later; complete corresponding source at the pinned source archive URL'}
        (runtime/'FFmpeg-source.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        print('::notice title=Actual Win32 codec::FFmpeg'+VERSION+' native PE=x86 compiled from digest-pinned '+COMMIT+'; old imageio4.2.2 codec is NOT bundled.')

if __name__=='__main__':main()
