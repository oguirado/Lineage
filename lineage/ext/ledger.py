"""Shared ledger tools with closed schemas and no journal-writing callbacks.

U04's integrated ToolSpec uses mutating. Export receives mutation protection,
but appends no event. Event actor filters confer no mutation authority.
"""
from copy import deepcopy

# A-INT1: discovery can reach this extension before importing memory. Install
# its idempotent K0 seam before either registry load order consumes descriptors.
from lineage.domain import memory as _memory
_memory._install()

from lineage.core import events, export
from lineage.core.errors import LineageError
from lineage.core.registry import ToolSpec
from lineage.core.schema import SchemaError, validate
from lineage.domain import scorecard

_AGENT = {"type": "string", "minLength": 3, "maxLength": 64,
          "pattern": r"^[a-z][a-z0-9-]{2,63}(?![\s\S])"}
_INTEGER = {"type": "integer", "minimum": 0, "maximum": 9007199254740991}
_PATH = {"type": "string", "minLength": 1, "maxLength": 512,
         "pattern": r"^(?!/)(?!.*(?:^|/)\.{1,2}(?:/|$))(?!.*\\)[A-Za-z0-9._/-]+(?![\s\S])"}


def _object(properties, required=()):
    return {"type": "object", "properties": deepcopy(properties),
            "required": list(required), "additionalProperties": False}


_SCHEMAS = {
    "ledger_events": _object({
        "after": _INTEGER, "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
        "wait_ms": {"type": "integer", "minimum": 0, "maximum": 30000},
        "agent_id": _AGENT,
        "kinds": {"type": "array", "items": {"enum": list(events.KINDS)},
                  "minItems": 0, "maxItems": len(events.KINDS), "uniqueItems": True},
        "agent": _AGENT}),
    "ledger_verify": _object({"agent": _AGENT}),
    "ledger_export": _object({"out": _PATH, "agent": _AGENT}, ("out",)),
    "scorecard_get": _object({"agent_id": _AGENT, "agent": _AGENT}, ("agent_id",)),
}


def _check(name, args):
    try:
        validate(args, _SCHEMAS[name])
    except SchemaError:
        raise LineageError("bad_args", "invalid ledger tool arguments") from None


def ledger_events(args, *, context):
    _check("ledger_events", args)
    return events.read_events(context.home, after=args.get("after", 0),
                              limit=args.get("limit", 100), agent_id=args.get("agent_id"),
                              kinds=args.get("kinds", ()), wait_ms=args.get("wait_ms", 0))


def ledger_export(args, *, context):
    _check("ledger_export", args)
    return export.export_ledger(context.home, out=args["out"])


def ledger_verify(args, *, context):
    _check("ledger_verify", args)
    raw = events.verify_ledger(context.home)
    report = events._verification_data(raw)
    if not report["valid"]:
        code = "internal" if not raw["journal"]["exists"] else "hash_mismatch"
        raise LineageError(code, events._verification_detail(report))
    return report


def scorecard_get(args, *, context):
    _check("scorecard_get", args)
    return scorecard.get(args["agent_id"], context=context)


TOOLS = (
    ToolSpec("ledger_events", "Read verified committed events after a Lamport cursor.",
             _SCHEMAS["ledger_events"], ledger_events, False),
    ToolSpec("ledger_export", "Export verified history and scoped projections beneath exports/.",
             _SCHEMAS["ledger_export"], ledger_export, True),
    ToolSpec("ledger_verify", "Check journal integrity and the scorecard projection scope.",
             _SCHEMAS["ledger_verify"], ledger_verify, False),
    ToolSpec("scorecard_get", "Read agent telemetry grouped by full seat and memory arm.",
             _SCHEMAS["scorecard_get"], scorecard_get, False),
)
VALIDATORS = {}
FOLDS = {}
