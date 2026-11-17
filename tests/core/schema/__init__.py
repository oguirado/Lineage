"""Shared public-contract assertions for the U02 oracle."""

from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
import builtins
import io
import os
import socket
import subprocess
from unittest.mock import patch

from lineage.core import schema as boundary


class OracleMixin:
    def reject(self, function, *args, reason, pointer="", schema_pointer=None):
        with self.assertRaises(boundary.SchemaError) as caught:
            function(*args)
        error = caught.exception
        self.assertEqual(error.code, "bad_args")
        self.assertEqual(error.reason, reason)
        self.assertEqual(error.pointer, pointer)
        self.assertEqual(error.schema_pointer, schema_pointer)
        self.assertEqual(str(error), "bad_args:" + reason)
        return error

    def raw_error(self, raw, reason):
        return self.reject(boundary.strict_loads, raw, reason=reason)

    def value_error(self, value, schema, reason, pointer=""):
        return self.reject(boundary.validate, value, schema,
                           reason=reason, pointer=pointer)

    def schema_error(self, schema, pointer, reason="invalid_schema", value=None):
        return self.reject(boundary.validate, value, schema, reason=reason,
                           schema_pointer=pointer)

    def accept(self, value, schema):
        self.assertIsNone(boundary.validate(value, schema))

    def one_of_errors(self, function, *args, reasons, pointers=("",),
                      schema_pointers=(None,)):
        """Only for alternatives explicitly left unresolved by Amendment B."""
        with self.assertRaises(boundary.SchemaError) as caught:
            function(*args)
        error = caught.exception
        self.assertEqual(error.code, "bad_args")
        self.assertIn(error.reason, reasons)
        self.assertIn(error.pointer, pointers)
        self.assertIn(error.schema_pointer, schema_pointers)
        self.assertEqual(str(error), "bad_args:" + error.reason)
        return error


def nested_array(depth, leaf=0):
    value = leaf
    for _ in range(depth):
        value = [value]
    return value


def container_ids(value):
    result = []
    if type(value) is dict:
        result.append(id(value))
        for name in sorted(value):
            result.extend(container_ids(value[name]))
    elif type(value) is list:
        result.append(id(value))
        for item in value:
            result.extend(container_ids(item))
    return result


@contextmanager
def no_application_io():
    """Source/stdlib imports use importlib; application I/O must stay absent."""
    output, errors = io.StringIO(), io.StringIO()
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        caller = (globals or {}).get("__name__", "")
        if caller == "lineage.core.schema" and (
            level or name == "lineage" or name.startswith(("lineage.", "_seed"))
        ):
            raise AssertionError("schema imported an application dependency")
        return original_import(name, globals, locals, fromlist, level)

    with ExitStack() as stack:
        stack.enter_context(patch.object(builtins, "__import__", guarded_import))
        for owner, name in (
            (builtins, "open"), (builtins, "input"), (io, "open"),
            (os, "open"), (os, "getenv"), (os, "listdir"), (os, "scandir"),
            (os, "mkdir"), (os, "makedirs"), (os, "unlink"), (os, "remove"),
            (os, "rename"), (os, "replace"), (os, "system"),
            (socket, "socket"), (socket, "getaddrinfo"),
            (socket, "create_connection"), (subprocess, "Popen"),
            (type(os.environ), "__getitem__"),
            (type(os.environ), "__setitem__"),
        ):
            stack.enter_context(patch.object(
                owner, name, side_effect=AssertionError("application I/O attempted")))
        stack.enter_context(redirect_stdout(output))
        stack.enter_context(redirect_stderr(errors))
        yield output, errors
