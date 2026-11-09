"""Real code14 -> code15 install -r with data assertions on isolated CI emulator.

The existing protected identity has already passed apksigner comparison. The same
signed instrumentation APK first seeds the actual published old app, then reads
its real Room/preferences/queue/private+MediaStore/Studio state through the newly
installed app. Never uninstall, clear data, hide errors or retry a failing test.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

CLASS='app.dkord.InstallOverPersistenceTest'
RUNNER='app.dkord.test/androidx.test.runner.AndroidJUnitRunner'


def command(*args):
    result=subprocess.run(['adb',*map(str,args)],check=True,text=True,capture_output=True,timeout=180)
    return result.stdout


def package():
    value=command('shell','dumpsys','package','app.dkord')
    code=re.search(r'\bversionCode=(\d+)\b',value)
    uid=re.search(r'\buserId=(\d+)\b',value)
    if not code or not uid:raise ValueError('Installed app package/version/UID unavailable')
    return int(code[1]),int(uid[1])


def phase(name):
    result=command('shell','am','instrument','-w','-r','-e','class',CLASS,'-e','dkordUpgradePhase',name,RUNNER)
    print(result)
    if not re.search(r'OK \(1 test\)',result) or 'INSTRUMENTATION_CODE: -1' not in result:
        raise ValueError('Real Android install-over '+name+' assertions failed; no retries/reset permitted')


def verify(old,new,test,output):
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!='DeepuExplainsAi/dkord':
        raise ValueError('Production APK installer fixture is restricted to disposable CI')
    if command('shell','getprop','ro.kernel.qemu').strip()!='1':raise ValueError('An isolated emulator is required')
    if hashlib.sha256(old.read_bytes()).hexdigest()!='d2a354903e3eda3707aab77721a391ee0eee3134010284e7ffd1a3e28f2deed9':
        raise ValueError('Only the immutable published original code14 APK can be the baseline')
    command('install','-r','-t',old)
    old_code,old_uid=package()
    if old_code!=14:raise ValueError('Wrong original installed version')
    command('install','-r','-t',test);phase('seed')
    command('shell','am','force-stop','app.dkord')
    command('install','-r','-t',new)
    new_code,new_uid=package()
    if new_code!=15 or old_uid!=new_uid:raise ValueError('Real install-over failed to keep app UID/increase version')
    phase('verify')
    receipt=dict(format=1,package='app.dkord',baselineTag='v0.10.0',fromVersionCode=old_code,toVersionCode=new_code,
                 source=os.environ['GITHUB_SHA'],sameUid=True,noUninstall=True,noDataReset=True,
                 realRoom=True,settings=True,queue=True,privateDownload=True,mediaStoreExport=True,studioProjectAndSourceBytes=True)
    with output.open('x') as file:json.dump(receipt,file,indent=2)
    print('::notice title=Actual Android install-over::Original signed code14 -> code15, same UID, actual Room/likes/history/playlist/settings/queue/private and device audio/Studio source bytes preserved on isolated API35 emulator. Not a physical-device pass.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('old','new','test','output'):parser.add_argument('--'+arg,type=Path,required=True)
    args=parser.parse_args();verify(args.old,args.new,args.test,args.output)
