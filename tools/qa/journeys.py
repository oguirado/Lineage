"""Semantic tool-result, immutable-event and corresponding-read witnesses."""
from __future__ import annotations
import hashlib
from pathlib import Path
from .contracts import canonical, decode, validate_postcondition, validate_shape, validate_wire
from .report import check


def _wire(value, name):
    definition=decode((Path(__file__).resolve().parents[2]/'schemas'/(name+'.schema.json')).read_bytes())
    if name=="event":
        # Semantic helper consumes the immutable envelope and separately checks
        # the operation record. Full event payload admission belongs to the
        # public wire integration gate (validate_wire), not this slice.
        validate_shape(value,{k:v for k,v in definition.items() if k!="allOf"})
    else:
        validate_wire(value,name+".schema.json")


def _unwrap(value):
    return value['untrusted'] if type(value) is dict and set(value)=={'untrusted'} and type(value['untrusted']) is dict else None


def _objects(value):
    if type(value) is dict:
        yield value
        for v in value.values(): yield from _objects(v)
    elif type(value) in (list,tuple):
        for v in value: yield from _objects(v)


def check_postcondition(*, expected, result, events, observed):
    validate_postcondition(expected)
    if events is None: return check('evidence_missing','Event history unavailable.',requirement='O11')
    if type(events) not in (list,tuple): raise ValueError('bad_config')
    data=_unwrap(result);read=_unwrap(observed)
    if expected['expect']=='refusal':
        if data is not None or result.get('ok') is not False or result.get('code')!=expected['code']:
            return check('semantic_mismatch','Expected exact semantic refusal.',requirement='O11')
        if any(e.get('agent')==expected['actor'] and (expected['op_id'] is None or e.get('op_id')==expected['op_id']) and e.get('kind')==expected['kind'] for e in events):
            return check('semantic_mismatch','Mutation event contradicts refusal.',requirement='O11')
        # A caller must supply independently captured before/after folds and
        # inspected operation-prefix bounds. An arbitrary current read is not
        # evidence that the relevant state stayed unchanged.
        if read is None or not {'before','after','history_complete'}<=read.keys() or read['history_complete'] is not True:
            return check('evidence_missing','Refusal needs before/after state and inspected history.',requirement='O11')
        if read['before']!=read['after']: return check('semantic_mismatch','Refusal changed state.',requirement='O11')
        return check(requirement='O11')
    if data is None: return check('semantic_mismatch','Dispatch did not return successful data.',requirement='O11')
    if expected['expect']=='projection':
        if read is None or type(read.get('head')) is not int: return check('evidence_missing','Verified projection head unavailable.',requirement='O11')
        if expected['tool']=='ledger_verify':
            if data.get('valid') is not True or data.get('head')!=read['head']: return check('semantic_mismatch','Verification/head mismatch.',requirement='O11')
            return check(requirement='O11')
        # Manifest verification is supplied by the separately confined artifact
        # verifier; a write acknowledgement never sets this field on its own.
        if not data.get('manifest') or read.get('manifest_verified') is not True or data.get('head')!=read['head']:
            return check('evidence_missing','Verified export manifest unavailable.',requirement='O11')
        return check(requirement='O11')
    if expected['op_id'] is None:
        return check('evidence_missing','Captured request operation identity required.',requirement='O11')
    matching=[e for e in events if e.get('agent')==expected['actor'] and e.get('op_id')==expected['op_id'] and e.get('kind')==expected['kind']]
    if not matching: return check('missing_witness','No matching authoritative event.',requirement='O11')
    try:
        previous=None;ids=set()
        for e in events:
            _wire(e,'event')
            if e['id'] in ids: raise ValueError('duplicate event')
            ids.add(e['id'])
            if hashlib.sha256(canonical({k:v for k,v in e.items() if k!='sha256'})).hexdigest()!=e['sha256']: raise ValueError('event digest')
            if previous is not None:
                if e['lamport']!=previous['lamport']+1 or e['prev_sha256']!=hashlib.sha256(canonical(previous)+b'\n').hexdigest(): raise ValueError('event chain')
            previous=e
        commit=data.get('commit')
        if type(commit) is not dict or set(commit)!={'event_ids','head','sha256'}: raise ValueError('commit absent')
        selected=[e for e in events if e['id'] in commit['event_ids']]
        if not selected or len(selected)!=len(commit['event_ids']) or any(e not in selected for e in matching): raise ValueError('commit events')
        last=selected[-1]
        if type(commit['head']) is not int or commit['head']!=last['lamport'] or commit['sha256']!=last['sha256']: raise ValueError('commit prefix')
        if read is None or type(read.get('head')) is not int or read['head']<commit['head']: return check('evidence_missing','Acknowledged read head unavailable.',requirement='O11')
        if expected['tool']=='run_close':
            run=data.get('run');_wire(run,'run')
            if run.get('run_id')!=expected['run_id'] or run.get('agent_id')!=expected['actor'] or run.get('memory',{}).get('gate_passed') is not True: raise ValueError('run identity or gate')
            if run!=matching[-1]['payload'].get('record') or read.get('closed')!=run: raise ValueError('run fold')
        else:
            # Validate the actual record schema and require full equality with
            # its corresponding read. Unsupported compound operations do not
            # gain an invented root event or automatic success.
            mapping={'agent.born':'agent','memory.put':'mem_unit','run.open':'run','bench.declared':'bench_declared'}
            name=mapping.get(expected['kind'])
            if name is None: return check('evidence_missing','Operation-specific read comparison unavailable.',requirement='O11')
            record=matching[-1]['payload'].get('record',matching[-1]['payload'].get('unit'))
            _wire(record,name)
            if expected['entity_id'] and record.get('agent_id',record.get('id'))!=expected['entity_id']: raise ValueError('entity identity')
            if not any(v==record for v in _objects(read)): raise ValueError('corresponding read')
    except (ValueError,TypeError,KeyError,OSError):
        return check('semantic_mismatch','Event, commit, identity or read mismatch.',requirement='O11')
    return check(requirement='O11')
