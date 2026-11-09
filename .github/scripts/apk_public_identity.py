"""Bounded APK v2/v3 signing-block CERTIFICATE reader, NOT a signature verifier.

Call only after apksigner verification and compare leaf DER hashes with its
verified signer report. No key material or ZIP contents are executed/extracted.
"""
from __future__ import annotations
import struct

MAGIC=b'APK Sig Block 42'
SCHEMES={0x7109871a,0xf05368c0,0x1b93ad61}
MAX_BLOCK=16*1024*1024


def _lp(data,offset=0):
    if offset<0 or offset+4>len(data):raise ValueError('Truncated signing identity')
    size=struct.unpack_from('<I',data,offset)[0];end=offset+4+size
    if end>len(data):raise ValueError('Truncated signing identity')
    return data[offset+4:end],end


def leaf_certificates(value):
    signers,end=_lp(value)
    if end!=len(value):raise ValueError('Unexpected signing identity suffix')
    offset=0;result=[]
    while offset<len(signers):
        signer,offset=_lp(signers,offset)
        signed,_=_lp(signer)
        _,position=_lp(signed)  # digests (not trusted here)
        certificates,_=_lp(signed,position)
        certificate,_=_lp(certificates)
        if not certificate:raise ValueError('Empty signing certificate')
        result.append(certificate)
        if len(result)>16:raise ValueError('Too many APK signing identities')
    return result


def apk_certificates(data):
    if not isinstance(data,bytes) or len(data)>256*1024*1024:raise ValueError('Invalid bounded APK')
    eocd=data.rfind(b'PK\x05\x06',max(0,len(data)-65557))
    while eocd>=0:
        if eocd+22<=len(data) and eocd+22+struct.unpack_from('<H',data,eocd+20)[0]==len(data):break
        eocd=data.rfind(b'PK\x05\x06',max(0,len(data)-65557),eocd)
    if eocd<0:raise ValueError('APK central directory missing')
    disk,central_disk=struct.unpack_from('<HH',data,eocd+4)
    central_size,central=struct.unpack_from('<II',data,eocd+12)
    if disk or central_disk or central==0xffffffff or central+central_size!=eocd or central<32 or central>eocd:
        raise ValueError('Unsupported APK directory layout')
    size=struct.unpack_from('<Q',data,central-24)[0]
    start=central-size-8
    if data[central-16:central]!=MAGIC or not 24<=size<=MAX_BLOCK or start<0 or struct.unpack_from('<Q',data,start)[0]!=size:
        raise ValueError('APK v2/v3 signature block missing')
    position=start+8;end=central-24;result=[]
    while position<end:
        if position+8>end:raise ValueError('Truncated signing block pair')
        length=struct.unpack_from('<Q',data,position)[0];position+=8
        if length<4 or length>end-position:raise ValueError('Invalid signing block pair')
        scheme=struct.unpack_from('<I',data,position)[0]
        if scheme in SCHEMES:result.extend(leaf_certificates(data[position+4:position+length]))
        position+=length
    if position!=end or not result:raise ValueError('No supported signing certificate')
    return list(dict.fromkeys(result))
