"""Verified ledger cursors, canonical agent projection integrity and CLI delegation.

Matches are filtered before limiting a page. Exhausted queries advance to the
captured global head, and polling waits for a match using only monotonic time.
Every snapshot releases the journal lock before waiting.
"""
from collections.abc import Mapping, Sequence
from copy import deepcopy
import time

from . import journal
from .errors import LineageError

KINDS = ("reference.pinned", "skill.published", "skill.retired", "agent.born",
         "agent.status", "memory.put", "memory.retire", "run.open", "run.beat",
         "run.close", "bench.declared", "bench.result", "bench.verdict")


def read_events(home=None, *, after=0, limit=100, agent_id=None, kinds=(), wait_ms=0):
    from lineage.domain.scorecard import _AGENT, _matches
    if (type(after) is not int or not 0 <= after <= 9007199254740991
            or type(limit) is not int or not 1 <= limit <= 1000
            or type(wait_ms) is not int or not 0 <= wait_ms <= 30000
            or (agent_id is not None and not _matches(_AGENT, agent_id))):
        raise LineageError("bad_args", "invalid cursor arguments")
    if kinds is not None:
        if (not isinstance(kinds, Sequence) or isinstance(kinds, (str, bytes))
                or len(kinds) > len(KINDS)
                or any(type(kind) is not str or kind not in KINDS for kind in kinds)
                or len(set(kinds)) != len(kinds)):
            raise LineageError("bad_args", "invalid event kinds")
    selected = frozenset(kinds or ())
    deadline = time.monotonic() + wait_ms / 1000
    while True:
        history = journal.snapshot(home)
        head = history[-1]["lamport"] if history else 0
        if after > head:
            return {"events": [], "next_after": 0, "head": head,
                    "has_more": False, "resync": True}
        page, cursor = [], after
        for event in history:
            if event["lamport"] <= after:
                continue
            matches = ((agent_id is None or event["agent"] == agent_id)
                       and (not selected or event["kind"] in selected))
            # Consume nonmatches beyond a full page, but leave the next match
            # for the following cursor. A filter hole never strands a reader.
            if matches and len(page) == limit:
                break
            cursor = event["lamport"]
            if matches:
                page.append(event)
        result = {"events": deepcopy(page), "next_after": cursor,
                  "head": head, "has_more": cursor < head, "resync": False}
        if page or wait_ms == 0 or time.monotonic() >= deadline:
            return result
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return result
        time.sleep(min(0.025, remaining))


def verify_ledger(home=None, *, expected_head: Mapping | None = None,
                  lock_timeout_s=journal.LOCK_TIMEOUT_S):
    """Preserve the journal report and certify all canonical agent projection files."""
    from .export import _Tree, _application_files, _capture, _io_boundary, _projections, _verify_journal
    with _io_boundary():
        report, history = _capture(home, expected_head=expected_head, lock_timeout_s=lock_timeout_s)
        projections = {"scope": "agents", "checked": [], "errors": [], "unverified": []}
        if not report["ok"]:
            return {"ok": False, "journal": report, "projections": projections}
        with _Tree(home) as tree:
            files, _ = _application_files(tree)
            projections = _projections(history, files)
            tree.unchanged()
            current = _verify_journal(home, expected_head={"lamport": report["head"],
                                                          "sha256": report["head_sha256"]},
                                      lock_timeout_s=lock_timeout_s)
            if current != report:
                raise LineageError("busy", "journal changed during verification")
            tree.unchanged()
        return {"ok": not projections["errors"], "journal": report, "projections": projections,
                "unverified": _unverified(history, projections)}


def _unverified(history, projections):
    result = [{'scope': 'external_openfresnel',
               'reason': 'external state and application completion were not inspected'}]
    result.extend({'scope': path, 'reason': 'opaque projection is outside the deterministic rebuild scope'}
                  for path in projections['unverified'])
    ran = {event['payload'].get('record', {}).get('agent_id')
           for event in history if event['kind'] == 'run.close'}
    for event in history:
        if event['kind'] == 'agent.born':
            agent_id = event['payload']['record']['agent_id']
            if agent_id not in ran:
                result.append({'scope': 'scorecard:' + agent_id,
                               'reason': 'agent has no completed runs; fitness is not measured'})
    return result


def _verification_data(report):
    """Translate the integrated journal/scope reports to the frozen wire shape.

    Opaque caches remain unverified internally. The public contract has no field
    certifying them, so only actual integrity failures and torn-tail warnings
    appear in issues.
    """
    source = report["journal"]
    issues = [{"path": issue["path"], "line": issue.get("line"),
               "code": "bad_args" if issue["code"] == "bad_args" else "hash_mismatch",
               "detail": issue["detail"][:2048]}
              for issue in source["errors"]]
    issues.extend({"path": issue["path"], "line": None, "code": "projection_drift",
                   "detail": issue["reason"]}
                  for issue in report["projections"]["errors"])
    tail = source["torn_tail"]
    if tail:
        issues.append({"path": "ledger/main/events.jsonl", "line": tail["line"],
                       "code": "torn_tail", "detail": "uncommitted final line"})
    # A-OPC1: the ledger_verify result schema is frozen (closed); declared
    # non-verification (R4) is reported by `lineage doctor`, not by this tool.
    return {"valid": report["ok"], "head": source["head"],
            "sha256": source["head_sha256"] if source["head"] else None,
            "torn_tail_bytes": tail["byte_length"] if tail else 0, "issues": issues}


def _verification_detail(report):
    """A bounded string diagnostic with relative file and line coordinates."""
    return "; ".join(issue["path"] + (":" + str(issue["line"]) if issue["line"] else "")
                     + ": " + issue["code"] + ": " + issue["detail"]
                     for issue in report["issues"])[:2048]


def _delegate(name, args, *, context, registry, stdout):
    from .app import dispatch
    if name is None:
        payload, code = {"ok": False, "code": "bad_args"}, 2
    else:
        result = dispatch(name, args, context=context, registry=registry)
        payload, code = result.payload, result.exit_code
    try:
        stdout.write(journal.canonical_bytes(payload).decode("utf-8") + "\n")
        stdout.flush()
    except Exception:
        return 3
    return code


def verify_main(argv, *, context, registry, stdin, stdout, stderr):
    return _delegate(None if argv else "ledger_verify", {}, context=context,
                     registry=registry, stdout=stdout)


def _install_projection_verification():
    """Compose D-VER1 with the integrated dual-call journal verification seam.

    Keep the native report/signature and the Services-backed report form. The
    private capture legs unwrap native verification to avoid recursive checks.
    """
    from functools import wraps
    from lineage.domain import memory

    previous = memory._verify
    if getattr(previous, '_agent_projection_verifier', False):
        return

    @wraps(previous)
    def verify(*args, ctx=None, projections=True, **kwargs):
        raw = previous(*args, ctx=ctx, projections=False, **kwargs)
        if not projections:
            return raw
        home = ctx.services.home if ctx is not None else (args[0] if args else kwargs.get('home'))
        checked = verify_ledger(home, expected_head=kwargs.get('expected_head'),
                                lock_timeout_s=kwargs.get('lock_timeout_s', journal.LOCK_TIMEOUT_S))
        if ctx is not None:
            return _verification_data(checked)
        result = deepcopy(checked['journal'])
        result['ok'] = checked['ok']
        result['errors'].extend({'path': issue['path'], 'line': None,
                                 'code': 'projection_drift', 'detail': issue['reason']}
                                for issue in checked['projections']['errors'])
        return result

    verify._agent_projection_verifier = True
    # _install() may rebind facades after a provider reload. Keep its stable
    # function identity rather than layering a fresh wrapper on every load.
    memory._verify = verify
    if journal.verify is previous:
        journal.verify = verify
