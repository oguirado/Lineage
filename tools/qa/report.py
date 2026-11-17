"""Truthful verdict reduction and public-safe canonical emission."""
from __future__ import annotations
import copy
import html
import re
from .contracts import canonical, relative_ref, schema, validate_shape

FAIL_CODES=frozenset('article_control duplicate_name name_too_long identity_key_mismatch identity_collision non_native_control invalid_selector inventory_mismatch missing_control invalid_state focus_mismatch announcement_mismatch stale_ready unexpected_console layout_mismatch contrast_mismatch missing_witness semantic_mismatch evidence_mismatch unsafe_content'.split())
INCOMPLETE_CODES=frozenset('bad_config observer_unavailable wrong_target no_document empty_tree incomplete_tree deadline dependency_missing evidence_missing cleanup_incomplete probe_internal'.split())
CONTEXT_KEYS=('contract_sha256','inventory_sha256','fixture_sha256','scenario','frame','head','viewport','theme','reduced_motion','zoom_percent','owner_ref')


def check(code='ok', detail='', *, requirement='O13', expected=None, observed=None):
    status='PASS' if code=='ok' else 'FAIL' if code in FAIL_CODES else 'INCONCLUSIVE'
    return dict(id=requirement,requirement=requirement,status=status,code=code,
                detail=detail,expected=expected,observed=observed)


def context_for(inventory=None, contract=None):
    value=dict.fromkeys(CONTEXT_KEYS)
    if contract: value['contract_sha256']=contract['sha256']
    if inventory:
        import hashlib
        value.update(inventory_sha256=hashlib.sha256(canonical(inventory)).hexdigest(),
                     scenario=inventory['scenario'],frame=inventory['frame'])
    return value


def reduction(checks):
    if any(c['status']=='FAIL' for c in checks): return 'FAIL',1
    if not checks or any(c['status']=='INCONCLUSIVE' for c in checks): return 'INCONCLUSIVE',2
    return 'PASS',0


def make_report(*, method, scope, checks, artifacts, context):
    status,rc=reduction(checks)
    result=dict(schema='lineage.qa.report/v1',method=method,scope=scope,status=status,rc=rc,
                checks=copy.deepcopy(list(checks)),artifacts=copy.deepcopy(list(artifacts)),context=copy.deepcopy(context))
    exit_code(result)
    return result


def exit_code(report):
    validate_shape(report,schema('report'))
    if type(report['rc']) is not int: raise ValueError('bad_config: invalid exit code')
    for c in report['checks']:
        required='PASS' if c['code']=='ok' else 'FAIL' if c['code'] in FAIL_CODES else 'INCONCLUSIVE' if c['code'] in INCOMPLETE_CODES else None
        if required!=c['status']: raise ValueError('bad_config: status code mismatch')
    if (report['status'],report['rc'])!=reduction(report['checks']): raise ValueError('bad_config: false verdict')
    for a in report['artifacts']: relative_ref(a['ref'])
    return report['rc']


def public_text(value):
    value=re.sub(r'(?<![A-Za-z0-9_.-])(?:[A-Za-z]:[\\/]|/)[^\s<>"\']+', '[redacted-path]', value)
    value=re.sub(r'\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}\b','[redacted-host]',value)
    value=re.sub(r'\b(?:sk-|Bearer\s+|token[=:]\s*)[^\s<>"\']+', '[redacted-secret]',value,flags=re.I)
    return html.escape(value,quote=True)


def emit(report, *, write):
    rc=exit_code(report)
    result=copy.deepcopy(report)
    for c in result['checks']:
        for k in ('detail','expected','observed'):
            if c[k] is not None: c[k]=public_text(c[k])
    for k in ('scenario','frame','owner_ref'):
        if result['context'][k] is not None: result['context'][k]=public_text(result['context'][k])
    write(canonical(result)+b'\n')
    return rc
