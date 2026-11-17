"""Frozen K0 extraction and passive, closed QA input boundaries."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from lineage.core.schema import strict_loads, validate
from lineage.core.journal import canonical_bytes

APPENDIX = b'<!-- U27-APPENDIX:BEGIN -->'
FROZEN_SHA256 = '06d87b1e36a6a39f7627ed461a4078e1c3162bf3b4ce3ae9b199cc91c0a3b197'
SAFE_INTEGER = 9007199254740991
STATES = ('busy','checked','current','disabled','expanded','hidden','pressed','selected')
ENTITIES = ('agent','run','bench','event','unit','skill')
SCREENS = ('agents','agent','lineage','arena','bench','ledger')
ROLES = ('article','group','document','heading','button','link','textbox','searchbox',
         'combobox','checkbox','radio','option','list','listitem','navigation','banner',
         'main','status','dialog','table','row','cell','columnheader','rowheader',
         'text','separator','generic','spinbutton','img')
RETAINED = frozenset(ROLES) - {'article','group','generic','document','text','img','separator'}
OPERATIONS = {
 'Create agent':('agent_create','agent.born'), 'Derive agent':(None,'agent.born'),
 'Write memory':('memory_put','memory.put'), 'Open run':('run_open','run.open'),
 'Record heartbeat':('run_beat','run.beat'), 'Close run':('run_close','run.close'),
 'Declare benchmark':('bench_declare','bench.declared'),
 'Launch benchmark':('bench_run',None), 'Evaluate benchmark':('bench_verdict','bench.verdict'),
 'Retire agent':('agent_retire','agent.status'), 'Promote agent':('agent_promote','agent.status'),
 'Export ledger':('ledger_export',None), 'Verify ledger':('ledger_verify',None)}


def canonical(value):
    return canonical_bytes(value)


def decode(raw):
    return strict_loads(raw)


def positive(value):
    if type(value) is not int or not 0 < value <= SAFE_INTEGER:
        raise ValueError('bad_config: positive integer required')
    return value


def schema(name):
    return decode((Path(__file__).parent / (name+'.schema.json')).read_bytes())


def validate_shape(value, shape):
    validate(value, {k:v for k,v in shape.items() if k != '$defs'})


def relative_ref(value):
    if (type(value) is not str or not 1 <= len(value) <= 512 or
            not re.fullmatch(r'[A-Za-z0-9_./-]+',value) or
            any(p in ('','.','..') for p in value.split('/'))):
        raise ValueError('bad_config: invalid artifact reference')
    return value


def normalize_name(value: str) -> str:
    if type(value) is not str:
        raise TypeError('bad_config: name must be text')
    value.encode('utf-8',errors='strict')
    return ' '.join(unicodedata.normalize('NFC',value).split())


def identity_key(kind: str, identity: str) -> str:
    if not normalize_name(kind) or not normalize_name(identity):
        raise ValueError('bad_config: empty identity')
    if len(identity.encode('utf-8')) <= 20:
        return identity
    prefix=identity[:7]
    if not prefix.isascii():
        raise ValueError('bad_config: identity prefix must be ASCII')
    return prefix+'-'+hashlib.sha256((kind+'\0'+identity).encode()).hexdigest()[:12]


def load_contract(path: Path) -> dict:
    prefix=Path(path).read_bytes().split(APPENDIX,1)[0]
    digest=hashlib.sha256(prefix).hexdigest()
    if digest != FROZEN_SHA256:
        raise ValueError('bad_config: unsupported frozen contract')
    text=prefix.decode('utf-8',errors='strict')
    actions={};fields={};reading_fields=False
    for line in text.splitlines():
        if line.startswith('| Form | Semantic names |'): reading_fields=True;continue
        if not line.startswith('|'):
            reading_fields=False
            continue
        cells=[x.strip() for x in line.strip('|').split('|')]
        if len(cells)==4 and re.fullmatch(r'`[a-z]+(?:-[a-z]+)+`',cells[0]):
            action=cells[0].strip('`')
            if action in actions: raise ValueError('bad_config: ambiguous action')
            actions[action]={'action':action,'element':cells[1].replace('`',''),'name':cells[2].strip('`')}
        if reading_fields and len(cells)==3 and '`' in cells[1]:
            names=re.findall(r'`([^`]+)`',cells[1])
            if names: fields[cells[0]] = names
    if not actions or not fields: raise ValueError('bad_config: incomplete registry')
    return dict(sha256=digest,actions=actions,fields=fields,screens=list(SCREENS),
                entities=list(ENTITIES),states=list(STATES))


def role_for(element):
    return {'a':'link','button':'button','select':'combobox','input search':'searchbox',
            'input checkbox':'checkbox','input':'textbox','input or select':'textbox'}.get(element,'textbox')


def validate_postcondition(value):
    validate_shape(value,schema('report')['$defs']['postcondition'])
    pair=OPERATIONS.get(value['operation'])
    if pair is None: raise ValueError('bad_config: unknown operation')
    tool,kind=pair
    if ((tool is not None and tool!=value['tool']) or
        (tool is None and value['tool'] not in ('agent_clone','agent_distill','agent_cross','agent_mutate','agent_specialize')) or
        (kind is not None and kind!=value['kind'])):
        raise ValueError('bad_config: operation mismatch')
    if value['expect']=='refusal':
        if value['code'] is None: raise ValueError('bad_config: refusal code required')
    elif value['code'] is not None: raise ValueError('bad_config: unexpected refusal code')
    if value['expect']=='projection' and value['tool'] not in ('ledger_export','ledger_verify'):
        raise ValueError('bad_config: not a projection')


def selector_attributes(selector):
    # Deliberately small CSS grammar: attribute equality and descendant scope.
    pattern=r'\[([a-z-]+)="((?:[^"\\]|\\(?:[0-9a-fA-F]{1,6} ?|.))*)"\]'
    matches=list(re.finditer(pattern,selector))
    residue=re.sub(pattern,'',selector)
    if not matches or residue.strip(): raise ValueError('invalid_selector')
    allowed={'data-lin-screen','data-lin-entity','data-lin-id','data-lin-action','data-lin-ready','data-lin-rev','name'}
    def unescape(value):
        return re.sub(r'\\([0-9a-fA-F]{1,6}) ?|\\(.)',lambda m:chr(int(m[1],16)) if m[1] else m[2],value)
    attrs={}
    for m in matches:
        if m[1] not in allowed or m[1] in attrs: raise ValueError('invalid_selector')
        attrs[m[1]]=unescape(m[2])
    return attrs


def validate_inventory(value: dict, *, contract: dict) -> None:
    validate_shape(value,schema('inventory'))
    if value['contract_sha256']!=contract['sha256']:
        raise ValueError('bad_config: contract hash mismatch')
    contexts=set()
    for ctx in value['contexts']:
        route=ctx['route'].split('?',1)[0]
        expected=('#/agents' if ctx['screen']=='agents' else '#/agents/' if ctx['screen']=='agent' else
                  '#/arena/' if ctx['screen']=='bench' else '#/'+ctx['screen'])
        if (route!=expected if ctx['screen'] not in ('agent','bench') else not route.startswith(expected) or route==expected):
            raise ValueError('bad_config: route screen mismatch')
        key=(ctx['route'],ctx['dialog'])
        if key in contexts: raise ValueError('bad_config: duplicate context')
        contexts.add(key);actions=set()
        if not ctx['actions']: raise ValueError('bad_config: empty context action set')
        for a in ctx['actions']:
            definition=contract['actions'].get(a['action'])
            if definition is None: raise ValueError('bad_config: unknown action')
            if (a['entity'] is None)!=(a['id'] is None): raise ValueError('bad_config: incomplete identity')
            key=(a['action'],a['entity'],a['id'],a['selector'])
            if key in actions: raise ValueError('bad_config: duplicate action')
            actions.add(key)
            roles={role_for(definition['element'])}
            if a['action']=='edit-field': roles={'textbox','combobox','checkbox','spinbutton'}
            if a['role'] not in roles: raise ValueError('bad_config: role mismatch')
            # Templates are syntactically validated here; full identity is checked
            # against computed names at the observer boundary, before actions.
            template=definition['name']
            pattern=''.join(re.escape(piece) if j%2==0 else r'.+' for j,piece in enumerate(re.split(r'\{([^{}]+)\}',template)))
            if not re.fullmatch(pattern,normalize_name(a['name'])): raise ValueError('bad_config: name mismatch')
            if a['availability']!='enabled' and not a['reason']: raise ValueError('bad_config: reason required')
            attrs=selector_attributes(a['selector'])
            if a['action']=='edit-field':
                fields={field for names in contract['fields'].values() for field in names}
                if attrs.get('name') not in fields:
                    raise ValueError('invalid_selector: undeclared semantic field')
            if attrs.get('data-lin-action')!=a['action']: raise ValueError('invalid_selector')
            if 'data-lin-screen' in attrs and attrs['data-lin-screen']!=ctx['screen']: raise ValueError('invalid_selector')
            if a['entity'] is not None and (attrs.get('data-lin-id')!=a['id'] or attrs.get('data-lin-entity')!=a['entity']):
                raise ValueError('invalid_selector')
            if a['entity'] is None and ('data-lin-id' in attrs or 'data-lin-entity' in attrs): raise ValueError('invalid_selector')
        if any(j not in contract['actions'] for j in ctx['journey']): raise ValueError('bad_config: unknown journey action')
        for post in ctx['postconditions']: validate_postcondition(post)


def validate_nodes(nodes, *, states=True):
    shape=schema('report')['$defs']['node']
    if not states:
        shape=dict(shape,properties=dict(shape['properties'],states={'type':'array','items':{'type':'string'},'uniqueItems':True}))
    validate_shape(nodes,{'type':'array','items':shape})
    by_id={n['id']:n for n in nodes}
    if len(by_id)!=len(nodes): raise ValueError('bad_config: duplicate node id')
    for n in nodes:
        if (n['entity'] is None)!=(n['entity_id'] is None): raise ValueError('bad_config: incomplete node identity')
        visited=set();current=n
        while current['parent'] is not None:
            if current['id'] in visited or current['parent'] not in by_id: raise ValueError('bad_config: invalid forest')
            visited.add(current['id']);current=by_id[current['parent']]


def validate_wire(value, filename):
    """Adapt the integrated mini-validator to the bundled wire keyword set.

    All composition, references and conditional constraints are evaluated; no
    keyword is silently discarded and network resolution is never attempted.
    """
    root=Path(__file__).resolve().parents[2]/'schemas'
    names={p.name for p in root.glob('*.schema.json')}
    if filename not in names: raise ValueError('bad_config: unknown wire schema')
    documents={}
    def document(name):
        if name not in documents: documents[name]=decode((root/name).read_bytes())
        return documents[name]
    advanced={'$ref','$defs','allOf','anyOf','oneOf','if','then','else','not',
              'patternProperties','propertyNames','maxProperties','minProperties',
              'exclusiveMinimum','exclusiveMaximum'}
    def apply(instance,definition,base,depth=0):
        if depth>64: raise ValueError('bad_config: schema recursion limit')
        if definition is True: return
        if definition is False: raise ValueError('semantic_mismatch: false schema')
        if type(definition) is not dict: raise ValueError('bad_config: malformed schema')
        if '$ref' in definition:
            ref=definition['$ref'];file,_,fragment=ref.partition('#')
            file=file or base
            if file not in names or (fragment and not fragment.startswith('/')): raise ValueError('bad_config: nonlocal schema reference')
            target=document(file)
            for part in fragment.split('/')[1:]: target=target[part.replace('~1','/').replace('~0','~')]
            apply(instance,target,file,depth+1)
        shallow={k:v for k,v in definition.items() if k not in advanced}
        props=definition.get('properties',{})
        if 'properties' in shallow: shallow['properties']={k:{} for k in props}
        if 'items' in shallow: shallow['items']={}
        patterns=definition.get('patternProperties',{})
        if type(instance) is dict and patterns:
            shallow['properties']=dict(shallow.get('properties',{}))
            for key in instance:
                if any(re.search(pattern,key) for pattern in patterns): shallow['properties'][key]={}
        additional=definition.get('additionalProperties')
        if type(additional) is dict: shallow['additionalProperties']=True
        validate_shape(instance,shallow)
        if type(instance) is dict:
            if len(instance)<definition.get('minProperties',0) or len(instance)>definition.get('maxProperties',SAFE_INTEGER): raise ValueError('semantic_mismatch: property count')
            for key,item in instance.items():
                if 'propertyNames' in definition: apply(key,definition['propertyNames'],base,depth+1)
                if key in props: apply(item,props[key],base,depth+1)
                matched=False
                for pattern,child in patterns.items():
                    if re.search(pattern,key): apply(item,child,base,depth+1);matched=True
                if key not in props and not matched and type(additional) is dict: apply(item,additional,base,depth+1)
        if type(instance) is list and 'items' in definition:
            for item in instance: apply(item,definition['items'],base,depth+1)
        if type(instance) in (int,float):
            if 'exclusiveMinimum' in definition and instance<=definition['exclusiveMinimum']: raise ValueError('semantic_mismatch: lower bound')
            if 'exclusiveMaximum' in definition and instance>=definition['exclusiveMaximum']: raise ValueError('semantic_mismatch: upper bound')
        def matches(child):
            try: apply(instance,child,base,depth+1);return True
            except ValueError: return False
        for child in definition.get('allOf',[]): apply(instance,child,base,depth+1)
        if 'anyOf' in definition and not any(matches(child) for child in definition['anyOf']): raise ValueError('semantic_mismatch: anyOf')
        if 'oneOf' in definition and sum(matches(child) for child in definition['oneOf'])!=1: raise ValueError('semantic_mismatch: oneOf')
        if 'not' in definition and matches(definition['not']): raise ValueError('semantic_mismatch: not')
        if 'if' in definition:
            branch='then' if matches(definition['if']) else 'else'
            if branch in definition: apply(instance,definition[branch],base,depth+1)
    apply(value,document(filename),filename)
