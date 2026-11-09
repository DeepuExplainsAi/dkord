"""Existing 64-bit codecs stay unchanged. Win32 uses our pinned current native FFmpeg build."""
from pathlib import Path
import sys
from .platforms import WINDOWS_X86


def ffmpeg_exe() -> str:
    if WINDOWS_X86:
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
        for file in (root/'runtime/ffmpeg.exe',root/'.runtime/ffmpeg.exe'):
            if file.is_file():return str(file)
        raise RuntimeError('The genuine Windows32 FFmpeg runtime is missing; do not substitute an x64/PATH binary')
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def ffprobe_exe() -> str:
    if not WINDOWS_X86:raise RuntimeError('The Win32 probe locator is only used by the compatibility profile')
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    for file in (root/'runtime/ffprobe.exe',root/'.runtime/ffprobe.exe'):
        if file.is_file():return str(file)
    raise RuntimeError('The genuine Windows32 ffprobe runtime is missing')
