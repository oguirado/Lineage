# A-U01R: A-FLK1 permits only the immediate genuine stdlib caller to sleep.
import selectors
import subprocess
import threading
import time
from types import FunctionType
import unittest
from unittest import mock

from lineage.core import app
from . import _support
from ._support import _sleep_guard, registry


def compiled_function(source, globals):
    code = compile(source, "<sleep-guard-control>", "exec")
    function = next(item for item in code.co_consts if hasattr(item, "co_code"))
    return FunctionType(function, globals)


class SleepGuardRegression(unittest.TestCase):
    def test_direct_product_sleep_is_refused(self):
        with mock.patch.object(time, "sleep", _sleep_guard()):
            with self.assertRaisesRegex(AssertionError, "real sleep forbidden"):
                time.sleep(0.01)

    def test_immediate_stdlib_callers_may_sleep(self):
        for module in (subprocess, threading, selectors):
            with self.subTest(module=module.__name__):
                caller = compiled_function("def invoke(sleep): sleep(0.01)", vars(module))
                with mock.patch.object(_support, "_REAL_SLEEP") as real:
                    caller(_sleep_guard())
                real.assert_called_once_with(0.01)

    def test_spoofed_stdlib_module_name_does_not_pass(self):
        caller = compiled_function("def invoke(sleep): sleep(0.01)", {"__name__":"subprocess"})
        with self.assertRaisesRegex(AssertionError, "real sleep forbidden"):
            caller(_sleep_guard())

    def test_stdlib_ancestor_does_not_exempt_product_callback(self):
        caller = compiled_function("def invoke(callback): callback()", vars(subprocess))
        with mock.patch.object(time, "sleep", _sleep_guard()):
            with self.assertRaisesRegex(AssertionError, "real sleep forbidden"):
                caller(lambda: time.sleep(0.01))

    def test_injected_product_handler_sleep_fails_dispatch(self):
        def product(args, *, context):
            time.sleep(0.01)
            return {"ok":True}
        installed = registry(product)
        context = app.create_context(registry=installed)
        with mock.patch.object(time, "sleep", _sleep_guard()):
            with self.assertRaisesRegex(AssertionError, "real sleep forbidden"):
                product({}, context=context)
            result = app.dispatch("regression_echo", {}, context=context, registry=installed)
        self.assertEqual(result.exit_code, 3)
        self.assertEqual(result.payload, {"ok":False,"code":"internal"})
