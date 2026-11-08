"""Export ONLY the public identity from the actual immutable published APK.

No signing secret, keystore or private key is read. apksigner first verifies the
APK; a bounded reader's public leaf certificate hashes must equal its signer
report and the APK bytes must match the previously verified published SHA-256.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec

from verify_apk_update import certificates
from apk_public_identity import apk_certificates

APK_SHA256 = 'd2a354903e3eda3707aab77721a391ee0eee3134010284e7ffd1a3e28f2deed9'


def export(apk: Path, apksigner: Path, output: Path):
    apk_bytes = apk.read_bytes()
    if hashlib.sha256(apk_bytes).hexdigest() != APK_SHA256:
        raise ValueError('Published APK differs from the previously verified immutable release')
    verified = set(certificates(apksigner, apk))
    candidates = apk_certificates(apk_bytes)
    found = {hashlib.sha256(data).hexdigest(): data for data in candidates}
    if len(verified) != 1 or set(found) != verified:
        raise ValueError('Public root does not match the verified existing APK signing identity')
    digest = next(iter(verified)); data = found[digest]
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
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--apksigner', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        export(args.apk, args.apksigner, args.output)
    except Exception as error:
        print('::error title=Public update identity::Public APK identity verification failed ('+type(error).__name__+'). No signing material was read or changed.')
        raise SystemExit(1)
