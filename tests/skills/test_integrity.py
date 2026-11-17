"""Direct journal admission, projection integrity, and durable recovery."""
import copy
from contextlib import ExitStack
import errno
import hashlib
import io
import os
from pathlib import Path
import shutil
from unittest import mock

from tests.skills import (FILES, PIN, RuntimeCase, boundary_files, disk_image,
                          independent_pin, one, refusal_witness, skills)


class IntegrityOracle(RuntimeCase):
    def new_home(self, name):
        self.home = self.base / name
        self.home.mkdir()
        self.ctx = self.context(self.home, tag=name)

    def make_link(self, component):
        destination = self.projection()
        path = {"root": self.home / "skills", "id": destination.parent,
                "hash": destination, "parent": destination / "docs",
                "leaf": destination / "SKILL.md"}[component]
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()
        outside = self.base / (self.home.name + "-sentinel")
        outside.mkdir()
        (outside / "sentinel.txt").write_text("sentinel bytes", encoding="utf-8")
        if component == "leaf":
            path.symlink_to(outside / "sentinel.txt")
        else:
            path.symlink_to(outside, target_is_directory=True)
        return outside

    def test_a07_new_publish_refuses_each_symlink_before_transaction(self):
        for component in ("root", "id", "hash", "parent", "leaf"):
            with self.subTest(component=component):
                self.new_home("unsafe-" + component)
                outside = self.make_link(component)
                before = disk_image(outside)
                original_transact = self.journal.transact
                def forbidden(*args, **kwargs):
                    self.fail("unsafe projection was admitted to journal.transact")
                with ExitStack() as stack:
                    for name, value in list(vars(skills).items()):
                        if value is original_transact:
                            stack.enter_context(mock.patch.object(skills, name, side_effect=forbidden))
                    stack.enter_context(mock.patch.object(self.journal, "transact", side_effect=forbidden))
                    self.assert_code("bad_args", lambda: self.publish())
                self.assertEqual(self.raw(), b"")
                self.assertEqual(disk_image(outside), before)

    def test_a07_existing_lookup_refuses_each_symlink(self):
        for component in ("root", "id", "hash", "parent", "leaf"):
            with self.subTest(component=component):
                self.new_home("lookup-" + component)
                self.publish()
                outside = self.make_link(component)
                before = disk_image(self.home)
                sentinel = disk_image(outside)
                self.assert_code("bad_args", lambda: skills.get("sample", sha256=PIN, ctx=self.ctx))
                self.assertEqual(disk_image(self.home), before)
                self.assertEqual(disk_image(outside), sentinel)

    def test_a07_symlink_above_runtime_skills_is_allowed(self):
        alias = self.base / "home-alias"
        alias.symlink_to(self.home, target_is_directory=True)
        ctx = self.context(alias, tag="alias")
        result = self.publish(ctx=ctx)
        self.assertEqual(skills.get("sample", ctx=ctx)["skill"], result.value["skill"])
        self.assert_projection()

    def test_a05_a06_rejected_packages_append_nothing(self):
        invalid = [[], [{"path": "nested/SKILL.md", "content": ""}],
                   one() + one("duplicate"),
                   one() + [{"path": "a", "content": ""}, {"path": "a/b", "content": ""}],
                   one() + [{"path": "a//b", "content": ""}],
                   one() + [{"path": "a/b/", "content": ""}],
                   one() + [{"path": "../outside", "content": ""}]]
        sentinel = self.base / "outside"
        sentinel.write_text("unchanged")
        for files in invalid:
            with self.subTest(files=files):
                self.assert_code("bad_args", lambda: self.publish(files))
                self.assertFalse((self.home / "skills").exists())
        self.assertEqual(sentinel.read_text(), "unchanged")

    def test_a08_rejected_publication_bounds_have_no_event(self):
        invalid = [one("é" * 65537),
                   one() + [{"path": "file-%03d" % i, "content": ""} for i in range(256)],
                   boundary_files(1048577)]
        for files in invalid:
            with self.subTest(count=len(files)):
                self.assert_code("bad_args", lambda: self.publish(files))
        self.assertEqual(self.raw(), b"")

    def direct_append(self, kind, payload):
        # A-U09: transact is the integrated public append seam; registered validators run unchanged.
        event = self.journal.transact(self.ctx.home, agent=self.ctx.actor,
            op_id="direct-" + str(next(self._serial)), kind=kind,
            payload=copy.deepcopy(payload), validators=self.ctx.validators)
        commit = {"event_ids": [event["id"]], "head": event["lamport"], "sha256": event["sha256"]}
        if kind == "skill.published":
            value = {"skill": {"skill_id": payload["skill_id"], "sha256": payload["sha256"],
                     "retired": False, "files": copy.deepcopy(payload["files"])}, "commit": commit}
        else:
            value = {"skill_id": payload["skill_id"], "sha256": payload["sha256"],
                     "retired": True, "commit": commit}
        from types import SimpleNamespace
        return SimpleNamespace(event=event, value=value, head=event["lamport"], sha256=event["sha256"])

    def test_a19_direct_append_cannot_bypass_publication_checks(self):
        correct = {"skill_id": "sample", "sha256": PIN, "files": sorted(FILES, key=lambda f: f["path"])}
        variants = [
            ({**correct, "sha256": "0" * 64}, "hash_mismatch"),
            ({**correct, "files": list(reversed(correct["files"]))}, "bad_args"),
            ({**correct, "skill_id": "A"}, "bad_args"),
            ({**correct, "sha256": "F" * 64}, "bad_args"),
            ({**correct, "extra": True}, "bad_args"),
        ]
        invalid_files = [one() + one("duplicate"),
                         one() + [{"path": "../escape", "content": ""}],
                         [{"path": "not-entry", "content": ""}],
                         one() + [{"path": "a", "content": ""}, {"path": "a/b", "content": ""}],
                         one() + [{"path": "f%03d" % i, "content": ""} for i in range(256)],
                         one("a" * 65537), boundary_files(1048577),
                         [{"path": "SKILL.md", "content": "", "extra": True}],
                         one() + [{"path": "nested/SKILL.md", "content": ""}],
                         one() + [{"path": "a//b", "content": ""}]]
        for files in invalid_files:
            variants.append(({"skill_id": "sample", "sha256": independent_pin(files), "files": files}, "bad_args"))
        for payload, code in variants:
            with self.subTest(keys=list(payload), code=code):
                refusal_witness(self, self.LineageError, lambda: self.direct_append("skill.published", payload), self.raw, code)
        result = self.direct_append("skill.published", correct)
        self.assert_receipt(result)
        self.assertEqual(skills.get("sample", ctx=self.ctx)["skill"]["sha256"], PIN)

    def test_a19_direct_append_retirement_schema_and_existence(self):
        payload = {"skill_id": "sample", "sha256": PIN}
        self.assert_code("bad_args", lambda: self.direct_append("skill.retired", payload))
        self.publish()
        for extra in ({"reason": "forbidden"}, {"retired": True}, {"extra": 0}):
            with self.subTest(extra=extra):
                self.assert_code("bad_args", lambda: self.direct_append("skill.retired", {**payload, **extra}))
        self.assert_receipt(self.direct_append("skill.retired", payload))
        self.assertTrue(skills.get("sample", sha256=PIN, ctx=self.ctx)["skill"]["retired"])

    def test_a20_tampered_projection_is_not_repaired_by_get_or_replay(self):
        for variant in ("changed", "missing", "extra", "nondirectory"):
            with self.subTest(variant=variant):
                self.new_home("tamper-" + variant)
                original = self.publish(op="original")
                path = self.projection()
                if variant == "changed":
                    (path / "SKILL.md").write_text("tampered")
                elif variant == "missing":
                    (path / "SKILL.md").unlink()
                elif variant == "extra":
                    (path / "extra.txt").write_text("unexpected")
                else:
                    shutil.rmtree(path)
                    path.write_text("not a directory")
                before = disk_image(self.home)
                expected = {"skills": [{"skill_id": "sample", "sha256": PIN, "retired": False}]}
                self.assertEqual(skills.list_skills(ctx=self.ctx), expected)
                self.assert_code("hash_mismatch", lambda: skills.get("sample", sha256=PIN, ctx=self.ctx))
                self.assert_error_wire(self.dispatch("skill_get", {"skill_id": "sample", "sha256": PIN}), "hash_mismatch")
                self.assert_code("hash_mismatch", lambda: self.publish(op="original"))
                self.assertEqual(disk_image(self.home), before)
                self.assertEqual(len(self.events()), 1)
                self.assertFalse(original.value["skill"]["retired"])

    def test_a20_new_operation_does_not_overwrite_existing_corrupt_pin(self):
        self.publish()
        (self.projection() / "SKILL.md").write_text("tampered")
        before = disk_image(self.home)
        self.assert_code("hash_mismatch", lambda: self.publish(op="new-identity"))
        self.assertEqual(disk_image(self.home), before)

    def test_a21_absent_projection_reads_are_pure_retry_rebuilds_original(self):
        original = self.publish(op="original")
        before_files = disk_image(self.projection())
        shutil.rmtree(self.projection())
        before = disk_image(self.home)
        self.assertEqual(skills.get("sample", sha256=PIN, ctx=self.ctx), {"skill": original.value["skill"]})
        self.assertEqual(skills.list_skills(ctx=self.ctx), {"skills": [{"skill_id": "sample", "sha256": PIN, "retired": False}]})
        self.assertEqual(disk_image(self.home), before)
        ledger = self.raw()
        replay = self.publish(op="original", expected=0)
        self.assertEqual(replay.value, original.value)
        self.assertEqual(replay.event, original.event)
        self.assertEqual(self.raw(), ledger)
        self.assertEqual(disk_image(self.projection()), before_files)
        self.assert_projection()

    def test_a16_corrupt_or_unreadable_ledger_never_lists_as_empty(self):
        self.publish()
        path = self.home / "ledger/main/events.jsonl"
        path.write_bytes(self.raw().replace(b'"skill_id":"sample"', b'"skill_id":"broken"', 1))
        self.assert_code("internal", lambda: skills.list_skills(ctx=self.ctx))
        self.assert_error_wire(self.dispatch("skill_list", {}), "internal")
        # A directory in place of the history is unreadable as JSONL, even as root.
        path.unlink()
        path.mkdir()
        self.assert_code("internal", lambda: skills.list_skills(ctx=self.ctx), unchanged=False)

    def test_a24_corrupt_history_blocks_mutation_without_projection(self):
        self.publish()
        path = self.home / "ledger/main/events.jsonl"
        path.write_bytes(self.raw().replace(b'"skill_id":"sample"', b'"skill_id":"broken"', 1))
        target = self.projection(independent_pin(one("new")))
        before = self.raw()
        with self.assertRaises(self.LineageError) as caught:
            self.publish(one("new"))
        self.assertIn(caught.exception.code, {"hash_mismatch", "internal"})
        self.assertEqual(self.raw(), before)
        self.assertFalse(target.exists())

    def test_a25_postcommit_io_failure_has_no_partial_final_and_exact_recovery(self):
        originals = {"os.open": os.open, "builtins.open": open, "io.open": io.open}
        failures = []
        attempted_writes = []
        def guard(original, *args, **kwargs):
            if self.raw():
                mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
                if original is originals["os.open"]:
                    flags = kwargs.get("flags", args[1] if len(args) > 1 else 0)
                    writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
                else:
                    writing = isinstance(mode, str) and any(c in mode for c in "wax+")
                candidate = args[0] if args else kwargs.get("file", "")
                text = os.fsdecode(candidate) if isinstance(candidate, (str, bytes, os.PathLike)) else ""
                projection = ("skills" in Path(text).parts or "SKILL.md" in text or
                              "note.txt" in text or kwargs.get("dir_fd") is not None)
                if writing and projection:
                    attempted_writes.append(text)
                    # Let an earlier package entry be created before the fault.
                    # An in-place implementation must therefore expose a partial final.
                    if len(attempted_writes) == 2:
                        failures.append(True)
                        raise OSError(errno.EIO, "injected projection file-write failure")
            return original(*args, **kwargs)
        # Inspect history with an unpatched primitive, avoiding recursion in guards.
        original_raw = self.raw
        history_path = self.home / "ledger/main/events.jsonl"
        def raw_unpatched():
            try:
                with originals["builtins.open"](history_path, "rb") as stream:
                    return stream.read()
            except FileNotFoundError:
                return b""
        self.raw = raw_unpatched
        with ExitStack() as stack:
            for target, original in originals.items():
                stack.enter_context(mock.patch(target, side_effect=lambda *a, _fn=original, **k: guard(_fn, *a, **k)))
            self.assert_code("internal", lambda: self.publish(op="recover"), unchanged=False)
        self.raw = original_raw
        self.assertTrue(failures, "fault must actually reach post-commit projection I/O")
        self.assertEqual(len(attempted_writes), 2)
        self.assertEqual(len(self.events()), 1)
        self.assertFalse(self.projection().exists())
        event = self.events()[0]
        before = self.raw()
        replay = self.publish(op="recover")
        self.assertEqual(self.raw(), before)
        self.assertEqual(replay.event, event)
        self.assertEqual(replay.value["commit"], {"event_ids": [event["id"]], "head": event["lamport"], "sha256": event["sha256"]})
        self.assert_projection()
        self.assert_receipt(replay)


    def collision_case(self, collision_errno, corrupt=False):
        import stat
        original_rename, original_replace = os.rename, os.replace
        collided = []
        def copy_fd(source_fd, target_fd):
            for name in os.listdir(source_fd):
                info = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    os.mkdir(name, dir_fd=target_fd)
                    child_source = os.open(name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=source_fd)
                    child_target = os.open(name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=target_fd)
                    try:
                        copy_fd(child_source, child_target)
                        os.fsync(child_target)
                    finally:
                        os.close(child_source)
                        os.close(child_target)
                else:
                    self.assertTrue(stat.S_ISREG(info.st_mode))
                    reader = os.open(name, os.O_RDONLY, dir_fd=source_fd)
                    writer = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=target_fd)
                    try:
                        while True:
                            data = os.read(reader, 65536)
                            if not data:
                                break
                            position = 0
                            while position < len(data):
                                position += os.write(writer, data[position:])
                        os.fsync(writer)
                    finally:
                        os.close(reader)
                        os.close(writer)
        def placement(original, source, destination, *args, **kwargs):
            if not collided and Path(os.fsdecode(destination)).name == PIN:
                source_fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY,
                                    dir_fd=kwargs.get("src_dir_fd"))
                try:
                    os.mkdir(destination, dir_fd=kwargs.get("dst_dir_fd"))
                    target_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY,
                                        dir_fd=kwargs.get("dst_dir_fd"))
                    try:
                        copy_fd(source_fd, target_fd)
                        if corrupt:
                            writer = os.open("SKILL.md", os.O_WRONLY | os.O_TRUNC, dir_fd=target_fd)
                            try:
                                os.write(writer, b"tampered")
                                os.fsync(writer)
                            finally:
                                os.close(writer)
                        os.fsync(target_fd)
                    finally:
                        os.close(target_fd)
                finally:
                    os.close(source_fd)
                collided.append(True)
                raise OSError(collision_errno, "injected simultaneous destination publication")
            return original(source, destination, *args, **kwargs)
        with ExitStack() as stack:
            for name, value in list(vars(skills).items()):
                if value is original_rename or value is original_replace:
                    stack.enter_context(mock.patch.object(skills, name,
                        side_effect=lambda *a, _fn=value, **k: placement(_fn, *a, **k)))
            stack.enter_context(mock.patch("os.rename", side_effect=lambda *a, **k: placement(original_rename, *a, **k)))
            stack.enter_context(mock.patch("os.replace", side_effect=lambda *a, **k: placement(original_replace, *a, **k)))
            if corrupt:
                self.assert_code("hash_mismatch", lambda: self.publish(), unchanged=False)
            else:
                result = self.publish()
        self.assertTrue(collided, "immutable final placement must use atomic rename")
        if corrupt:
            self.assertEqual((self.projection() / "SKILL.md").read_bytes(), b"tampered")
        else:
            self.assert_receipt(result)
            self.assert_projection()
        self.assertEqual(len(self.events()), 1)

    def test_a23_atomic_placement_eexist_verifies_identical_destination(self):
        self.collision_case(errno.EEXIST)

    def test_a23_atomic_placement_enotempty_verifies_identical_destination(self):
        self.collision_case(errno.ENOTEMPTY)


    def test_a23_collision_with_changed_destination_refuses_without_overwrite(self):
        self.collision_case(errno.EEXIST, corrupt=True)

    def test_a19_registered_validator_is_pure_and_cannot_dispatch_or_write(self):
        import importlib
        # A-U09: validators receive history/event; snapshot is an immutable detached tuple.
        before = self.journal.snapshot(self.ctx.home)
        original_state = copy.deepcopy(before)
        committed = self.publish()
        validator = importlib.import_module("lineage.ext.skills").VALIDATORS["skill.published"]
        image = disk_image(self.home)
        event = copy.deepcopy(committed.event)
        frozen_event = copy.deepcopy(event)
        original_open, original_io_open, original_os_open = open, io.open, os.open
        def mode_guard(original, *args, **kwargs):
            mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
            if isinstance(mode, str) and any(c in mode for c in "wax+"):
                self.fail("registered validator attempted a file write")
            return original(*args, **kwargs)
        def fd_guard(*args, **kwargs):
            flags = kwargs.get("flags", args[1] if len(args) > 1 else 0)
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                self.fail("registered validator attempted a descriptor write")
            return original_os_open(*args, **kwargs)
        def forbidden(*args, **kwargs):
            self.fail("registered validator attempted mutation, dispatch or execution")
        with ExitStack() as stack:
            stack.enter_context(mock.patch("builtins.open", side_effect=lambda *a, **k: mode_guard(original_open, *a, **k)))
            stack.enter_context(mock.patch("io.open", side_effect=lambda *a, **k: mode_guard(original_io_open, *a, **k)))
            stack.enter_context(mock.patch("os.open", side_effect=fd_guard))
            for target in ("os.mkdir", "os.rename", "os.replace", "os.unlink", "os.remove", "os.write", "subprocess.Popen", "os.system"):
                stack.enter_context(mock.patch(target, side_effect=forbidden))
            for module, name in ((self.journal, "transact"), (self.app, "dispatch")):
                original = getattr(module, name)
                for alias, value in list(vars(skills).items()):
                    if value is original:
                        stack.enter_context(mock.patch.object(skills, alias, side_effect=forbidden))
                stack.enter_context(mock.patch.object(module, name, side_effect=forbidden))
            self.assertIsNone(validator(before, event))
            forged = copy.deepcopy(event)
            forged["payload"]["sha256"] = "0" * 64
            with self.assertRaises(self.LineageError) as caught:
                validator(before, forged)
            self.assertEqual(caught.exception.code, "hash_mismatch")
        self.assertEqual(event, frozen_event)
        self.assertEqual(before, original_state)
        self.assertEqual(disk_image(self.home), image)
