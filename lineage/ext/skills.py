"""Skill discovery, shared handlers and pure journal validation callbacks."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from lineage.core.errors import LineageError
from lineage.core.registry import ToolSpec
from lineage.domain import skills

_AGENT = {"type": "string", "minLength": 3, "maxLength": 64,
          "pattern": r"^[a-z][a-z0-9-]{2,63}(?![\s\S])"}
_HASH = {"type": "string", "minLength": 64, "maxLength": 64,
         "pattern": r"^[0-9a-f]{64}(?![\s\S])"}
_OP = {"type": "string", "minLength": 1, "maxLength": 128,
       "pattern": r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\s\S])"}
_PATH = {"type": "string", "minLength": 1, "maxLength": 512,
         "pattern": r"^(?!/)(?!.*(?:^|/)\.{1,2}(?:/|$))(?!.*\\)[A-Za-z0-9._/-]+(?![\s\S])"}
_FILES = {"type": "array", "minItems": 1, "maxItems": 256, "items": {
    "type": "object", "properties": {"path": _PATH,
        "content": {"type": "string", "minLength": 0, "maxLength": 65536}},
    "required": ["path", "content"], "additionalProperties": False}}
_REVISION = {"type": "integer", "minimum": 0, "maximum": 9007199254740991}


def _schema(properties: dict, required: list[str]) -> dict:
    return deepcopy({"type": "object", "properties": properties,
                     "required": required, "additionalProperties": False})


def _context(args: dict, context: Any) -> Any:
    actor = args.get("agent", "system")
    skills._match(actor, skills._AGENT)
    try:
        return replace(context, actor=actor, op_id=args.get("op_id"))
    except (TypeError, ValueError):
        raise LineageError("bad_args", "invalid skill context") from None


def _command(tool: str, args: dict) -> skills._Command:
    return skills._Command(tool, deepcopy(args), args["agent"], args["op_id"], args.get("expected_head"))


def _list(args: dict, *, context: Any) -> dict:
    return skills.list_skills(include_retired=args.get("include_retired", False),
                              ctx=_context(args, context))


def _get(args: dict, *, context: Any) -> dict:
    return skills.get(args["skill_id"], sha256=args.get("sha256"), ctx=_context(args, context))


def _publish(args: dict, *, context: Any) -> dict:
    return skills.publish(args["skill_id"], args["files"],
                          command=_command("skill_publish", args), ctx=_context(args, context)).value


def _retire(args: dict, *, context: Any) -> dict:
    return skills.retire(args["skill_id"], args["sha256"], args["reason"],
                         command=_command("skill_retire", args), ctx=_context(args, context)).value


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("skill_get", "Resolve immutable skill context by id and optional pin.",
             _schema({"skill_id": _AGENT, "sha256": _HASH, "agent": _AGENT}, ["skill_id"]),
             _get, False),
    ToolSpec("skill_list", "List available skill version pins and optional retired history.",
             _schema({"include_retired": {"type": "boolean"}, "agent": _AGENT}, []),
             _list, False),
    ToolSpec("skill_publish", "Publish a passive, immutable skill package.",
             _schema({"skill_id": _AGENT, "files": _FILES, "agent": _AGENT,
                      "op_id": _OP, "expected_head": _REVISION},
                     ["skill_id", "files", "agent", "op_id"]), _publish, True),
    ToolSpec("skill_retire", "Retire one pin while preserving historical resolution.",
             _schema({"skill_id": _AGENT, "sha256": _HASH,
                      "reason": {"type": "string", "minLength": 1, "maxLength": 2048},
                      "agent": _AGENT, "op_id": _OP, "expected_head": _REVISION},
                     ["skill_id", "sha256", "reason", "agent", "op_id"]), _retire, True),
)
VALIDATORS = {"skill.published": skills._validate_published,
              "skill.retired": skills._validate_retired}
FOLDS = {"skills": skills._SkillsFold()}
