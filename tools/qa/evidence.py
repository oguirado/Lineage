"""External evidence admission; unsupported receipts never gain credit."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import stat
from .contracts import canonical, decode, relative_ref
from .report import check, context_for, make_report


def _artifact_root(root):
    path=Path(root).absolute()
    descriptor=os.open(os.sep,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            if part in ('.','..'): raise ValueError('bad_config')
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=descriptor)
            os.close(descriptor);descriptor=child
        result=descriptor;descriptor=None
        return result
    finally:
        if descriptor is not None: os.close(descriptor)


def _artifact_bytes(root, ref):
    relative_ref(ref)
    # Walk with dirfds and O_NOFOLLOW, including the root; no symlink race.
    descriptor=_artifact_root(root)
    try:
        segments=ref.split('/')
        for segment in segments[:-1]:
            child=os.open(segment,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=descriptor)
            os.close(descriptor);descriptor=child
        fd=os.open(segments[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=descriptor)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError('evidence_mismatch')
            with os.fdopen(fd,'rb',closefd=False) as stream: return stream.read()
        finally: os.close(fd)
    finally: os.close(descriptor)


def verify_artifact(artifact, *, artifact_root):
    from .contracts import schema, validate_shape
    validate_shape(artifact,schema('report')['$defs']['artifact'])
    raw=_artifact_bytes(artifact_root,artifact['ref'])
    if artifact['hash_basis']=='canonical_json': raw=canonical(decode(raw))
    elif artifact['hash_basis']=='canonical_pixels':
        raise ValueError('evidence_missing: pixel decoder and capture pins required')
    return hashlib.sha256(raw).hexdigest()==artifact['sha256']


def verify_capsule(records, *, artifact_root: Path, expected):
    if type(records) not in (list,tuple) or type(expected) is not dict: raise ValueError('bad_config')
    checks=[]
    if not records: checks.append(check('evidence_missing','Capsule records unavailable.'))
    else:
        # No unpinned vis.receipt/v1 or persona rubric is accepted. Shapes that
        # resemble receipts are not authority and cannot supply their own schema.
        for record in records:
            if type(record) is not dict: raise ValueError('bad_config')
            checks.append(check('bad_config','Pinned external receipt schema and observer trust root unavailable.'))
    return make_report(method='V',scope='selftest',checks=checks,artifacts=[],context=context_for())
