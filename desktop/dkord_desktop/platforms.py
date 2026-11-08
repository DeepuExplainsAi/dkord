"""Installed-process architecture, not the host CPU reported by WoW64."""
from __future__ import annotations
import platform
import struct

TARGETS = ('windows-x64', 'windows-x86', 'macos-x64', 'macos-arm64', 'linux-x64', 'linux-arm64')


def platform_key(system: str | None = None, machine: str | None = None, pointer_bits: int | None = None) -> str:
    system = system or platform.system()
    machine = (machine or platform.machine()).casefold()
    bits = struct.calcsize('P') * 8 if pointer_bits is None else pointer_bits
    if system == 'Windows' and bits == 32 and machine in {'amd64', 'x86_64', 'x86', 'i386', 'i686', 'arm64', 'aarch64'}:
        return 'windows-x86'  # A real x86 process can run under WoW64 on an x64/arm64 host.
    os_name = {'Windows': 'windows', 'Darwin': 'macos', 'Linux': 'linux'}.get(system)
    arch = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(machine)
    target = f'{os_name}-{arch}'
    if bits != 64 or target not in TARGETS:
        raise ValueError('No supported desktop OS/CPU build for this installation')
    return target


WINDOWS_X86 = platform.system() == 'Windows' and struct.calcsize('P') == 4
