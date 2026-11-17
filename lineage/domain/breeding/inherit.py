"""The single receipt-backed, context-only inheritance policy.

Selection retains source identities. Adoption is a separate pure step because
only the caller knows the child identity. Neither step changes a source object.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import re
from types import SimpleNamespace

from lineage.core.errors import LineageError
from lineage.core.journal import canonical_bytes
from lineage.domain.memory import schema as memory_schema

_AGENT = re.compile(r'[a-z][a-z0-9-]{2,63}')
_ID = re.compile(r'[A-Za-z0-9_-]{8,64}')
_PATH = re.compile(r'[A-Za-z0-9._/-]{1,512}')
_KINDS = frozenset(('lesson', 'negative', 'workflow'))


@dataclass(frozen=True)
class InheritanceSelection:
    inherited: tuple[dict, ...]
    rejected: tuple[dict, ...]


def _identity(value, pattern):
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise LineageError('bad_args', 'invalid source identity')


def _sequence(value):
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


@lru_cache(maxsize=1)
def _audit_schema():
    definition = memory_schema._STORE.load('mem_unit.schema.json')
    # Two explicit audit exceptions: an empty receipt array and an unsafe path.
    # Relax only these assertions in the source inspection schema. No accepted
    # copy is validated with this schema; it must pass the complete schema.
    for branch in definition['allOf']:
        if branch.get('if', {}).get('properties', {}).get('level') == {'const': 2}:
            branch['then']['properties']['receipts']['minItems'] = 0
    definition['properties']['receipts']['items']['properties']['path'].pop('pattern')
    return definition


def _source_shape(unit):
    try:
        memory_schema._validate(unit, _audit_schema(), store=memory_schema._STORE,
                                base='mem_unit.schema.json')
        if len(canonical_bytes(unit)) > 6000:
            raise LineageError('bad_args', 'source unit exceeds byte capacity')
        if unit['kind'] == 'workflow':
            stats = unit['body']['stats']
            if stats['successes'] > stats['runs']:
                raise LineageError('bad_args', 'invalid source workflow statistics')
    except memory_schema.boundary.SchemaError:
        raise LineageError('bad_args', 'invalid source memory shape') from None


def _evidence_context(ctx):
    try:
        home = ctx.services.home if hasattr(ctx, 'services') else ctx.home
        home = Path(home).resolve(strict=True)
        if not home.is_dir():
            raise OSError
    except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
        raise LineageError('internal', 'runtime evidence service unavailable') from None
    return SimpleNamespace(services=SimpleNamespace(home=home))


def _receipts_valid(receipts, ctx):
    runtime = _evidence_context(ctx)
    for receipt in receipts:
        path = receipt['path']
        if (_PATH.fullmatch(path) is None or path.startswith('/')
                or any(part in ('', '.', '..') for part in path.split('/'))
                or path.split('/')[0] in ('ledger', 'family')):
            return False
        try:
            # U10's descriptor walk hashes current bytes and refuses symlinks,
            # directories and evidence that changes while being read.
            memory_schema._evidence(receipt, runtime)
        except LineageError as exc:
            if exc.code in ('bad_args', 'hash_mismatch'):
                return False
            raise LineageError('internal', 'evidence verification unavailable') from None
        except Exception:
            raise LineageError('internal', 'evidence verification unavailable') from None
    return True


def _rejection(unit, *, workflow, language, selected, ctx):
    """First applicable reason; all operators and admission use this predicate."""
    if unit['kind'] == 'episode':
        return 'episode'
    if unit['level'] == 1:
        return 'level_one'
    if unit['level'] == 3:
        return 'level_three'
    if unit['privacy'] == 'private':
        return 'private'
    if unit['status'] != 'active':
        return 'inactive'
    if unit['kind'] not in _KINDS:
        return 'kind_not_inheritable'
    scope = unit['scope']
    if scope['workflow'] != workflow or scope['language'] not in (language, 'general'):
        return 'scope_mismatch'
    if not unit['receipts']:
        return 'missing_receipt'
    if not _receipts_valid(unit['receipts'], ctx):
        return 'invalid_receipt'
    if unit['kind'] == 'workflow' and unit['body']['status'] != 'promoted':
        return 'not_promoted'
    if selected is not None and unit['id'] not in selected:
        return 'not_selected'
    return None


def select(parents: Sequence[dict], units: Mapping[str, Sequence[dict]], *,
           workflow: str, language: str, selected_ids: Sequence[str] | None = None,
           ctx) -> InheritanceSelection:
    """Audit every supplied owned unit without truncation, inference or I/O writes."""
    if (not _sequence(parents) or not isinstance(units, Mapping)
            or workflow not in ('develop', 'test', 'review', 'harden', 'research', 'orchestrate')
            or type(language) is not str or not 1 <= len(language) <= 64):
        raise LineageError('bad_args', 'invalid inheritance inputs')
    try:
        canonical_bytes(language)
        owners = []
        for parent in parents:
            if type(parent) is not dict:
                raise LineageError('bad_args', 'invalid source agent')
            agent_id = parent.get('agent_id')
            _identity(agent_id, _AGENT)
            if agent_id in ('operator', 'system') or agent_id in owners:
                raise LineageError('bad_args', 'invalid source agent membership')
            owners.append(agent_id)
        if set(units) - set(owners) or set(owners) - set(units):
            raise LineageError('not_inheritable', 'source ownership is unproven')
        selected = None
        if selected_ids is not None:
            if not _sequence(selected_ids) or len(selected_ids) > 256:
                raise LineageError('bad_args', 'invalid selected unit collection')
            for unit_id in selected_ids:
                _identity(unit_id, _ID)
            selected = set(selected_ids)
            if len(selected) != len(selected_ids):
                raise LineageError('bad_args', 'duplicate selected unit')
        candidates, identities = [], set()
        for owner in sorted(owners):
            if not _sequence(units[owner]):
                raise LineageError('bad_args', 'invalid source memory collection')
            for unit in units[owner]:
                _source_shape(unit)
                key = (owner, unit['id'])
                if key in identities:
                    raise LineageError('bad_args', 'duplicate owned source unit')
                identities.add(key)
                candidates.append((owner, deepcopy(unit)))
        if selected is not None and selected - {unit_id for _, unit_id in identities}:
            raise LineageError('bad_args', 'selected unit is not owned by a source')
        inherited, rejected = [], []
        for owner, unit in sorted(candidates, key=lambda item: (item[0], item[1]['id'])):
            reason = _rejection(unit, workflow=workflow, language=language, selected=selected, ctx=ctx)
            if reason is not None:
                rejected.append({'agent_id': owner, 'unit_id': unit['id'], 'reason': reason})
                continue
            digest = sha256(canonical_bytes(unit)).hexdigest()
            source_id = unit['id']
            unit['provenance']['inherited_from'] = {
                'agent_id': owner, 'unit_id': source_id, 'unit_sha256': digest}
            memory_schema._shape(unit, 'mem_unit.schema.json')
            inherited.append({'unit': unit, 'source_agent_id': owner,
                              'source_unit_id': source_id, 'unit_sha256': digest})
        return InheritanceSelection(tuple(inherited), tuple(rejected))
    except LineageError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
        raise LineageError('bad_args', 'invalid inheritance inputs') from None


def _adopt(selection: InheritanceSelection, child_id: str) -> list[dict]:
    """Finalize deterministic child IDs; preserve source provenance and receipts."""
    _identity(child_id, _AGENT)
    if child_id in ('operator', 'system'):
        raise LineageError('bad_args', 'reserved child identity')
    result, identities = [], {}
    for original in selection.inherited:
        wrapper = deepcopy(original)
        key = {'child_id': child_id, 'source_agent_id': wrapper['source_agent_id'],
               'source_unit_id': wrapper['source_unit_id']}
        unit_id = 'inh-' + sha256(canonical_bytes(key)).hexdigest()[:44]
        if unit_id in identities:
            raise LineageError('conflict', 'adopted unit identity collision')
        identities[unit_id] = key
        unit = wrapper['unit']
        unit['id'] = unit_id
        unit['supersedes'] = []
        unit.pop('superseded_by', None)
        memory_schema._shape(unit, 'mem_unit.schema.json')
        if len(canonical_bytes(unit)) > 6000:
            raise LineageError('memory_debt', 'unit byte capacity exceeded; cuts required')
        result.append(wrapper)
    return result
