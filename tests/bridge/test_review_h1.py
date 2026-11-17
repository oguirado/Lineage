"""Repair h1 regressions: integrated registry and recipient admission."""
# A-U20: add discriminating coverage without changing frozen assertions.
from contextlib import ExitStack
import io
import json
import os
import stat
from unittest import mock

from lineage.core import app, cli, jsonlane, registry as extensions
from tests.bridge._support import (BridgeCase, canonical, call_envelope,
                                   client_double, contract_schema, image)


class RepairH1Oracle(BridgeCase):
    def test_review_h1_full_registry_retains_exact_bridge_schemas_without_effects(self):
        """Positive registry admission; hostile publication doubles must stay idle."""
        before = image(self.home)
        with ExitStack() as stack:
            for target in ('os.open', 'os.mkdir', 'os.makedirs', 'os.write',
                           'os.rename', 'os.replace'):
                stack.enter_context(mock.patch(target, side_effect=AssertionError(
                    'registry discovery attempted a filesystem effect')))
            loaded = extensions.load()
        for name in ('openfresnel_probe', 'openfresnel_spawn'):
            spec = loaded.tools[name]
            self.assertEqual(spec.input_schema, contract_schema(name))
            self.assertIs(spec.mutating, True)
        self.assertEqual(loaded.tools['openfresnel_spawn'].input_schema[
            'properties']['envelope'], {'$ref': 'family_envelope.schema.json'})
        self.assertEqual(image(self.home), before)

    def test_review_h1_mutating_descriptors_remain_external_to_u05(self):
        """The installed facade must not turn acknowledgements into journal calls."""
        loaded = extensions.load()
        context = app.CallContext(self.home, loaded.validators, loaded.folds)
        runtime = jsonlane._runtime(context, loaded)
        for name in ('openfresnel_probe', 'openfresnel_spawn'):
            self.assertIs(loaded.tools[name].mutating, True)
            self.assertEqual(jsonlane._effect(name, runtime), 'external')
            self.assertFalse(getattr(loaded.tools[name].handler,
                                     '_memory_contract', False))
        self.assertFalse((self.home / 'ledger').exists())

    def test_review_h1_recipient_fixture_ignores_permissive_umask(self):
        """A permissive host umask cannot invalidate the authorized fixture."""
        previous = os.umask(0)
        try:
            configuration = self.recipient_configuration(
                sources=['source'], tools=['openfresnel_probe'])
        finally:
            os.umask(previous)
        for directory in (self.home, configuration.parent, configuration):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((configuration / 'config.json').stat().st_mode),
                         0o600)

    def test_review_h1_writable_recipient_configuration_still_refuses_dispatch(self):
        """Negative permissions contrast proves the fixture repair grants no bypass."""
        configuration = self.recipient_configuration(
            sources=['source'], tools=['openfresnel_probe'])
        (configuration / 'config.json').chmod(0o620)
        specs = self.descriptors()
        registry = extensions.Registry({spec.name: spec for spec in specs}, {}, {})
        out, err = io.StringIO(), io.StringIO()
        with client_double(self, 'probe', {}) as client:
            code = cli.main(['--home', str(self.home), 'json'], registry=registry,
                            stdin=io.BytesIO(canonical(call_envelope())),
                            stdout=out, stderr=err)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())['result'],
                         {'ok': False, 'code': 'bad_args'})
        # A-JL1: the contract sends diagnostics to stderr; require a path-naming
        # diagnostic that never echoes configuration content.
        self.assertIn('config.json', err.getvalue())
        self.assertNotIn('openfresnel_probe', err.getvalue())
        self.assertNotIn('source', err.getvalue().replace('config.json', ''))
        client.assert_not_called()
        self.assertFalse((self.home / 'ledger').exists())
