"""Fetch bounded, SHA-pinned build dependencies through GitHub's asset API.

Only transient dependency-download transport failures may retry (max3). Tests,
installers, hashes and native acceptance never retry or get substituted. GitHub's
CLI handles authenticated redirects; tokens never go into URLs/argv/output files.
"""
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import time


def download_asset(repository:str,asset_id:int,output:Path,sha256:str):
    if not re.fullmatch(r'AppImage/(appimagetool|type2-runtime)',repository) or type(asset_id) is not int or asset_id<=0 or not re.fullmatch('[0-9a-f]{64}',sha256):
        raise ValueError('An explicit upstream asset identity and SHA-256 are required')
    if output.exists() or output.is_symlink():raise ValueError('Never overwrite an existing build dependency')
    command=['gh','api','-H','Accept: application/octet-stream',f'repos/{repository}/releases/assets/{asset_id}']
    with tempfile.TemporaryDirectory(prefix='dkord-pinned-dependency-',dir=output.parent) as temporary:
        staging=Path(temporary)/'asset'
        for attempt in range(3):
            try:
                with staging.open('wb') as file:
                    result=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=file,stderr=subprocess.PIPE,timeout=90,check=False)
                if result.returncode==0:
                    if not 1024<=staging.stat().st_size<=32*1024*1024 or hashlib.sha256(staging.read_bytes()).hexdigest()!=sha256:
                        raise ValueError('Pinned upstream dependency changed; review, never retry/substitute its bytes')
                    staging.rename(output);return output
                error=result.stderr.decode('utf-8',errors='replace')
                if not re.search(r'HTTP (429|500|502|503|504)',error) or attempt==2:
                    raise RuntimeError('Pinned dependency asset download failed; no unverified fallback')
            except subprocess.TimeoutExpired:
                if attempt==2:raise RuntimeError('Pinned dependency transport timed out') from None
            time.sleep(2*(attempt+1))
