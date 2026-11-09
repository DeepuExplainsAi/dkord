"""Owner-authorized release-only desktop manifest attestation.

Uses the EXISTING protected APK signing identity inside the publication runner.
Never creates a key, changes the APK identity, exports a private key, emits secrets,
accepts an unpinned key, or signs arbitrary files/URLs. Native artifacts must first
pass the separate exact-source six-host provenance/test gate.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,ec,padding
from cryptography.hazmat.primitives.serialization import pkcs12
from dkord_desktop.updates import canonical,UPDATE_DOMAIN,Updater,verify_manifest,version as parse_version

KINDS={'windows-x64':(('exe','exe'),),'windows-x86':(('exe','exe'),),
       'macos-x64':(('pkg','pkg'),),'macos-arm64':(('pkg','pkg'),),
       'linux-x64':(('deb','deb'),('appimage','AppImage')),'linux-arm64':(('deb','deb'),('appimage','AppImage'))}


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def payload(folder,version,tag,source):
    parse_version(version)
    if tag!='v'+version or not re.fullmatch('[a-f0-9]{40}',source) or int(source,16)==0:
        raise ValueError('Exact common release version/tag/source required')
    assets={}
    for target,kinds in KINDS.items():
        artifacts={}
        for kind,extension in kinds:
            name=f'Dkord-desktop-v{version}-{target}.{extension}';path=folder/name
            if path.is_symlink() or not path.is_file() or not 1024<=path.stat().st_size<=1024**3:
                raise ValueError('Missing/bounded exact-platform native installer')
            artifacts[kind]=dict(name=name,kind=kind,size=path.stat().st_size,sha256=sha256(path),
                                url=f'https://github.com/DeepuExplainsAi/dkord/releases/download/{tag}/{name}')
        assets[target]=artifacts if target.startswith('linux-') else next(iter(artifacts.values()))
    return dict(format=2,channel='desktop',version=version,tag=tag,source=source,assets=assets)


def sign(folder,version,tag,source,keystore,password,keys=None):
    body=payload(folder,version,tag,source)
    keys=Updater.production_keys() if keys is None else keys
    private,certificate,_=pkcs12.load_key_and_certificates(keystore.read_bytes(),password.encode('utf-8'))
    if private is None or certificate is None:
        raise ValueError('Existing signing identity required; no replacement or fallback key')
    digest=certificate.fingerprint(hashes.SHA256()).hex()
    public=base64.b64encode(certificate.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).decode('ascii')
    matches=[(key_id,root) for key_id,root in keys.items() if isinstance(root,dict) and root.get('certificateSha256')==digest and root.get('publicKey')==public]
    if len(matches)!=1 or private.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)!=certificate.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo):
        raise ValueError('Keystore identity differs from the original pinned published APK')
    key_id,root=matches[0];message=UPDATE_DOMAIN+canonical(body)
    if root['algorithm']=='rsa-pkcs1-sha256' and isinstance(private,rsa.RSAPrivateKey) and private.key_size>=2048:
        signature=private.sign(message,padding.PKCS1v15(),hashes.SHA256())
    elif root['algorithm']=='ecdsa-p256-sha256' and isinstance(private,ec.EllipticCurvePrivateKey) and isinstance(private.curve,ec.SECP256R1):
        signature=private.sign(message,ec.ECDSA(hashes.SHA256()))
    else:
        raise ValueError('Wrong existing signing algorithm')
    envelope=dict(payload=body,keyId=key_id,signature=base64.b64encode(signature).decode('ascii'))
    raw=json.dumps(envelope,ensure_ascii=False,indent=2).encode('utf-8')+b'\n'
    # Exercise the actual installed verifier for EVERY platform and Linux kind.
    for target in KINDS:
        for image in ((False,True) if target.startswith('linux-') else (False,)):
            update=verify_manifest(raw,keys,installed='0.0.0',target=target,image=image)
            if update is None or sha256(folder/update.name)!=update.sha256:
                raise ValueError('Generated update manifest failed installed-client verification')
    output=folder/f'Dkord-desktop-v{version}-manifest.json'
    with output.open('xb') as file:file.write(raw)  # never replace a previously signed manifest
    return output


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,required=True);parser.add_argument('--version',required=True)
    parser.add_argument('--tag',required=True);parser.add_argument('--source',required=True)
    args=parser.parse_args()
    try:
        result=sign(args.folder,args.version,args.tag,args.source,Path(os.environ['DKORD_KEYSTORE']),os.environ['DKORD_KEYSTORE_PASS'])
        print('::notice title=Signed desktop update manifest::'+result.name+' verified for all six targets/eight packages using the original pinned APK identity. No key rotation.')
    except Exception as error:
        # No command arguments, password, keystore bytes or private-key repr in logs.
        print('::error title=Desktop update attestation::Signing refused ('+type(error).__name__+'); existing pinned identity and verified packages are required.')
        raise SystemExit(1)
