"""Private, local-only, allowlisted diagnostics. No URL/room code/query/path log.

Reports are produced only on explicit Copy. This module cannot upload anything
and deliberately does not accept exception text, titles or other user metadata.
"""
from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
import re

KINDS={'playback','download','background','video','rooms'}
CODES={'prepare_failed','media_failed','failed','unavailable','cancelled','reconnecting'}


class Diagnostics:
    def __init__(self,clock=lambda:datetime.now(timezone.utc)):
        self.events=deque(maxlen=60);self.clock=clock

    def record(self,kind,code):
        if kind not in KINDS or code not in CODES:
            raise ValueError('Only allowlisted diagnostic event codes are accepted')
        self.events.append((self.clock().isoformat(timespec='seconds'),kind,code))

    def report(self,version,target,qt,source):
        if (not all(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9 ._-]{1,80}',value) for value in (version,target,qt))
                or source not in {'none','online','local'}):
            raise ValueError('Diagnostic environment must not contain private data')
        lines=['Dkord playback diagnostics',f'Version: {version}',f'Platform: {target}',f'Qt: {qt}',f'Audio source: {source}',
               'Local report. No URLs, song metadata, paths, queries or room codes.','Events:']
        lines.extend(f'{stamp} {kind}: {code}' for stamp,kind,code in self.events)
        if not self.events:lines.append('No recent failures recorded.')
        return '\n'.join(lines)
