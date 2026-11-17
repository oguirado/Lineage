"""Mutation-sensitive bridge descriptors; discovery performs no I/O."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

# A-K0-9: initialize the installed registry facade before binding ToolSpec.
# Its schema-aware descriptor path preserves the frozen $ref verbatim.
from lineage.domain import memory as _registry_facade
from lineage.bridge import openfresnel as client
from lineage.core.registry import ToolSpec

if TYPE_CHECKING:
    from lineage.core.app import CallContext


def _probe(args: dict[str, Any], *, context: CallContext) -> dict[str, Any]:
    effective = client.validated_args('openfresnel_probe', args, ctx=context)
    command = client.Command('openfresnel_probe', effective,
                             effective['agent'], effective['op_id'])
    options = {key: value for key, value in effective.items()
               if key not in ('agent', 'op_id')}
    return client.probe(**options, command=command, ctx=context)


def _spawn(args: dict[str, Any], *, context: CallContext) -> dict[str, Any]:
    effective = client.validated_args('openfresnel_spawn', args, ctx=context)
    command = client.Command('openfresnel_spawn', effective,
                             effective['agent'], effective['op_id'])
    options = {key: value for key, value in effective.items()
               if key not in ('agent', 'op_id', 'mode')}
    return client.spawn(effective['mode'], **options, command=command, ctx=context)


# The facade's journal descriptor flag means mutating=True. U05 classifies
# these exact names as external before consulting mutation flags; neither
# handler uses the memory-contract dispatcher or creates application events.
TOOLS = (
    ToolSpec('openfresnel_probe', 'Request external terminal capabilities',
             client.argument_schema('openfresnel_probe'), 'journal', _probe),
    ToolSpec('openfresnel_spawn', 'Request a headless Lineage terminal launch',
             client.argument_schema('openfresnel_spawn'), 'journal', _spawn),
)
VALIDATORS = {}
FOLDS = {}
