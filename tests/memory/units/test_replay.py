"""A17–A18: retained-prefix results, digest identity and immutable unit ids."""
import copy
from ._support import IntegrationCase, OWNER, canonical, unit
from lineage.domain.memory import units


class ReplayTests(IntegrationCase):
    def test_a17_original_result_after_later_write_and_stale_expected_head(self):
        self.runtime()
        value = unit()
        first = self.write(value, op="retained-operation")
        first_wrapped = {"untrusted": first.value}
        self.write(unit(uid="unit_002"))
        before = self.fingerprint()
        replay = self.write(value, op="retained-operation", expected=0)
        self.assertEqual(canonical({"untrusted": replay.value}), canonical(first_wrapped))
        self.assertEqual(replay.event, first.event)
        self.assertEqual((replay.head, replay.sha256), (first.head, first.sha256))
        self.assertNotIn("replay", replay.value)
        self.assertEqual(self.fingerprint(), before)
        self.reject("stale_rev", lambda: self.write(unit(uid="unit_003"), expected=0))

    def test_a17_changed_content_tool_and_binding_are_bad_op(self):
        self.runtime()
        value = unit()
        self.write(value, op="retained-operation")
        changed = copy.deepcopy(value)
        changed["statement"] += " changed"
        self.reject("bad_op", lambda: self.write(changed, op="retained-operation"))
        self.reject("bad_op", lambda: self.write(value, op="retained-operation", run_id="unknown1"))
        command = self.command({"agent_id": OWNER, "unit": value}, op="retained-operation")
        from dataclasses import replace
        self.reject("bad_op", lambda: units.put(OWNER, value, command=replace(command, tool="agent_create"), ctx=self.ctx))

    def test_a18_distinct_operation_cannot_overwrite_equal_or_changed_unit(self):
        self.runtime()
        value = unit()
        original = self.write(value, op="first-operation")
        self.reject("conflict", lambda: self.write(value, op="second-operation"))
        changed = copy.deepcopy(value)
        changed["statement"] += " changed"
        self.reject("conflict", lambda: self.write(changed, op="third-operation"))
        result = units.get(OWNER, value["id"], ctx=self.ctx)
        result["unit"]["body"]["blocked_use"].append("caller corruption")
        original.value["unit"]["statement"] = "caller corruption"
        self.assertEqual(units.get(OWNER, value["id"], ctx=self.ctx)["unit"], value)
        self.assertEqual(self.write(value, op="first-operation").value["unit"], value)
        successor = unit(uid="unit_002")
        successor["supersedes"] = [value["id"]]
        self.write(successor)

    def test_a18_identity_is_scoped_to_owner(self):
        self.runtime()
        self.write()
        self.born("other-agent")
        other = unit(actor="other-agent")
        self.assertEqual(self.write(other, owner="other-agent", actor="other-agent").value["unit"], other)
