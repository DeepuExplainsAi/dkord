"""One owner-authorized v0.10.0 push on the assigned branch; historical requests stay consumed."""
import json
import os
from pathlib import Path
import subprocess
import sys
from validate_release_request import ROOT, SHA, app_version

REQUEST = Path('.github/release-requests/v0.10.0.json')
BRANCH = 'arena/a0209191-dkord'
REPOSITORY = 'DeepuExplainsAi/dkord'
TAG = 'v0.10.0'
CODE = 14


def validate(request, event, *, event_name, ref, repository, sha, tag, version_name, version_code):
    if not isinstance(request, dict) or set(request) != {'tag', 'versionCode', 'branch', 'validatedHead'}:
        raise ValueError('Unexpected release-request schema.')
    if not isinstance(event, dict) or event_name != 'push' or ref != f'refs/heads/{BRANCH}' or event.get('ref') != ref:
        raise ValueError('Only this explicitly authorized trusted-branch push can request publication.')
    if repository != REPOSITORY or event.get('repository', {}).get('full_name') != REPOSITORY:
        raise ValueError('Other repositories/forks cannot publish this release.')
    if event.get('forced') is not False or event.get('deleted') is not False:
        raise ValueError('Forced/deleted pushes cannot publish.')
    if request['tag'] != TAG or tag != TAG or request['branch'] != BRANCH or version_name != TAG[1:]:
        raise ValueError('Only v0.10.0 on the assigned branch is authorized; old requests are consumed.')
    if type(request['versionCode']) is not int or request['versionCode'] != CODE or version_code != CODE:
        raise ValueError('Only the prepared increasing versionCode14 is authorized.')
    previous = request['validatedHead']
    if not isinstance(previous, str) or not SHA.fullmatch(previous) or int(previous, 16) == 0 or event.get('before') != previous:
        raise ValueError('Push must start at its recorded validated source head.')
    if not isinstance(sha, str) or not SHA.fullmatch(sha) or int(sha, 16) == 0 or event.get('after') != sha or sha == previous:
        raise ValueError('Target must be the new release-request commit.')
    return TAG


def validate_changes(previous, parent, changes):
    if parent != previous or changes != [REQUEST.as_posix()]:
        raise ValueError('Publication push must be one direct metadata-only child of the validated head.')


def main():
    request = json.loads((ROOT / REQUEST).read_text(encoding='utf-8'))
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
    name, code = app_version((ROOT / 'app/build.gradle.kts').read_text(encoding='utf-8'))
    sha = os.environ.get('GITHUB_SHA')
    validate(request, event, event_name=os.environ.get('GITHUB_EVENT_NAME'), ref=os.environ.get('GITHUB_REF'),
             repository=os.environ.get('GITHUB_REPOSITORY'), sha=sha, tag=os.environ.get('TAG'), version_name=name, version_code=code)
    parent = subprocess.check_output(['git', 'rev-parse', sha + '^'], cwd=ROOT, text=True).strip()
    changes = subprocess.check_output(['git', 'diff', '--name-only', request['validatedHead'], sha], cwd=ROOT, text=True).splitlines()
    validate_changes(request['validatedHead'], parent, changes)
    print('Authorized v0.10.0 / code14 metadata-only request validated. Signing, full CI and APK compatibility gates remain mandatory.')

if __name__ == '__main__':
    try:
        main()
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit('Release request refused: ' + str(error))
