"""Fresh explicitly requested Android + PC 0.10.2 publication, never an old route.

Only one metadata-only direct child of an already validated source head may enter.
APK certificate/install-over, exact-child Android/native/screenshot and signed
PC-manifest gates are mandatory downstream. No old artifact/tag is overwritten.
"""
import json
import os
from pathlib import Path
import re
import subprocess
from validate_release_request import ROOT,SHA
from validate_release_request_v010 import app_version

BRANCH='arena/a6a6bbda-dkord'
REPOSITORY='DeepuExplainsAi/dkord'
TAG='v0.10.2'
CODE=16
VERSION='0.10.2'
REQUEST=Path('.github/release-requests/v0.10.2.json')


def validate(request,event,*,event_name,ref,repository,sha,tag,version_name,version_code,desktop_version):
    if not isinstance(request,dict) or set(request)!={'tag','versionCode','desktopVersion','branch','validatedHead'}:
        raise ValueError('Unexpected new Android/PC release request schema')
    if not isinstance(event,dict) or event_name!='push' or ref!='refs/heads/'+BRANCH or event.get('ref')!=ref:
        raise ValueError('Only the freshly authorized assigned-branch push can publish')
    if repository!=REPOSITORY or event.get('repository',{}).get('full_name')!=REPOSITORY:
        raise ValueError('Wrong release repository')
    if event.get('forced') is not False or event.get('deleted') is not False:
        raise ValueError('Forced/deleted release request refused')
    if (tag!=TAG or version_name!=VERSION or type(version_code) is not int or version_code!=CODE or desktop_version!=VERSION
        or request['tag']!=TAG or type(request['versionCode']) is not int or request['versionCode']!=CODE
        or request['desktopVersion']!=VERSION or request['branch']!=BRANCH):
        raise ValueError('Only the new 0.10.2/code16 Android and matching PC release is authorized')
    previous=request['validatedHead']
    if not isinstance(previous,str) or not SHA.fullmatch(previous) or int(previous,16)==0 or event.get('before')!=previous:
        raise ValueError('Release request must start at its recorded validated parent')
    if not isinstance(sha,str) or not SHA.fullmatch(sha) or int(sha,16)==0 or sha==previous or event.get('after')!=sha:
        raise ValueError('Wrong fresh release metadata commit')
    return TAG


def validate_changes(previous,parent,changes):
    if parent!=previous or changes!=[REQUEST.as_posix()]:
        raise ValueError('Release must be one direct metadata-only child; code changes require new validation')


def main():
    request=json.loads((ROOT/REQUEST).read_text())
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    version_name,version_code=app_version((ROOT/'app/build.gradle.kts').read_text())
    desktop_version=re.search(r'__version__\s*=\s*"([^"]+)"',(ROOT/'desktop/dkord_desktop/__init__.py').read_text())[1]
    sha=os.environ['GITHUB_SHA']
    validate(request,event,event_name=os.environ['GITHUB_EVENT_NAME'],ref=os.environ['GITHUB_REF'],repository=os.environ['GITHUB_REPOSITORY'],sha=sha,
             tag=os.environ['TAG'],version_name=version_name,version_code=version_code,desktop_version=desktop_version)
    parent=subprocess.check_output(['git','rev-parse',sha+'^'],cwd=ROOT,text=True).strip()
    changes=subprocess.check_output(['git','diff','--name-only',request['validatedHead'],sha],cwd=ROOT,text=True).splitlines()
    validate_changes(request['validatedHead'],parent,changes)
    print('Fresh 0.10.2/code16 Android + PC request validated. Original identity/data and exact-child proof gates remain mandatory. No old release is replaced.')


if __name__=='__main__':
    main()
