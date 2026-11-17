"""Independent opaque-article compatibility transform; no external code."""
from __future__ import annotations
import argparse
import copy
from pathlib import Path
import sys
from .contracts import (RETAINED, STATES, decode, load_contract, normalize_name,
                        schema, validate_shape, validate_inventory, validate_nodes)
from .report import check, context_for, emit, make_report


def transform(nodes):
    validate_nodes(nodes)
    by_id={n['id']:n for n in nodes};retained={}
    for n in nodes:
        current=n
        while current is not None and current['role']!='article':
            current=by_id.get(current['parent'])
        if current is not None: continue
        if n['role'] in RETAINED or n['actionable']:
            retained[n['id']]=dict(copy.deepcopy(n),name=normalize_name(n['name']))
    for n in retained.values():
        parent=n['parent']
        while parent is not None and parent not in retained: parent=by_id[parent]['parent']
        n['parent']=parent
    return list(retained.values())


def semantic(n):
    return n['role'],normalize_name(n['name']),n['entity'],n['entity_id'],n['action']


def compare(raw, pruned, *, required, complete):
    for nodes in (raw,pruned): validate_nodes(nodes,states=False)
    # Requirement snapshots reference the raw forest; their parents need not
    # themselves be required. They are not a separately traversable forest.
    definition=schema('report')['$defs']['node']
    definition=dict(definition,properties=dict(definition['properties'],states={'type':'array','items':{'type':'string'},'uniqueItems':True}))
    validate_shape(list(required),{'type':'array','items':definition})
    if type(complete) is not bool: raise ValueError('bad_config: completeness must be Boolean')
    checks=[]
    for values in (raw,pruned):
        names=set()
        for n in values:
            name=normalize_name(n['name'])
            if any(s not in STATES for s in n['states']): checks.append(check('invalid_state',requirement='O6'))
            if n['actionable'] or n['role']=='heading':
                if len(name.encode())>64: checks.append(check('name_too_long',requirement='O3'))
                if n['actionable']:
                    # Native select options have independent parent scopes.
                    key=(n['parent'] if n['role']=='option' else None,name)
                    if key in names: checks.append(check('duplicate_name',requirement='O3'))
                    names.add(key)
    raw_set={semantic(n) for n in raw};pruned_set={semantic(n) for n in pruned}
    natural=transform(raw) if all(set(n['states'])<=set(STATES) for n in raw) else []
    natural_set={semantic(n) for n in natural}
    for n in required:
        key=semantic(n)
        if key not in raw_set:
            checks.append(check('missing_control' if complete else 'incomplete_tree',requirement='O4'))
        elif key not in pruned_set:
            checks.append(check('article_control' if key not in natural_set else 'missing_control',requirement='O1'))
    if not complete: checks.append(check('incomplete_tree',requirement='O13'))
    if not required: checks.append(check('evidence_missing','No required identity set.',requirement='O4'))
    if not checks: checks=[check(requirement='O1')]
    return make_report(method='P',scope='selftest',checks=checks,artifacts=[],context=context_for())


def main(argv=None):
    from .cdp_probe import _ArgumentParser
    parser=_ArgumentParser(description=__doc__)
    parser.add_argument('--observation',required=True,type=Path)
    parser.add_argument('--inventory',required=True,type=Path)
    parser.add_argument('--contract',required=True,type=Path)
    try:
        args=parser.parse_args(argv)
        contract=load_contract(args.contract);inventory=decode(args.inventory.read_bytes())
        validate_inventory(inventory,contract=contract)
        obs=decode(args.observation.read_bytes())
        validate_shape(obs,schema('report')['$defs']['observation'])
        required=[]
        for ctx in inventory['contexts']:
            for a in ctx['actions']:
                if a['availability']=='absent': continue
                required.append(dict(id=str(len(required)),parent=None,role=a['role'],name=a['name'],
                                     states=[],actionable=True,entity=a['entity'],entity_id=a['id'],action=a['action']))
        result=compare(obs['nodes'],transform(obs['nodes']),required=required,
                       complete=obs['complete'] and not obs['truncated'] and obs['document_found'])
        # Pruning witnesses are supplied by the caller, never relabelled live.
        result['scope']=inventory['scope'];result['context']=context_for(inventory,contract)
        if not obs['owner_ref']:
            result=make_report(method='P',scope=inventory['scope'],checks=result['checks']+[check('evidence_missing','Missing ownership association.')],artifacts=[],context=result['context'])
    except (ValueError,TypeError,OSError,RuntimeError):
        result=make_report(method='P',scope='selftest',checks=[check('bad_config','Invalid prune inputs.')],artifacts=[],context=context_for())
    return emit(result,write=lambda b:sys.stdout.write(b.decode('utf-8')))

if __name__=='__main__': raise SystemExit(main())
