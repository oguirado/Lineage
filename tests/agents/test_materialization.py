"""Derived projections, confinement, durable recovery and drift integration."""
from copy import deepcopy
from hashlib import sha256
import shutil
from pathlib import Path
from unittest import mock
from lineage.core import journal
from lineage.core.errors import LineageError
from . import (CONSTITUTION, OracleCase, agents, brief, canonical, expected_brief,
               record, unit)


class MaterializationTests(OracleCase):
    def test_a35_exact_layout_files_and_rebuild_bytes(self):
        event = self.seed()
        paths = self.materialize()
        self.assertIs(type(paths), tuple)
        expected_names = {"agent.json", "CONSTITUTION.md", "BRIEF_HEAD.md"}
        directory = self.projection_dir()
        self.assertTrue(expected_names <= {p.name for p in paths})
        for p in paths:
            self.assertTrue(p.is_relative_to(self.home))
        value = event["payload"]["record"]
        # Canonical JSON has no LF; the journal alone adds a JSONL delimiter.
        actual_json = (directory / "agent.json").read_bytes()
        self.assertEqual(actual_json, canonical(value))
        self.assertEqual((directory / "CONSTITUTION.md").read_bytes(), CONSTITUTION)
        self.assertEqual((directory / "BRIEF_HEAD.md").read_bytes(), expected_brief(value))
        captured = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
        shutil.rmtree(directory)
        self.materialize()
        self.assertEqual({p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}, captured)
        self.assertEqual(len(self.assert_chain()), 1)

    def test_a35_memory_projection_owned_by_u11(self):
        self.seed()
        self.materialize()
        store = self.require_peer("lineage.domain.memory.store")
        before = self.inventory()
        # A-U12: U11 rebuild consumes a folded Snapshot and Services-backed Context.
        files = store.rebuild("agent-one", snapshot=self.memory_snapshot(), ctx=self.memory_context())
        self.assertIs(type(files), tuple)
        again = store.rebuild("agent-one", snapshot=self.memory_snapshot(), ctx=self.memory_context())
        self.assertEqual(files, again)
        self.assertEqual(self.inventory(), before)

    def test_a36_unsafe_language_hash_component_and_exact_wire_value(self):
        for index, language in enumerate(("../escape", "a/b", ".", "..", "日本語", "/absolute-looking", "C:\\folder")):
            name = f"agent-{index}"
            event = self.seed(name, language=language)
            self.materialize(name)
            directory = self.projection_dir(name, language)
            self.assertTrue((directory / "agent.json").is_file())
            self.assertEqual(self.invoke(agents.get, name, ctx=self.ctx)["record"]["language"], language)
            self.assertEqual(event["payload"]["record"]["language"], language)
        self.assertFalse((self.root / "escape").exists())

    def test_a36_symlinked_parent_component_is_refused(self):
        self.seed()
        outside = self.root / "outside"
        outside.mkdir()
        (self.home / "agents").symlink_to(outside, target_is_directory=True)
        before = list(outside.iterdir())
        self.reject("internal", agents.materialize, "agent-one", snapshot=journal.snapshot(self.home), ctx=self.ctx)
        self.assertEqual(list(outside.iterdir()), before)

    def test_a36_symlinked_agent_and_individual_destination_are_refused(self):
        self.seed()
        directory = self.projection_dir()
        directory.parent.mkdir(parents=True)
        outside = self.root / "outside"
        outside.mkdir()
        directory.symlink_to(outside, target_is_directory=True)
        self.reject("internal", agents.materialize, "agent-one", snapshot=journal.snapshot(self.home), ctx=self.ctx)
        directory.unlink()
        directory.mkdir()
        target = outside / "protected.txt"
        target.write_bytes(b"protected")
        for name in ("agent.json", "CONSTITUTION.md", "BRIEF_HEAD.md"):
            link = directory / name
            link.symlink_to(target)
            self.reject("internal", agents.materialize, "agent-one", snapshot=journal.snapshot(self.home), ctx=self.ctx)
            self.assertEqual(target.read_bytes(), b"protected")
            link.unlink()

    def test_a36_destination_swap_before_publication_cannot_escape(self):
        self.seed()
        self.materialize()
        directory = self.projection_dir()
        outside = self.root / "outside"
        outside.mkdir()
        directory.rename(directory.with_name("previous"))
        directory.symlink_to(outside, target_is_directory=True)
        self.reject("internal", agents.materialize, "agent-one", snapshot=journal.snapshot(self.home), ctx=self.ctx)
        self.assertEqual(list(outside.iterdir()), [])

    def test_a37_postcommit_publication_failure_preserves_birth_and_exact_retry(self):
        args = self.arguments()
        command = self.command(args)
        with mock.patch.object(agents, "materialize", side_effect=OSError("fixture publication refusal")):
            with self.assertRaises(LineageError) as raised:
                self.invoke(agents.create, **args, command=command, ctx=self.ctx)
        self.assertEqual(raised.exception.code, "internal")
        events = self.assert_chain()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "agent.born")
        before = self.ledger()
        result = self.create(command=command)
        self.assertEqual(self.ledger(), before)
        self.assertEqual(result.value["record"], events[0]["payload"]["record"])
        self.assertEqual(result.value["commit"], {"event_ids": [events[0]["id"]], "head": 1, "sha256": events[0]["sha256"]})
        self.assertTrue((self.projection_dir() / "agent.json").is_file())

    def test_a37_replay_recovery_keeps_current_projection(self):
        args = self.arguments()
        command = self.command(args)
        first = self.create(command=command)
        self.append_fixture("memory.put", {"agent_id": "agent-one", "unit": unit()})
        self.materialize()
        current = self.inventory()
        original = first.value
        replay = self.create(command=command)
        self.assertEqual(replay.value, original)
        self.assertEqual(self.inventory(), current, "old replay overwrote a current projection")

    def test_a38_integrated_verifier_must_report_agent_and_scorecard_drift(self):
        self.seed()
        self.materialize()
        directory = self.projection_dir()
        (directory / "agent.json").write_bytes(b'{"status":"promoted"}\n')
        (directory / "scorecard.json").write_bytes(b'{"score":999}\n')
        report = journal.verify(self.home)
        self.assertFalse(report["ok"], "BLOCKED/HOLD: U03/U14 projection-verifier integration AUSENTE")
        self.assertTrue(report["errors"])
        self.assertNotIn(str(self.home), canonical(report).decode())

    def test_a39_missing_agent_projection_is_not_clean_verification(self):
        self.seed()
        self.materialize()
        expected = self.invoke(agents.get, "agent-one", ctx=self.ctx)
        target = self.projection_dir() / "agent.json"
        target.unlink()
        self.assertEqual(self.invoke(agents.get, "agent-one", ctx=self.ctx), expected)
        self.assertFalse(target.exists())
        report = journal.verify(self.home)
        self.assertFalse(report["ok"], "BLOCKED/HOLD: missing projection was reported clean")
        self.materialize()
        self.assertTrue(target.is_file())

    def test_a39_missing_memory_projection_is_reported_by_owner(self):
        self.seed()
        self.materialize()
        store = self.require_peer("lineage.domain.memory.store")
        # A-U12: use U10's folded snapshot and Context for all U11 owner calls.
        snapshot = self.memory_snapshot()
        memory_ctx = self.memory_context()
        paths = store.rebuild("agent-one", snapshot=snapshot, ctx=memory_ctx)
        before = {p.relative_to(self.home).as_posix(): p.read_bytes() for p in paths if p.is_file()}
        self.assertTrue(before, "no memory projection witness")
        victim = next(p for p in paths if p.is_file())
        victim.unlink()
        self.assertTrue(store.verify_projection("agent-one", snapshot=snapshot, ctx=memory_ctx))
        store.rebuild("agent-one", snapshot=snapshot, ctx=memory_ctx)
        self.assertEqual({p.relative_to(self.home).as_posix(): p.read_bytes() for p in paths if p.is_file()}, before)

    def test_a37_stale_snapshot_cannot_replace_a_newer_projection(self):
        self.seed()
        old = journal.snapshot(self.home)
        self.materialize()
        self.append_fixture("memory.put", {"agent_id": "agent-one", "unit": unit()})
        self.materialize()
        before = self.inventory()
        try:
            self.invoke(agents.materialize, "agent-one", snapshot=old, ctx=self.ctx)
        except LineageError as exc:
            self.assertEqual(exc.code, "internal")
        self.assertEqual(self.inventory(), before)

    def test_a36_adversarial_swap_at_write_or_publication_is_refused(self):
        import io
        import os
        self.seed()
        self.materialize()
        directory = self.projection_dir()
        moved = directory.with_name("before-swap")
        outside = self.root / "outside"
        outside.mkdir()
        protected = outside / "protected.txt"
        protected.write_bytes(b"protected")
        fired = []
        names = {"agent.json", "CONSTITUTION.md", "BRIEF_HEAD.md"}
        real_open, real_io_open = os.open, io.open
        real_replace, real_rename = os.replace, os.rename
        def swap(path):
            if fired or isinstance(path, int) or Path(path).name not in names:
                return
            fired.append(True)
            real_rename(directory, moved)
            directory.symlink_to(outside, target_is_directory=True)
        def descriptor_open(path, flags, *args, **kwargs):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                swap(path)
            return real_open(path, flags, *args, **kwargs)
        def stream_open(path, mode="r", *args, **kwargs):
            if any(flag in mode for flag in "wax+"):
                swap(path)
            return real_io_open(path, mode, *args, **kwargs)
        def replace(source, destination, *args, **kwargs):
            swap(destination)
            return real_replace(source, destination, *args, **kwargs)
        def rename(source, destination, *args, **kwargs):
            swap(destination)
            return real_rename(source, destination, *args, **kwargs)
        with mock.patch("os.open", side_effect=descriptor_open), \
             mock.patch("io.open", side_effect=stream_open), \
             mock.patch("os.replace", side_effect=replace), \
             mock.patch("os.rename", side_effect=rename):
            with self.assertRaises(LineageError) as raised:
                self.invoke(agents.materialize, "agent-one", snapshot=journal.snapshot(self.home), ctx=self.ctx)
        self.assertEqual(raised.exception.code, "internal")
        self.assertTrue(fired, "BLOCKED/HOLD: publication interleaving was not exercised")
        self.assertEqual({p.name: p.read_bytes() for p in outside.iterdir()}, {"protected.txt": b"protected"})
