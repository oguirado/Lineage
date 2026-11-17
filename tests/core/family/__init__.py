"""U05 oracle helpers. Importing this package performs no I/O or registration."""

import copy
import hashlib
import importlib
import inspect
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = "lineage.family/1"
ERRORS = frozenset("bad_args bad_op stale_rev busy internal conflict no_agent "
                   "no_run run_closed memory_required memory_debt forbidden_level "
                   "not_inheritable hash_mismatch rule_not_declared no_benchmark "
                   "heldout_forbidden seat_not_allowed fixture_readonly timeout".split())


def wire(value):
    """Independent wire encoder, never an implementation helper."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def request(kind="capabilities", **updates):
    value = dict(schema=PROTOCOL, id="request01", source="Sender_1",
                 target="Endpoint_1", kind=kind, agent="alice", payload={})
    if kind == "events.read":
        value["after"] = 0
    elif kind == "call":
        value["payload"] = {"tool": "skill_list", "args": {}}
    value.update(copy.deepcopy(updates))
    return value


def config(**updates):
    value = dict(endpoint="Endpoint_1", sources=["Sender_1", "Sender_2"],
                 tools=["skill_list", "skill_publish", "ledger_events"])
    value.update(copy.deepcopy(updates))
    return value


def op_id(value):
    raw = "\0".join(value[k] for k in ("source", "target", "id")).encode()
    return "lin-" + hashlib.sha256(raw).hexdigest()[:44]


def require_k0(case):
    """Missing dependencies are an explicit failed prerequisite, never a skip."""
    # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
    requirements = {
        "lineage.core.schema": ("validate", "strict_loads"),
        "lineage.core.registry": ("Registry", "ToolSpec", "load"),
        "lineage.core.errors": ("JSONValue", "LineageError"),
        "lineage.core.journal": ("snapshot", "transact", "verify"),
        "lineage.core.app": ("CallContext", "create_context", "DispatchResult", "list_tools", "dispatch"),
    }
    missing = []
    modules = {}
    for name, names in requirements.items():
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError as exc:
            if exc.name != name:
                raise
            missing.append(name)
            continue
        modules[name] = module
        missing.extend(name + "." + n for n in names if not hasattr(module, n))
    # A-U05: Check the integrated keyword seams, not absent documented aliases.
    signatures = {
        "lineage.core.app": {"list_tools": ("registry",),
            "dispatch": ("context", "registry"), "create_context": ("registry",)},
        "lineage.core.journal": {"snapshot": ("home",), "verify": ("home",),
            "transact": ("home", "agent", "op_id", "kind", "payload", "validators", "prepare")},
    }
    for name, functions in signatures.items():
        module = modules.get(name)
        if module is None:
            continue
        for name2, parameters in functions.items():
            fn = getattr(module, name2, None)
            if callable(fn):
                signature = inspect.signature(fn)
                missing.extend(name + "." + name2 + "(" + p + ")"
                               for p in parameters if p not in signature.parameters)
    case.assertFalse(missing, "BLOCKED U03/U04 frozen K0 seam: " + ", ".join(missing))
    return modules


def _validate_schema(value, name, boundary):
    # A-U05: Adapt missing SchemaStore by composing the integrated structural
    # validator with frozen local references; do not use the transport validator.
    documents = {}
    def document(filename):
        # A-U05: Load public schema fixtures relative to the repository.
        if filename not in documents:
            documents[filename] = json.loads((ROOT / "schemas" / filename).read_bytes())
        return documents[filename]
    def check(item, shape, base):
        # A-U05: Preserve reference, composition and closed-object assertions.
        if type(shape) is bool:
            if not shape:
                raise AssertionError("closed schema violation")
            return
        if "$ref" in shape:
            filename, _, fragment = shape["$ref"].partition("#")
            target = document(filename or base)
            for key in fragment.lstrip("/").split("/") if fragment else ():
                target = target[key.replace("~1", "/").replace("~0", "~")]
            check(item, target, filename or base)
        structural = {k:v for k,v in shape.items() if k not in {
            "$ref", "$defs", "properties", "additionalProperties", "items",
            "patternProperties", "oneOf", "anyOf", "allOf"}}
        boundary.validate(item, structural)
        if isinstance(item, dict):
            import re
            for key, child in item.items():
                shapes = ([shape["properties"][key]] if key in shape.get("properties", {}) else [])
                shapes += [v for k,v in shape.get("patternProperties", {}).items() if re.search(k,key)]
                if not shapes:
                    shapes = [shape.get("additionalProperties", True)]
                for child_shape in shapes:
                    check(child, child_shape, base)
        if isinstance(item, list) and "items" in shape:
            for child in item:
                check(child, shape["items"], base)
        for child_shape in shape.get("allOf", ()):
            check(item, child_shape, base)
        for keyword in ("oneOf", "anyOf"):
            if keyword not in shape:
                continue
            matched = 0
            for child_shape in shape[keyword]:
                try:
                    check(item, child_shape, base)
                except (AssertionError, boundary.SchemaError):
                    continue
                matched += 1
            if not (matched == 1 if keyword == "oneOf" else matched > 0):
                raise AssertionError("schema composition violation")
    check(value, name if isinstance(name, dict) else document(name),
          "family_envelope.schema.json" if isinstance(name, dict) else name)


def _registry_schema(shape):
    # A-U05: U04 preflights structural schemas only. Lower nullable branches
    # losslessly; defer recursive wire references to full handler validation.
    if isinstance(shape, list):
        return [_registry_schema(v) for v in shape]
    if not isinstance(shape, dict):
        return shape
    if "$ref" in shape:
        return {"type": "object"}
    if "anyOf" in shape:
        branches = shape["anyOf"]
        assert len(branches) == 2 and branches[1] == {"type": "null"}
        return {**_registry_schema(branches[0]), "type": [branches[0]["type"], "null"]}
    return {k: _registry_schema(v) for k,v in shape.items()}


class WireCase(unittest.TestCase):
    def valid_raw(self, raw, endpoint, filename_id):
        from lineage.core import envelope
        try:
            return envelope.validate(raw, endpoint, filename_id)
        except (envelope.InvalidEnvelope, NotImplementedError) as exc:
            self.fail("valid K0 request rejected: " + str(exc))

    def validate_request(self, value):
        # A-U05: Preserve InvalidEnvelope for negative callers; valid_raw turns
        # it into self.fail and masks the existing assertRaises assertions.
        from lineage.core import envelope
        return envelope.validate(wire(value), value["target"], value["id"])

    def assert_error(self, value, code):
        self.assertIsInstance(value, dict)
        self.assertIs(value.get("ok"), False)
        self.assertEqual(value.get("code"), code)
        self.assertLessEqual(set(value), {"ok", "code", "detail"})
        if "detail" in value:
            self.assertIsInstance(value["detail"], str)
            self.assertTrue(1 <= len(value["detail"]) <= 2048)


class RuntimeCase(WireCase):
    """Real frozen registry and journal; no substitute transaction engine."""

    def setUp(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        modules = require_k0(self)
        self.reg = modules["lineage.core.registry"]
        self.journal = modules["lineage.core.journal"]
        self.app = modules["lineage.core.app"]
        self.schema = modules["lineage.core.schema"]
        self.err = modules["lineage.core.errors"]
        # A-U05: Make valid fixture control files private independently of the
        # invoking host umask; hostile-mode cases still explicitly chmod entries.
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)
        self.temp = tempfile.TemporaryDirectory(prefix="lineage-u05-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.endpoint = self.home / "family" / "Endpoint_1"
        self.endpoint.mkdir(parents=True, mode=0o700)
        self.write_config(config())
        # Registry construction is intentionally delegated to the public loader.
        # The inline module uses the real U03 transaction API and frozen tool names.
        import sys
        package = self.home / "oracle_extension"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        frozen = json.loads((ROOT / "schemas" / "family_envelope.schema.json").read_text())
        event_schema = json.loads((ROOT / "schemas" / "event.schema.json").read_text())
        branches = next(b["then"]["properties"]["payload"]["oneOf"]
                        for b in frozen["allOf"]
                        if b["if"]["properties"]["kind"]["const"] == "call")
        input_schemas = {}
        for branch in branches:
            name = branch["properties"]["tool"]["const"]
            if name not in {"skill_list", "skill_publish", "ledger_events", "run_close", "openfresnel_spawn"}:
                continue
            shaped = copy.deepcopy(branch["properties"]["args"])
            shaped["properties"]["agent"] = copy.deepcopy(frozen["properties"]["agent"])
            if name in {"skill_publish", "run_close", "openfresnel_spawn"}:
                shaped["properties"]["op_id"] = copy.deepcopy(event_schema["properties"]["op_id"])
                shaped["required"] += ["agent", "op_id"]
            input_schemas[name] = shaped
        source = (EXTENSION + "\nWIRE_SCHEMAS = " + repr(input_schemas)
                  + "\nSCHEMAS = " + repr({k: _registry_schema(v) for k,v in input_schemas.items()})
                  + "\n" + EXTENSION_TOOLS)
        (package / "tools.py").write_text(source, encoding="utf-8")
        sys.path.insert(0, str(self.home))
        self.addCleanup(lambda: sys.path.remove(str(self.home)))
        def clear_modules():
            for name in tuple(sys.modules):
                if name == "oracle_extension" or name.startswith("oracle_extension."):
                    del sys.modules[name]
        self.addCleanup(clear_modules)
        self.registry = self.reg.load(package="oracle_extension")
        self.extension = importlib.import_module("oracle_extension.tools")
        # A-U05: The integrated context carries home/validator/fold services;
        # registry travels in the lane's existing private runtime seam.
        from dataclasses import dataclass
        from lineage.core import jsonlane
        @dataclass(frozen=True)
        class OperatorContext(self.app.CallContext):
            authority: str = "operator"
            transport: str = "library"
        context = OperatorContext(self.home, self.registry.validators, self.registry.folds,
                                  "system")
        self.ctx = jsonlane._Runtime(context, self.registry)

    def write_config(self, value):
        dest = self.endpoint / "config.json"
        temporary = self.endpoint / "config.next"
        temporary.write_bytes(wire(value) + b"\n")
        os.replace(temporary, dest)

    def lane(self, value, cfg=None):
        from lineage.core import jsonlane
        if cfg is not None:
            self.write_config(cfg)
        else:
            cfg = json.loads((self.endpoint / "config.json").read_bytes())
        return jsonlane.dispatch(value, cfg, ctx=self.ctx)

    def mailbox(self):
        from lineage.core.family import Mailbox
        box = Mailbox("Endpoint_1", ctx=self.ctx)
        box.open()
        self.addCleanup(box.release)
        return box

    def mutation(self, **updates):
        return request("call", payload={"tool": "skill_publish", "args": {
            "skill_id": "sample-skill", "files": [{"path": "SKILL.md", "content": "# Sample\n"}]
        }}, **updates)

    def assert_receipt(self, value):
        # A-U05: SchemaStore is absent; resolve the frozen receipt schema in
        # this independent test adapter, retaining full structural validation.
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        _validate_schema(value, "family_receipt.schema.json", self.schema)

    def assert_witness(self, value, envelope):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        snap = self.journal.snapshot(self.home)
        commit = value["untrusted"]["commit"]
        selected = [e for e in snap if e["id"] in commit["event_ids"]]
        self.assertEqual(len(selected), len(commit["event_ids"]))
        self.assertTrue(selected)
        self.assertEqual(selected[-1]["lamport"], commit["head"])
        self.assertEqual(selected[-1]["sha256"], commit["sha256"])
        for event in selected:
            self.assertEqual(event["agent"], envelope["agent"])
            self.assertEqual(event["op_id"], op_id(envelope))
        self.assertTrue(self.journal.verify(self.home)["ok"])


EXTENSION = '''"""Contract-valid local test extension, not a domain implementation."""
import copy
import hashlib
import json
import time
from lineage.core import journal
from lineage.core.errors import LineageError
from lineage.core.registry import ToolSpec
from lineage.core import schema
from tests.core.family import _validate_schema

SEEN = []
FAIL = None
REJECT = None
HAS_RESULT = False
RESULT = None
_IDS = iter("e-" + format(i, "016x") for i in range(1, 10001))
def encode(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def read(args, *, context):
    # A-U05: Integrated handlers take keyword-only context.
    # A-U05: Retain complete frozen input validation beyond U04 structural schemas.
    _validate_schema(args, WIRE_SCHEMAS["skill_list"], schema)
    SEEN.append((copy.deepcopy(args), context))
    if FAIL is not None: raise FAIL
    if HAS_RESULT: return copy.deepcopy(RESULT)
    return {"skills": []}
def publish(args, *, context):
    # A-U05: Use the real keyword transaction API and render its returned event.
    # A-U05: Retain complete frozen input validation beyond U04 structural schemas.
    _validate_schema(args, WIRE_SCHEMAS["skill_publish"], schema)
    SEEN.append((copy.deepcopy(args), context))
    if FAIL is not None: raise FAIL
    files=copy.deepcopy(args["files"])
    sha=hashlib.sha256(encode(files)).hexdigest()
    payload={"skill_id":args["skill_id"], "sha256":sha, "files":files}
    def prepare(history, draft):
        # A-U05: expected_head belongs to the fixture's locked domain prepare;
        # journal.transact checks exact replay before invoking this callback.
        head=history[-1]["lamport"] if history else 0
        if "expected_head" in args and args["expected_head"] != head:
            raise LineageError("stale_rev")
        return copy.deepcopy(payload)
    event=journal.transact(context.home,agent=args["agent"],op_id=args["op_id"],
        kind="skill.published",payload=copy.deepcopy(args),validators=context.validators,
        prepare=prepare,clock=lambda:1700000000000,id_factory=lambda:next(_IDS))
    payload=event["payload"]
    return {"skill":{"skill_id":payload["skill_id"],"sha256":payload["sha256"],
                     "retired":False,"files":payload["files"]},
            "commit":{"event_ids":[event["id"]],"head":event["lamport"],"sha256":event["sha256"]}}
def cursor(home, after, *, limit=100, wait_ms=0, agent_id=None, kinds=()):
    # A-U05: journal.read is absent; this local read fixture observes verified
    # tuple snapshots and preserves the frozen cursor/filter/wait contract.
    deadline=time.monotonic()+wait_ms/1000
    while True:
        history=journal.snapshot(home)
        head=history[-1]["lamport"] if history else 0
        if after>head:
            return {"events":[],"next_after":head,"head":head,"has_more":False,"resync":True}
        matches=[e for e in history if e["lamport"]>after
                 and (agent_id is None or e["agent"]==agent_id)
                 and (not kinds or e["kind"] in kinds)]
        page=matches[:limit]; more=len(matches)>len(page)
        if page or not wait_ms or time.monotonic()>=deadline:
            return {"events":page,"next_after":page[-1]["lamport"] if more else head,
                    "head":head,"has_more":more,"resync":False}
        time.sleep(min(0.01,max(0,deadline-time.monotonic())))
def events(args, *, context):
    # A-U05: Delegate the unavailable journal.read seam to the local read fixture.
    # A-U05: Retain complete frozen input validation beyond U04 structural schemas.
    _validate_schema(args, WIRE_SCHEMAS["ledger_events"], schema)
    SEEN.append((copy.deepcopy(args),context))
    if FAIL is not None: raise FAIL
    return cursor(context.home,args.get("after",0),limit=args.get("limit",100),
                  wait_ms=args.get("wait_ms",0),agent_id=args.get("agent_id"),
                  kinds=args.get("kinds",()))
def validate(history, event):
    # A-U05: The real journal validator receives history/event, without ctx.
    if REJECT is not None: raise REJECT
def close_refusal(args, *, context):
    # A-U05: Keep memory refusal inside real transaction preparation.
    # A-U05: Retain complete frozen input validation beyond U04 structural schemas.
    _validate_schema(args, WIRE_SCHEMAS["run_close"], schema)
    def prepare(history, draft):
        # A-U05: Match the integrated two-argument prepare callback.
        raise LineageError("memory_required","local transport admission fixture")
    event=journal.transact(context.home,agent=args["agent"],op_id=args["op_id"],
        kind="skill.published",payload=copy.deepcopy(args),validators=context.validators,
        prepare=prepare,clock=lambda:1700000000000,id_factory=lambda:next(_IDS))
    raise AssertionError("rejecting prepare must not render")
def external(args, *, context):
    # A-U05: Integrated external handlers take keyword-only context.
    # A-U05: Retain complete frozen input validation beyond U04 structural schemas.
    _validate_schema(args, WIRE_SCHEMAS["openfresnel_spawn"], schema)
    SEEN.append((copy.deepcopy(args),context))
    if FAIL is not None: raise FAIL
    rid=hashlib.sha256(encode({"agent":args["agent"],"op_id":args["op_id"]})).hexdigest()[:32]
    return {"rid":rid,"state":"launched","terminal_id":"test-terminal", "pane_id":None,
            "screen_id":None,"receipt_family":"compiler"}
'''

# A-U05: ToolSpec exposes mutating; the lane classifies frozen external tools.
EXTENSION_TOOLS = '''
TOOLS=(
 ToolSpec(name="skill_list",description="List skills",mutating=False,handler=read,
          input_schema=SCHEMAS["skill_list"]),
 ToolSpec(name="skill_publish",description="Publish skill",mutating=True,handler=publish,
          input_schema=SCHEMAS["skill_publish"]),
 ToolSpec(name="ledger_events",description="Read events",mutating=False,handler=events,
          input_schema=SCHEMAS["ledger_events"]),
 ToolSpec(name="run_close",description="Reject missing memory in local fixture",mutating=True,
          handler=close_refusal,input_schema=SCHEMAS["run_close"]),
 ToolSpec(name="openfresnel_spawn",description="Offline external acknowledgement",mutating=True,
          handler=external,input_schema=SCHEMAS["openfresnel_spawn"]),
)
VALIDATORS={"skill.published":validate}
FOLDS={}
'''
