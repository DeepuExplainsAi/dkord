"""Export ONLY the existing APK identity's public update-verification root.

Runs on an explicitly requested trusted-branch preparation push. No private key
is loaded into Python, printed, uploaded or changed. Public certificate must match
the actual immutable v0.10.0 APK after apksigner verification and pinned APK hash.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec

from verify_apk_update import certificates

APK_SHA256 = 'd2a354903e3eda3707aab77721a391ee0eee3134010284e7ffd1a3e28f2deed9'


def export(keystore: Path, apk: Path, apksigner: Path, output: Path):
    if hashlib.sha256(apk.read_bytes()).hexdigest() != APK_SHA256:
        raise ValueError('Published APK differs from the previously verified immutable release')
    certificate = output.parent / 'dkord-public-certificate.der'
    subprocess.run(['keytool', '-exportcert', '-storetype', 'pkcs12', '-keystore', str(keystore),
                    '-alias', 'dkord', '-storepass:env', 'DKORD_KEYSTORE_PASS', '-file', str(certificate)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    data = certificate.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if set(certificates(apksigner, apk)) != {digest}:
        raise ValueError('Public root does not match the existing published APK signing identity')
    public = x509.load_der_x509509_certificate(data).public_key()
    if isinstance(public, rsa.RSAPublicKey) and public.key_size >= 2048:
        algorithm = 'rsa-pkcs1-sha256'
    elif isinstance(public, ec.EllipticCurvePublicKey) and isinstance(public.curve, ec.SECP256R1):
        algorithm = 'ecdsa-p256-sha256'
    else:
        raise ValueError('Existing signing identity uses an unsupported update verification algorithm')
    key = dict(algorithm=algorithm, publicKey=base64.b64encode(public.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode('ascii'),
        certificateSha256=digest)
    result = {'format': 1, 'keys': {'dkord-apk-'+digest[:16]: key}, 'verifiedAgainst': {
        'tag': 'v0.10.0', 'asset': 'Dkord-v0.10.0.apk', 'apkSha256': APK_SHA256,
        'certificateSha256': digest}, 'privateKeyExported': False}
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    # Small PUBLIC payload can be retrieved through the read-only Check API;
    # never emit the PKCS12, password, private key, or runner environment.
    print('::notice title=Dkord existing public update identity::'+json.dumps(result,separators=(',',':')))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keystore', type=Path, required=True)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--apksigner', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    export(args.keystore, args.apk, args.apksigner, args.output)
