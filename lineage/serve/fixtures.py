"""Read-only fixture admission and server-local replacement of read providers."""
import copy
from dataclasses import replace
import hashlib
import math
from pathlib import Path
import re
import stat

from lineage.core.app import dispatch
from lineage.core.errors import LineageError
from lineage.core.schema import SchemaStore, canonical, decode, validate
from lineage.serve.static import _read_asset

_REQUIRED = {'clock.json', 'agents.json', 'runs.json', 'benches.json', 'events.jsonl',
             'memory.json', 'skills.json', 'references.json', 'constitutions.json',
             'scorecards.json', 'lineage.json', 'responses.json',
             'artifacts/lesson.txt', 'artifacts/negative.txt', 'artifacts/ruling.txt'}


def _require(condition):
    if not condition:
        raise LineageError('bad_args')


def _closed(value, keys):
    _require(isinstance(value, dict) and set(value) == set(keys.split()))


def _integer(value, minimum=0, maximum=9007199254740991):
    return type(value) is int and minimum <= value <= maximum


def _path(root, name):
    _require(isinstance(name, str) and len(name) <= 512 and
             re.fullmatch(r'[A-Za-z0-9_./-]+', name) is not None)
    parts = name.split('/')
    _require(all(p not in ('', '.', '..') for p in parts))
    path = root
    _require(stat.S_ISDIR(root.lstat().st_mode))
    for i, part in enumerate(parts):
        path = path / part
        mode = path.lstat().st_mode
        _require(stat.S_ISREG(mode) if i == len(parts) - 1 else stat.S_ISDIR(mode))
    return path


def _local_context(ctx, handlers):
    registry = copy.copy(ctx.services.registry)
    registry.tools = {name: replace(spec, handler=handlers(name, spec))
                      for name, spec in ctx.services.registry.tools.items()}
    return replace(ctx, services=replace(ctx.services, registry=registry))


class _Fixtures:
    def __init__(self, root, ctx):
        try:
            self._load(root, ctx)
        except LineageError:
            raise
        except (OSError, ValueError, TypeError, KeyError):
            raise LineageError('bad_args') from None

    def _load(self, root, ctx):
        manifest = decode(_read_asset('/manifest.json', root=root)[1])
        _closed(manifest, 'fixture_version files baseline clock head roots capture')
        _require(type(manifest['fixture_version']) is int and manifest['fixture_version'] == 1)
        _require(_integer(manifest['head']) and isinstance(manifest['roots'], list))
        _require(all(isinstance(v, str) for v in manifest['roots']))
        _require(len(manifest['roots']) == len(set(manifest['roots'])))
        _require(isinstance(manifest['files'], list))
        inventory = {}
        for item in manifest['files']:
            _closed(item, 'path sha256')
            name, digest = item['path'], item['sha256']
            _require(isinstance(name, str) and name != 'manifest.json' and name not in inventory)
            _require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest) is not None)
            _require(name in _REQUIRED or (name.startswith('scenarios/') and name.endswith('.json')))
            _path(root, name)
            data = _read_asset('/' + name, root=root)[1]
            if hashlib.sha256(data).hexdigest() != digest:
                raise LineageError('hash_mismatch')
            inventory[name] = data
        actual = set()
        for path in root.rglob('*'):
            mode = path.lstat().st_mode
            _require(stat.S_ISDIR(mode) or stat.S_ISREG(mode))
            if stat.S_ISREG(mode):
                actual.add(path.relative_to(root).as_posix())
        _require(actual == set(inventory) | {'manifest.json'})
        _require(_REQUIRED <= set(inventory))
        _require(manifest['clock'] == 'clock.json')
        _require(isinstance(manifest['baseline'], str) and manifest['baseline'].startswith('scenarios/') and
                 manifest['baseline'] in inventory)
        values = {name: decode(raw) for name, raw in inventory.items() if name.endswith('.json')}
        clock = values['clock.json']
        _closed(clock, 'epoch_ms tick_ms locale timezone theme reduced_motion')
        _require(_integer(clock['epoch_ms']) and _integer(clock['tick_ms'], 1))
        _require(clock['locale'] == 'en-GB' and clock['timezone'] == 'UTC')
        _require(clock['theme'] in ('light', 'dark') and type(clock['reduced_motion']) is bool)
        capture = manifest['capture']
        _closed(capture, 'device_scale_factor viewport theme reduced_motion')
        _closed(capture['viewport'], 'width height')
        scale = capture['device_scale_factor']
        _require(type(scale) in (int, float) and math.isfinite(scale) and scale > 0)
        _require(all(_integer(v, 1) for v in capture['viewport'].values()))
        _require(capture['theme'] in ('light', 'dark') and type(capture['reduced_motion']) is bool)
        for name, value in values.items():
            if name.startswith('scenarios/'):
                _closed(value, 'name dataset frames expect')
                _require(isinstance(value['name'], str) and isinstance(value['dataset'], str) and
                         isinstance(value['frames'], list) and isinstance(value['expect'], dict))
        store = SchemaStore(Path(__file__).resolve().parents[2] / 'schemas')
        def record(value, schema):
            validate(value, store.load(schema), store=store, base=schema)
        for name in ('agents', 'runs', 'benches', 'skills', 'references', 'constitutions', 'scorecards', 'lineage'):
            _require(isinstance(values[name + '.json'], list))
        for name, schema in (('agents', 'agent.schema.json'), ('benches', 'bench_declared.schema.json')):
            for item in values[name + '.json']:
                record(item, schema)
        for item in values['runs.json']:
            if isinstance(item, dict) and item.get('schema') == 'lineage.run/v1':
                record(item, 'run.schema.json')
            else:
                _closed(item, 'opened closed head')
                record(item['opened'], 'event.schema.json')
                _require(item['opened']['kind'] == 'run.open' and item['closed'] is None and
                         _integer(item['head']) and item['opened']['lamport'] <= item['head'] <= manifest['head'])
        _require(isinstance(values['memory.json'], dict))
        for units in values['memory.json'].values():
            _require(isinstance(units, list))
            for unit in units:
                record(unit, 'mem_unit.schema.json')
        self.events = []
        for line in inventory['events.jsonl'].splitlines():
            event = decode(line)
            record(event, 'event.schema.json')
            _require(event['lamport'] == len(self.events) + 1)
            self.events.append(event)
        self.head = manifest['head']
        _require(self.head == len(self.events))
        agent_ids = {v.get('agent_id', v.get('id')) for v in values['agents.json']}
        _require(set(manifest['roots']) <= agent_ids)
        responses = values['responses.json']
        _require(isinstance(responses, list))
        probe = _local_context(ctx, lambda name, spec: lambda args, context: args)
        self.responses = {}
        for response in responses:
            _closed(response, 'tool args data')
            name, args = response['tool'], response['args']
            _require(isinstance(name, str) and name in ctx.services.registry.tools)
            _require(ctx.services.registry.tools[name].effect == 'read' and name != 'ledger_export')
            _require(isinstance(args, dict))
            result = dispatch(name, args, ctx=probe)
            _require(isinstance(result, dict) and set(result) == {'untrusted'})
            effective = result['untrusted']
            _require(canonical(effective) == canonical(args))
            key = name, canonical(effective)
            _require(key not in self.responses)
            self.responses[key] = response['data']
        def handlers(name, spec):
            if spec.effect != 'read' or name == 'ledger_export':
                def readonly(args, context):
                    raise LineageError('fixture_readonly')
                return readonly
            if name == 'ledger_events':
                return self._cursor
            def read(args, context):
                key = name, canonical(args)
                if key not in self.responses:
                    raise LineageError('bad_args')
                return copy.deepcopy(self.responses[key])
            return read
        self.ctx = _local_context(ctx, handlers)

    def _cursor(self, args, ctx):
        after = args['after']
        if after > self.head:
            return dict(events=[], next_after=0, head=self.head, has_more=False, resync=True)
        selected = []
        scanned = after
        for event in self.events[after:]:
            scanned = event['lamport']
            if args.get('agent_id', event['agent']) == event['agent'] and event['kind'] in args.get('kinds', [event['kind']]):
                selected.append(copy.deepcopy(event))
            if len(selected) >= args['limit']:
                break
        return dict(events=selected, next_after=scanned, head=self.head,
                    has_more=scanned < self.head, resync=False)
