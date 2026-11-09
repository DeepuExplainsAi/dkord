"""Fresh owner-requested Windows x86 preview, disjoint from consumed Android publication routes."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from validate_release_request import ROOT, SHA

BRANCH='arena/a6a6bbda-dkord'
REPO='DeepuExplainsAi/dkord'
TAG='desktop-v0.10.0-preview.2'
VERSION='0.10.0'
REQUEST=Path('.github/release-requests/'+TAG+'.json')


def validate(request,event,*,event_name,ref,repository,sha,tag,version):
    if not isinstance(request,dict) or set(request)!={'tag','version','branch','validatedHead'}:raise ValueError('Unexpected preview request schema')
    if not isinstance(event,dict) or event_name!='push' or ref!='refs/heads/'+BRANCH or event.get('ref')!=ref:raise ValueError('Only the assigned trusted branch push is authorized')
    if repository!=REPO or event.get('repository',{}).get('full_name')!=REPO:raise ValueError('Wrong repository')
    if event.get('forced') is not False or event.get('deleted') is not False:raise ValueError('Forced/deleted push refused')
    if request['tag']!=TAG or tag!=TAG or request['version']!=VERSION or version!=VERSION or request['branch']!=BRANCH:raise ValueError('Only the freshly requested x86 desktop preview is authorized; Android/old requests are consumed')
    before=request['validatedHead']
    if not isinstance(before,str) or not SHA.fullmatch(before) or int(before,16)==0 or event.get('before')!=before:raise ValueError('Publication must start at the recorded validated source head')
    if not isinstance(sha,str) or not SHA.fullmatch(sha) or int(sha,16)==0 or sha==before or event.get('after')!=sha:raise ValueError('Wrong new preview request commit')
    return TAG


def validate_changes(previous,parent,changes):
    if parent!=previous or changes!=[REQUEST.as_posix()]:raise ValueError('Only one direct metadata-only child may request publication')


def main():
    request=json.loads((ROOT/REQUEST).read_text())
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    version=re.search(r'__version__\s*=\s*"([^"]+)"',(ROOT/'desktop/dkord_desktop/__init__.py').read_text())[1]
    sha=os.environ['GITHUB_SHA']
    validate(request,event,event_name=os.environ['GITHUB_EVENT_NAME'],ref=os.environ['GITHUB_REF'],repository=os.environ['GITHUB_REPOSITORY'],sha=sha,tag=os.environ['TAG'],version=version)
    parent=subprocess.check_output(['git','rev-parse',sha+'^'],text=True,cwd=ROOT).strip()
    changes=subprocess.check_output(['git','diff','--name-only',request['validatedHead'],sha],text=True,cwd=ROOT).splitlines()
    validate_changes(request['validatedHead'],parent,changes)
    print('Fresh Windows32 native desktop PREVIEW request validated. Full exact-head Android, six-host native and real screenshot gates remain mandatory. No signing keys or Android release mutations.')

if __name__=='__main__':
    try:main()
    except (KeyError,OSError,ValueError,subprocess.CalledProcessError) as error:sys.exit('Preview publication refused: '+str(error))
