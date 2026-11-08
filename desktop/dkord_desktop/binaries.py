"""Inspect real PE payloads. An x86 Inno bootstrap alone does not prove the bundled app is x86."""
from pathlib import Path
import struct


def pe_architecture(path: Path) -> str:
    with path.open('rb') as source:
        header=source.read(64)
        if len(header)!=64 or header[:2]!=b'MZ':raise ValueError('Missing PE DOS header: '+path.name)
        offset=struct.unpack_from('<I',header,60)[0]
        if not 64<=offset<=min(path.stat().st_size-6,8*1024*1024):raise ValueError('Invalid PE offset')
        source.seek(offset);pe=source.read(6)
        if pe[:4]!=b'PE\0\0':raise ValueError('Invalid PE signature')
        arch={0x14c:'x86',0x8664:'x64',0xaa64:'arm64'}.get(struct.unpack('<H',pe[4:])[0])
        if arch is None:raise ValueError('Unsupported PE machine')
        return arch


def require_pe_architecture(path: Path, expected: str) -> None:
    actual=pe_architecture(path)
    if actual!=expected:raise ValueError(f'{path.name}: expected {expected}, actual PE payload is {actual}')
