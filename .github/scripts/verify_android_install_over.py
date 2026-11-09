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
BASELINES={
    'v0.10.0': (14,15,'d2a354903e3eda3707aab77721a391ee0eee3134010284e7ffd1a3e28f2deed9'),
    'v0.10.1': (15,16,'04ad9ef99e7d4eb913d08aca6eda03af5796d69fe9eecdc1adb8225895098e4d'),
}


def diagnostic(title,text):
    # These commands run only in the disposable fixture after keystore removal.
    # Keep the failing evidence visible via Checks without retrying/resetting data;
    # each retained annotation is capped by GitHub at 4096 characters.
    text=text[-14000:]
    for index,start in enumerate(range(0,len(text),3500),1):
        piece=text[start:start+3500].replace('%','%25').replace('\r','%0D').replace('\n','%0A')
        print(f'::error title={title} part {index}::'+piece)


def command(*args):
    try:
        result=subprocess.run(['adb',*map(str,args)],check=True,text=True,capture_output=True,timeout=180)
    except subprocess.CalledProcessError as error:
        diagnostic('Android install-over adb failure',(error.stdout or '')+'\n'+(error.stderr or ''))
        raise
    return result.stdout


def package():
    value=command('shell','dumpsys','package','app.dkord')
    code=re.search(r'\bversionCode=(\d+)\b',value)
    # dumpsys's userId/appId display label is not a stable UID interface. Ask the
    # actual package manager for the installed owner-user UID, with exact package
    # matching: the separately installed app.dkord.test must never satisfy this.
    listing=command('shell','cmd','package','list','packages','-U','--user','0','app.dkord')
    uids=re.findall(r'^package:app\.dkord\s+uid:([1-9]\d*)\s*$',listing,re.MULTILINE)
    if not code or len(uids)!=1:
        fields=[line for line in value.splitlines() if any(key in line for key in ('versionCode=','userId=','appId=','Package [','User 0:'))]
        diagnostic('Android install-over package metadata','\n'.join(fields)+'\n'+listing)
        raise ValueError('Installed app package/version/owner-user UID unavailable or ambiguous')
    return int(code[1]),int(uids[0])


def phase(name):
    result=command('shell','am','instrument','-w','-r','-e','class',CLASS,'-e','dkordUpgradePhase',name,RUNNER)
    print(result)
    if not re.search(r'OK \(1 test\)',result) or 'INSTRUMENTATION_CODE: -1' not in result:
        diagnostic('Android install-over '+name+' assertions',result)
        raise ValueError('Real Android install-over '+name+' assertions failed; no retries/reset permitted')


def verify(old,new,test,output,baseline='v0.10.0',target_code=15):
    if baseline not in BASELINES or type(target_code) is not int or target_code!=BASELINES[baseline][1]:
        raise ValueError('Only recorded immutable baseline/next-code upgrade pairs are allowed')
    expected_old,expected_new,old_hash=BASELINES[baseline]
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!='DeepuExplainsAi/dkord':
        raise ValueError('Production APK installer fixture is restricted to disposable CI')
    if command('shell','getprop','ro.kernel.qemu').strip()!='1':raise ValueError('An isolated emulator is required')
    if hashlib.sha256(old.read_bytes()).hexdigest()!=old_hash:
        raise ValueError('Only the immutable published original-key APK can be the baseline')
    command('install','-r','-t',old)
    old_code,old_uid=package()
    if old_code!=expected_old:raise ValueError('Wrong original installed version')
    command('install','-r','-t',test);phase('seed')
    command('shell','am','force-stop','app.dkord')
    command('install','-r','-t',new)
    new_code,new_uid=package()
    if new_code!=expected_new or old_uid!=new_uid:raise ValueError('Real install-over failed to keep app UID/increase version')
    phase('verify')
    receipt=dict(format=1,package='app.dkord',baselineTag=baseline,fromVersionCode=old_code,toVersionCode=new_code,
                 source=os.environ['GITHUB_SHA'],sameUid=True,noUninstall=True,noDataReset=True,
                 realRoom=True,settings=True,queue=True,privateDownload=True,mediaStoreExport=True,studioProjectAndSourceBytes=True)
    with output.open('x') as file:json.dump(receipt,file,indent=2)
    print(f'::notice title=Actual Android install-over::Original signed code{old_code} -> code{new_code}, same UID, actual Room/likes/history/playlist/settings/queue/private and device audio/Studio source bytes preserved on isolated API35 emulator. Not a physical-device pass.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('old','new','test','output'):parser.add_argument('--'+arg,type=Path,required=True)
    parser.add_argument('--baseline',choices=tuple(BASELINES),default='v0.10.0')
    parser.add_argument('--target-code',type=int,default=15)
    args=parser.parse_args();verify(args.old,args.new,args.test,args.output,args.baseline,args.target_code)
