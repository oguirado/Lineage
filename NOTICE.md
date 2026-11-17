| Old module, identifier, or locator | New module, identifier, or locator |
|---|---|
| `bridge.room.ext.events` | `lineage.core.events` |
| `bridge/room/ext/events.py` | `lineage/core/events.py` |
| `bridge.room.ext.export` | `lineage.core.export` |
| `bridge/room/ext/export.py` | `lineage/core/export.py` |
| `bridge.room.ext.activity` | `lineage.core.activity` |
| `bridge/room/ext/activity.py` | `lineage/core/activity.py` |
| `bridge.room.ext.send` | `lineage.core.send` |
| `bridge/room/ext/send.py` | `lineage/core/send.py` |
| `bridge.room.ext.lifecycle` | `lineage.core.lifecycle` |
| `bridge/room/ext/lifecycle.py` | `lineage/core/lifecycle.py` |
| `bridge.room.ext.acquire` | `lineage.core.acquire` |
| `bridge/room/ext/acquire.py` | `lineage/core/acquire.py` |
| `bridge.room.store` | `lineage.core.journal` |
| `bridge/room/store.py` | `lineage/core/journal.py` |
| `bridge.room._lock` | `lineage.core.locking` |
| `bridge/room/_lock.py` | `lineage/core/locking.py` |
| `bridge.room.family_envelope` | `lineage.core.envelope` |
| `bridge/room/family_envelope.py` | `lineage/core/envelope.py` |
| `bridge.room.__main__` | `lineage.core.cli` |
| `bridge/room/__main__.py` | `lineage/core/cli.py` |
| `from bridge.room.ext import export` | `from lineage.core import export` |
| `from bridge.room.ext import acquire` | `from lineage.core import acquire` |
| `from bridge.room.ext import send` | `from lineage.core import send` |
| `bridge.room.ext` | `lineage.core.registry` |
| `bridge/room/ext/__init__.py` | `lineage/core/registry.py` |
| `bridge/room/ext/` | `lineage/core/` |
| `bridge.room` | `lineage.core` |
| `bridge/room` | `lineage/core` |
| `bridge.plan` | `lineage.core.plan` |
| `bridge/plan` | `lineage/core/plan` |
| `bridge.tests` | `tests.core.regression` |
| `bridge/tests` | `tests/core/regression` |
| `from ._lock import` | `from .locking import` |
| `from . import register` | `from .registry import register` |
| `full = "%s.%s" % (__name__, mod)` | `full = "%s.%s" % (__package__, mod)` |
| `BRIDGE = HERE.parent.parent` | `NAMESPACE_ROOT = HERE.parent.parent.parent` |
| `APP.parent.parent / "tests/room/u87/expected.json"` | `APP.parents[2] / "tests/core/regression/fixtures/room/u87/expected.json"` |
| `HERE / "legacy_tools.json"` | `ROOT / "tests/core/regression/fixtures/room/u94/legacy_tools.json"` |
| `os.path.join(repo, "docs",` | `os.path.join(repo, "lineage", "core", "resources", "docs",` |
| `"fixtures/` | `"tests/core/regression/fixtures/` |
| `/ "fixtures"` | `/ "tests/core/regression/fixtures"` |
| `"schemas/` | `"lineage/core/resources/schemas/` |
| `"docs/` | `"lineage/core/resources/docs/` |
| `/ "docs"` | `/ "lineage/core/resources/docs"` |
| `"bridge"` | `"lineage"` |
| `'fixtures/` | `'tests/core/regression/fixtures/` |
| `/ 'fixtures'` | `/ 'tests/core/regression/fixtures'` |
| `'schemas/` | `'lineage/core/resources/schemas/` |
| `'docs/` | `'lineage/core/resources/docs/` |
| `/ 'docs'` | `/ 'lineage/core/resources/docs'` |
| `'bridge'` | `'lineage'` |
| `CW_` | `LINEAGE_` |
| `CW CLI` | `Lineage CLI` |
| `.context-wall` | `.lineage` |
| `context-wall` | `lineage` |
| `TaskLight` | `Lineage` |
| `tasklight` | `lineage` |
| `bridge.` | `lineage.` |
| `BRIDGE` | `NAMESPACE_ROOT` |
| `cw_home` | `lineage_home` |
| `context_wall` | `lineage` |
| `from bridge.room.ext import events` | `from lineage.core import events` |
| `from bridge.room.ext import activity` | `from lineage.core import activity` |
| `from bridge.room.ext import lifecycle` | `from lineage.core import lifecycle` |
| `from bridge.room import store` | `from lineage.core import journal as store` |
| `{"store"}` | `{"journal"}` |
| Test locator `.parents[n]` | `.parents[n + 1]` (test package gains one directory; production `APP` locators retain their explicit root) |

The literal rows use one longest-match, non-recursive substitution; the last row applies only to copied test locators. Package-import aliases `store`, `_lock`, and `ext` refer to the same extracted module objects (`journal`, `locking`, and `registry`). `core.__main__` delegates to `core.cli`; `core.errors.RoomError` re-exports the original exception class. These facades preserve the pre-redesign calling conventions.

# Attribution and licence

The Python core and regression material are extracted by copying TaskLight from the verified seed supplied for this campaign. No upstream source is edited. The supplied GNU Affero General Public License text is retained byte-for-byte in `lineage/core/resources/LICENSE`. SPDX: AGPL-3.0-only. Separate commercial or dual-licensing rights require a separate grant; none is granted by this extraction.

# Extraction evidence

- Rename map: 67 rules [MEASURED].
- Verified seed manifest SHA-256: `f999a63de5b3b797a424d4eb1de78491639ceb875460ab72188f71e48f941f68` [MEASURED].
- Seed discovery: 1817 distinct outcomes; 1711 green; selected candidates: 1604 green before extraction [MEASURED].
- Discovery uses the standard `test*.py` pattern across the room, plan, and family suites. Hook/observer tests, the in-flight hook unit and external setup/docs tests are outside the extraction candidates. `tests/core/DROPPED.md` lists every exclusion.
- Baseline executes from the seed inside a disposable overlay in a user/PID/mount namespace. Scratch writes and isolated-interpreter bytecode stay in that overlay, leaving the seed on disk untouched. The namespace maps the invoking user to root only to permit the overlay mount.
- Regression assets and resource documents move with the same map. No production policy, admission rule, tool descriptor, event format, locking primitive, or exit code is redesigned.
- `tests/core/regression/fixtures/seed_results.json` records each measured outcome using renamed identifiers. `selection.json` freezes the selected green IDs. The suite refuses missing IDs and never converts a selected failure into a skip.
- Every test invocation uses `unshare --user --pid --fork --kill-child --mount-proc`. The runner adds `-B` only to Python children to keep bytecode out of source trees. No process-group signalling is used.
- Run the final suite from the repository root: `unshare --user --pid --fork --kill-child --mount-proc python3 -m unittest discover -s tests/core/regression -t .`.

Hook-only classes inside mixed legacy regression files are excluded by class as well as filename; their six seed-green methods are explicitly listed in `tests/core/DROPPED.md`. Their unrelated store and transport tests remain selected.

Final measured green candidate equality: 1604 before and 1604 after [MEASURED], with no missing, unexpected, skipped or failed selected IDs. The full per-ID outcomes are in `tests/core/regression/fixtures/seed_results.json` and `renamed_results.json`; `extraction_evidence.json` records the equality and negative controls.

Independent final verification [MEASURED]: `Ran 1604 tests in 288.845s`; `OK`; exit code 0. After the run, both the seed manifest and the frozen regression manifest verify, and all 92 regression files are listed in the frozen manifest [MEASURED].
