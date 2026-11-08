#!/usr/bin/env python3
"""Surface actual Kotlin/AAPT/Gradle errors from read-only CI, without external log downloads."""
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
if path.exists():
    lines = re.sub(r'\x1b\[[0-9;]*m', '', path.read_text(errors='replace')).splitlines()
    diagnostics = [line for line in lines if line.startswith(('e: ', 'e:file:', 'error:', 'ERROR:')) or ': error:' in line]
    if not diagnostics:
        for index, line in enumerate(lines):
            if line == '* What went wrong:':
                diagnostics = lines[index + 1:index + 14]
                break
    for line in diagnostics[:30]:
        safe = line[:1800].replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::error title=Android build diagnostic::' + safe)
