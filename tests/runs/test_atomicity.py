"""Bounded process coordination and the actual journal's fault-injection seams."""
from contextlib import ExitStack
from copy import deepcopy
import multiprocessing
import os
import socket
import subprocess
from unittest import mock

from lineage.core import app, journal
from lineage.domain import gate_close, runs
from tests.runs.support import (RunCase, OWNER, RUN, OUTCOME, COST,
    child_operation, lock_child, owned_process, canonical)


class Atomicity(RunCase):
    def command(self, label):
        return self.f.command('run_close', {'run_id': RUN, 'outcome': OUTCOME, 'cost': COST},
                              op_id=label)

    def ready(self):
        self.f.open()
        self.f.witness()

    def receive(self, connection):
        self.assertTrue(connection.poll(1.5), 'child did not answer within bounded deadline')
        value = connection.recv()
        if value[:2] == ('error', 'NotImplementedError'):
            raise NotImplementedError('U13 stub')
        return value

    def ordered(self, first, second):
        ctx = multiprocessing.get_context('fork')
        signals = [ctx.Event(), ctx.Event()]
        pipes = [ctx.Pipe(duplex=False), ctx.Pipe(duplex=False)]
        commands = [self.command('first001'), self.command('second01')]
        with ExitStack() as stack:
            children = []
            for index, operation in enumerate((first, second)):
                parent, child = pipes[index]
                self.addCleanup(parent.close)
                children.append(stack.enter_context(owned_process(child_operation,
                    (self.f.home, operation, commands[index], signals[index], child))))
                child.close()
            signals[0].set()
            result_first = self.receive(pipes[0][0])
            signals[1].set()
            result_second = self.receive(pipes[1][0])
            for child in children:
                child.join(0.5)
                self.assertEqual(child.exitcode, 0)
        return result_first, result_second

    def test_a29_retirement_first_refuses_close(self):
        self.ready()
        first, second = self.ordered('retire', 'close')
        self.assertEqual(first[0], 'ok')
        self.assertEqual(second[:2], ('error', 'conflict'))
        self.assertIsNone(runs.get(RUN, ctx=self.f.context())['closed'])

    def test_a29_close_first_can_commit_before_retirement(self):
        self.ready()
        first, second = self.ordered('close', 'retire')
        self.assertEqual((first[0], second[0]), ('ok', 'ok'))
        self.assertIsNotNone(runs.get(RUN, ctx=self.f.context())['closed'])
        kinds = [event['kind'] for event in self.f.events()]
        self.assertLess(kinds.index('run.close'), kinds.index('agent.status'))

    def test_a30_witness_retirement_first_refuses_close(self):
        self.ready()
        first, second = self.ordered('memory_retire', 'close')
        self.assertEqual(first[0], 'ok')
        self.assertEqual(second[:2], ('error', 'memory_debt'))
        self.assertIsNone(runs.get(RUN, ctx=self.f.context())['closed'])

    def test_a30_close_first_preserves_historical_memory_receipt(self):
        self.ready()
        first, second = self.ordered('close', 'memory_retire')
        self.assertEqual((first[0], second[0]), ('ok', 'ok'))
        self.assertEqual(runs.get(RUN, ctx=self.f.context())['closed'], first[1]['run'])
        before = self.f.raw()
        self.assertEqual(self.f.close(command=self.command('first001')).value, first[1])
        self.assertEqual(self.f.raw(), before)

    def test_a30_replacement_must_have_its_own_run_binding(self):
        self.ready()
        successor = self.f.unit(identifier='successor', run_id='other001')
        successor['supersedes'] = ['episode1']
        self.f.put(successor, run_id='other001')
        self.refusal('memory_debt', self.f.close)
        self.f.put(self.f.unit(identifier='episode2'))
        record = self.closed(self.f.close())
        self.assertEqual(record['memory']['unit_ids'], ['episode2'])

    def concurrent(self, identical):
        self.ready()
        ctx = multiprocessing.get_context('fork')
        start = ctx.Event()
        pipes = [ctx.Pipe(duplex=False) for _ in range(2)]
        with ExitStack() as stack:
            processes = []
            for index, (parent, child) in enumerate(pipes):
                self.addCleanup(parent.close)
                command = self.command('same0001' if identical else f'close00{index}')
                processes.append(stack.enter_context(owned_process(child_operation,
                    (self.f.home, 'close', command, start, child))))
                child.close()
            start.set()
            results = [self.receive(parent) for parent, _ in pipes]
            for process in processes:
                process.join(0.5)
                self.assertEqual(process.exitcode, 0)
        self.assertEqual(len([e for e in self.f.events() if e['kind'] == 'run.close']), 1)
        self.assertTrue(journal.verify(self.f.home)['ok'])
        return results

    def test_a31_identical_concurrent_closes_replay(self):
        first, second = self.concurrent(True)
        self.assertEqual(first[0], 'ok')
        self.assertEqual(first, second)

    def test_a31_distinct_concurrent_closes_have_one_winner(self):
        results = self.concurrent(False)
        self.assertEqual(sorted(value[0] for value in results), ['error', 'ok'])
        self.assertEqual(next(r for r in results if r[0] == 'error')[1], 'run_closed')

    def test_a33_real_lock_refusal_and_release(self):
        self.ready()
        ctx = multiprocessing.get_context('fork')
        ready, release = ctx.Event(), ctx.Event()
        with owned_process(lock_child, (self.f.home, ready, release)) as process:
            try:
                self.assertTrue(ready.wait(1.0), 'lock holder was not ready')
                before = self.f.raw()
                with self.assertRaises(Exception) as caught:
                    self.f.close()
                self.assertEqual(caught.exception.code, 'busy')
                self.assertEqual(self.f.raw(), before)
            finally:
                release.set()
            process.join(0.5)
            self.assertEqual(process.exitcode, 0)
        self.closed(self.f.close())

    def test_a34_gate_exception_is_internal_without_append(self):
        self.ready()
        with mock.patch.object(gate_close, 'check', side_effect=RuntimeError('oracle gate fault')):
            self.refusal('internal', self.f.close)
        self.closed(self.f.close())

    def test_a34_commit_write_failure_rolls_back(self):
        self.ready()
        before = self.f.raw()
        original_write = journal._write_all
        attempts = []
        def fail_once(fd, data):
            if not attempts:
                attempts.append(fd)
                raise OSError('oracle write fault')
            return original_write(fd, data)
        with mock.patch.object(journal, '_write_all', side_effect=fail_once):
            self.refusal('internal', self.f.close)
        self.assertEqual(self.f.raw(), before)
        self.assertTrue(journal.verify(self.f.home)['ok'])
        self.closed(self.f.close())

    def test_a34_fsync_failure_rolls_back(self):
        self.ready()
        real_fsync = os.fsync
        seen = []
        def fail_once(fd):
            if not seen:
                seen.append(fd)
                raise OSError('oracle fsync fault')
            return real_fsync(fd)
        with mock.patch('lineage.core.journal.os.fsync', side_effect=fail_once):
            self.refusal('internal', self.f.close)
        self.assertTrue(seen)
        self.closed(self.f.close())

    def test_a39_callbacks_do_not_dispatch_network_or_spawn(self):
        self.ready()
        def forbidden(*args, **kwargs):
            raise AssertionError('forbidden operation in locked callback')
        original_callback = journal._callback
        real_open = os.open
        import builtins
        import io
        real_builtin_open, real_io_open = builtins.open, io.open
        def readonly_os_open(path, flags, *args, **kwargs):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                forbidden()
            return real_open(path, flags, *args, **kwargs)
        def readonly_builtin(path, mode='r', *args, **kwargs):
            if any(letter in mode for letter in 'wax+'):
                forbidden()
            return real_builtin_open(path, mode, *args, **kwargs)
        def readonly_io(path, mode='r', *args, **kwargs):
            if any(letter in mode for letter in 'wax+'):
                forbidden()
            return real_io_open(path, mode, *args, **kwargs)
        observations = []
        def confined(callback, history, event):
            observations.append(event['kind'])
            with mock.patch.object(app, 'dispatch', forbidden), \
                 mock.patch.object(subprocess, 'Popen', forbidden), \
                 mock.patch.object(socket, 'socket', forbidden), \
                 mock.patch.object(journal, 'transact', forbidden), \
                 mock.patch('os.open', side_effect=readonly_os_open), \
                 mock.patch('builtins.open', side_effect=readonly_builtin), \
                 mock.patch('io.open', side_effect=readonly_io):
                return original_callback(callback, history, event)
        before = self.f.snapshot().state
        with mock.patch.object(journal, '_callback', side_effect=confined):
            self.closed(self.f.close())
        self.assertIn('run.close', observations)
        after = self.f.snapshot().state
        for namespace in before.keys() - {'runs'}:
            self.assertEqual(after[namespace], before[namespace])


def durable_memory_child(home, connection, release):
    from tests.runs.support import Fixture
    fixture = Fixture(home, seed=False)
    try:
        fixture.witness()
        connection.send('memory-durable')
        if not release.wait(1.5):
            raise AssertionError('parent did not end the controlled task')
    finally:
        connection.close()


class CrashBoundary(RunCase):
    def test_a32_owned_task_ends_after_durable_memory_before_close(self):
        self.f.open()
        ctx = multiprocessing.get_context('fork')
        parent, child = ctx.Pipe(duplex=False)
        self.addCleanup(parent.close)
        release = ctx.Event()
        with owned_process(durable_memory_child, (self.f.home, child, release)) as process:
            child.close()
            self.assertTrue(parent.poll(1.0), 'no durable-memory acknowledgement')
            self.assertEqual(parent.recv(), 'memory-durable')
            self.assertIsNotNone(process.pid)
            self.assertGreater(process.pid, 1)
            # Exact PID belongs to this Process, created above; no group signal exists.
            process.terminate()
            process.join(0.5)
            self.assertFalse(process.is_alive())
        self.assertIsNone(runs.get(RUN, ctx=self.f.context())['closed'])
        self.closed(self.f.close())

    def test_a34_result_validation_failure_precedes_durability(self):
        from contextlib import ExitStack
        from lineage.core import schema
        self.f.open()
        self.f.witness()
        original = schema.validate
        observed = []
        def fail_result(value, spec, *args, **kwargs):
            if type(value) is dict and set(value) == {'run', 'commit'}:
                observed.append(True)
                raise RuntimeError('oracle result rendering fault')
            return original(value, spec, *args, **kwargs)
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(schema, 'validate', fail_result))
            for name, value in vars(runs).items():
                if value is original:
                    stack.enter_context(mock.patch.object(runs, name, fail_result))
            self.refusal('internal', self.f.close)
        self.assertTrue(observed, 'rendered result was not validated through U02')
        self.closed(self.f.close())

    def test_a34_failed_rollback_blocks_mutation_until_verified_recovery(self):
        self.f.open()
        self.f.witness()
        original = self.f.raw()
        def partial_write(fd, data):
            os.write(fd, b'corrupt\n')
            raise OSError('oracle partial append')
        with mock.patch.object(journal, '_write_all', side_effect=partial_write), \
             mock.patch('lineage.core.journal.os.ftruncate', side_effect=OSError('oracle rollback fault')):
            with self.assertRaises(Exception) as caught:
                self.f.close()
        self.assertEqual(caught.exception.code, 'internal')
        self.assertFalse(journal.verify(self.f.home)['ok'])
        self.refusal('hash_mismatch', self.f.close)
        (self.f.home / 'ledger/main/events.jsonl').write_bytes(original)
        self.assertTrue(journal.verify(self.f.home)['ok'])
        self.closed(self.f.close())
