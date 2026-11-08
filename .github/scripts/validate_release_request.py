"""Validate the owner's narrowly scoped v0.8.2 trusted-push release request.

This does not sign or publish. The existing release workflow still runs its full tests,
original-key signing and actual old/new APK compatibility gates afterwards.
"""
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
REQUEST = Path('.github/release-requests/v0.8.2.json')
BRANCH = 'arena/59a2f745-dkord'
REPOSITORY = 'DeepuExplainsAi/dkord'
TAG = 'v0.8.2'
CODE = 11
SHA = re.compile(r'[0-9a-f]{40}')


def app_version(text):
    names = re.findall(r'^\s*versionName\s*=\s*"([^"]+)"\s*$', text, re.MULTILINE)
    codes = re.findall(r'^\s*versionCode\s*=\s*(\d+)\s*$', text, re.MULTILINE)
    if len(names) != 1 or len(codes) != 1:
        raise ValueError('App must declare one versionName and versionCode.')
    return names[0], int(codes[0])


def validate(request, event, *, event_name, ref, repository, sha, tag, version_name, version_code):
    if not isinstance(request, dict) or set(request) != {'tag', 'versionCode', 'branch', 'validatedHead'}:
        raise ValueError('Release request fields do not match the authorized metadata schema.')
    if not isinstance(event, dict):
        raise ValueError('Push event must be an object.')
    if event_name != 'push' or ref != f'refs/heads/{BRANCH}' or event.get('ref') != ref:
        raise ValueError('Only the explicitly authorized trusted-branch push may request this release.')
    if repository != REPOSITORY or event.get('repository', {}).get('full_name') != REPOSITORY:
        raise ValueError('Release request is not from the authorized repository.')
    if event.get('deleted') is not False or event.get('forced') is not False:
        raise ValueError('Deleted or force-pushed refs cannot request this release.')
    if request['branch'] != BRANCH or request['tag'] != TAG or tag != TAG or version_name != TAG[1:]:
        raise ValueError('This trusted-push route is authorized for v0.8.2 on the assigned branch only.')
    if type(request['versionCode']) is not int or request['versionCode'] != CODE or version_code != CODE:
        raise ValueError('Release request must match the authorized increasing app versionCode11.')
    previous = request['validatedHead']
    if not isinstance(previous, str) or not SHA.fullmatch(previous) or int(previous, 16) == 0:
        raise ValueError('Request must identify a real previously validated source commit.')
    if event.get('before') != previous:
        raise ValueError('Release-request push must start from its recorded validated source head.')
    if not isinstance(sha, str) or not SHA.fullmatch(sha) or int(sha, 16) == 0 or event.get('after') != sha or sha == previous:
        raise ValueError('Workflow target must be the new release-request push commit.')
    return TAG


def main():
    name, code = app_version((ROOT / 'app/build.gradle.kts').read_text(encoding='utf-8'))
    request = json.loads((ROOT / REQUEST).read_text(encoding='utf-8'))
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
    tag = validate(request, event,
                   event_name=os.environ.get('GITHUB_EVENT_NAME'),
                   ref=os.environ.get('GITHUB_REF'),
                   repository=os.environ.get('GITHUB_REPOSITORY'),
                   sha=os.environ.get('GITHUB_SHA'), tag=os.environ.get('TAG'),
                   version_name=name, version_code=code)
    print(f'Authorized trusted-branch release request validated: {tag} / versionCode{code}.')


if __name__ == '__main__':
    try:
        main()
    except (KeyError, OSError, ValueError) as error:
        sys.exit(f'Release request refused: {error}')
