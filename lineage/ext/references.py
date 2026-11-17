"""Read-only reference adapters for the installed shared registry."""
from lineage.core.errors import LineageError
from lineage.core.registry import ToolSpec
from lineage.core.schema import SchemaError, validate
from lineage.domain import references

_INPUT = {"type": "object", "properties": {
    "ref_id": {"enum": ["gold_s1", "memory_v21"]},
    "agent": {"type": "string", "minLength": 3, "maxLength": 64,
              "pattern": r"^[a-z][a-z0-9-]{2,63}(?![\s\S])"}},
    "required": ["ref_id"], "additionalProperties": False}


def _call(function, args, context):
    try:
        validate(args, _INPUT)
    except SchemaError:
        raise LineageError("bad_args", {"reason": "invalid_reference_arguments"}) from None
    try:
        return function(args["ref_id"], ctx=context)
    except references.ReferenceError as exc:
        raise LineageError(exc.code, exc.detail) from None


def handle_reference_get(args: dict, context: object = None) -> dict:
    return _call(references.get, args, context)


def handle_reference_verify(args: dict, context: object = None) -> dict:
    return _call(references.verify, args, context)


TOOLS = (
    ToolSpec(name="reference_get", description="Read a verified bundled founding reference.",
             input_schema=_INPUT, handler=handle_reference_get, mutating=False),
    ToolSpec(name="reference_verify", description="Verify a bundled founding reference package.",
             input_schema=_INPUT, handler=handle_reference_verify, mutating=False),
)
VALIDATORS = {}
FOLDS = {}
