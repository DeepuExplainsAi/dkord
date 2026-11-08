"""Stream real command output; on failure surface a bounded tail in the GitHub Check API.

The sandbox cannot read redirected Actions/Azure log archives. This preserves the original
exit code and tests; no retries, skip, credentials or failure suppression are introduced.
"""
from collections import deque
import os
from pathlib import Path
import subprocess
import sys

args=sys.argv[1:]
if len(args)<2:
    raise SystemExit('Usage: ci_run.py phase command [arguments]')
phase,*command=args
log=Path(os.environ.get('RUNNER_TEMP','.'))/f'dkord-desktop-{phase}.log'
tail=deque(maxlen=75)
with log.open('w',encoding='utf-8') as file:
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1)
    for line in process.stdout:
        print(line,end='',flush=True);file.write(line);file.flush();tail.append(line)
    code=process.wait()
if code and phase=='screenshot' and '--capture-ui' in command:
    try:
        report=Path(command[command.index('--capture-ui')+1])/'capture-error.txt'
        if report.is_file() and not report.is_symlink():
            with report.open(encoding='utf-8') as file:tail.extend(file.read(8000).splitlines(keepends=True))
    except OSError as error:
        tail.append('Could not read isolated screenshot failure report: '+str(error))
if code:
    text=(''.join(tail) or 'Native process exited without stdout; consult self-test report.').strip()[-2800:]
    text=text.replace('%','%25').replace('\r','%0D').replace('\n','%0A')
    print(f'::error title=Desktop {phase} failed (exit {code})::{text}',flush=True)
raise SystemExit(code)
