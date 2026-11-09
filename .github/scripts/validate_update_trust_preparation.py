"""One fresh PUBLIC-certificate-only preparation request, never a publication route."""
import json
import os
from pathlib import Path
import subprocess
from validate_release_request import ROOT, SHA

BRANCH='arena/a6a6bbda-dkord'
REPO='DeepuExplainsAi/dkord'
REQUEST=Path('.github/release-preparations/v0.10.1-update-root.json')
PURPOSE='verify-existing-public-update-root'


def validate(request,event,*,event_name,ref,repository,sha):
    if not isinstance(request,dict) or set(request)!={'purpose','version','branch','preparedHead'}:
        raise ValueError('Unexpected public preparation schema')
    if event_name!='push' or ref!='refs/heads/'+BRANCH or event.get('ref')!=ref:
        raise ValueError('Only the explicitly requested assigned-branch push may prepare the public root')
    if repository!=REPO or event.get('repository',{}).get('full_name')!=REPO:
        raise ValueError('Wrong repository')
    if event.get('forced') is not False or event.get('deleted') is not False:
        raise ValueError('Forced/deleted request refused')
    if request['purpose']!=PURPOSE or request['version']!='0.10.1' or request['branch']!=BRANCH:
        raise ValueError('Wrong public-only preparation purpose/version')
    previous=request['preparedHead']
    if not isinstance(previous,str) or not SHA.fullmatch(previous) or int(previous,16)==0 or event.get('before')!=previous:
        raise ValueError('Wrong recorded preparation parent')
    if not isinstance(sha,str) or not SHA.fullmatch(sha) or int(sha,16)==0 or sha==previous or event.get('after')!=sha:
        raise ValueError('Wrong fresh metadata child')
    return previous


def validate_changes(previous,parent,changes):
    if parent!=previous or changes!=[REQUEST.as_posix()]:
        raise ValueError('Public preparation push must be one direct metadata-only child')


def main():
    request=json.loads((ROOT/REQUEST).read_text())
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    sha=os.environ['GITHUB_SHA']
    previous=validate(request,event,event_name=os.environ['GITHUB_EVENT_NAME'],ref=os.environ['GITHUB_REF'],repository=os.environ['GITHUB_REPOSITORY'],sha=sha)
    parent=subprocess.check_output(['git','rev-parse',sha+'^'],cwd=ROOT,text=True).strip()
    changes=subprocess.check_output(['git','diff','--name-only',previous,sha],cwd=ROOT,text=True).splitlines()
    validate_changes(previous,parent,changes)
    print('Public certificate preparation authorized; no private-key export, release, tag, APK or installer publication.')


if __name__=='__main__':
    main()
