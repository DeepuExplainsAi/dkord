"""Execute the actual frozen host application; never relabel another CPU/OS capture."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dkord_desktop.platforms import platform_key
from gallery_proof import verify


def main(output, source, target):
    if target != platform_key():
        raise ValueError('Gallery must execute on its actual OS/CPU host')
    root = Path(__file__).resolve().parents[1]
    bundle = root / '.artifacts/bundle'
    executable = bundle / ('Dkord.app/Contents/MacOS/Dkord' if sys.platform == 'darwin'
                           else 'Dkord/Dkord.exe' if os.name == 'nt' else 'Dkord/Dkord')
    if not executable.is_file():
        raise ValueError('Real frozen native executable is required')
    env = dict(os.environ, DKORD_SOURCE_SHA=source)
    env['QT_QPA_PLATFORM'] = 'windows' if os.name == 'nt' else 'cocoa' if sys.platform == 'darwin' else 'xcb'
    command = [str(executable), '--capture-gallery', str(output.resolve())]
    if sys.platform.startswith('linux'):
        command = ['xvfb-run', '-a', '-s', '-screen 0 1600x1100x24', *command]
    try:
        subprocess.run(command, check=True, env=env, timeout=180)
    except subprocess.CalledProcessError:
        report = output / 'capture-error.txt'
        if report.is_file() and not report.is_symlink():
            print(report.read_text(encoding='utf-8')[-8000:], flush=True)
        raise
    proof = verify(output, source, target)
    print(f'::notice title=Actual native gallery::{target}: {len(proof["images"])} real frozen-window/dialog captures; original PNG hashes and runtime verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', required=True)
    args = parser.parse_args()
    main(args.output, args.source, args.target)
