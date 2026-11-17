"""A5-A8: precedence and safe lexical configuration, no receiver ABI needed."""
import errno
import os
from pathlib import Path
from unittest import mock

from lineage.bridge import openfresnel as bridge
from tests.bridge._support import BridgeCase, ENV, TOOL_LIMIT, canonical, image, install_cases


class ConfigurationOracle(BridgeCase):
    def test_a05_explicit_outranks_environment_and_unopened_contract(self):
        """Positive explicit selection; hostile lower source is never consulted."""
        os.environ[ENV] = str(self.other)
        missing = self.base / 'unused-contract'
        actual = self.invoke(bridge.commands_dir, commands_dir=str(self.channel), contract_file=str(missing))
        self.assertEqual(actual, self.channel)
        self.assertFalse(missing.exists())
        self.assertEqual(list(self.channel.iterdir()), [])

    def test_a05_environment_outranks_unopened_contract(self):
        """Positive environment selection despite an invalid unused contract."""
        os.environ[ENV] = str(self.channel)
        actual = self.invoke(bridge.commands_dir, contract_file=str(self.base / 'unused'))
        self.assertEqual(actual, self.channel)

    def test_a05_explicit_contract_when_higher_sources_are_absent(self):
        """Positive named contract only; no inferred metadata lookup."""
        self.assertEqual(self.invoke(bridge.commands_dir, contract_file=str(self.contract)), self.other)

    def test_a06_absent_configuration_is_bad_args_and_creates_nothing(self):
        self.no_effect_error('bad_args', bridge.commands_dir)

    def test_a06_invalid_explicit_never_uses_valid_environment(self):
        os.environ[ENV] = str(self.other)
        self.no_effect_error('bad_args', bridge.commands_dir, commands_dir='', contract_file=str(self.contract))

    def test_a06_empty_environment_never_uses_valid_contract(self):
        os.environ[ENV] = ''
        self.no_effect_error('bad_args', bridge.commands_dir, contract_file=str(self.contract))

    def test_a06_missing_environment_directory_never_falls_through(self):
        os.environ[ENV] = str(self.base / 'missing')
        self.no_effect_error('bad_args', bridge.commands_dir, contract_file=str(self.contract))

    def test_a06_regular_file_is_not_commands_directory(self):
        self.no_effect_error('bad_args', bridge.commands_dir, commands_dir=str(self.contract))

    def test_a06_missing_explicit_directory_is_not_created(self):
        os.environ[ENV] = str(self.other)
        self.no_effect_error('bad_args', bridge.commands_dir, commands_dir=str(self.base / 'missing'))

    def test_a06_missing_contract_is_not_discovered_elsewhere(self):
        self.no_effect_error('bad_args', bridge.commands_dir, contract_file=str(self.base / 'missing'))

    def test_a06_directory_is_not_contract_file(self):
        self.no_effect_error('bad_args', bridge.commands_dir, contract_file=str(self.other))

    def test_a06_unreadable_contract_is_configuration_error(self):
        """Fault injection is deterministic even when the runner has privilege."""
        real_open = os.open
        def denied(path, flags, *args, **kwargs):
            if Path(os.fspath(path)).name == self.contract.name:
                raise PermissionError(errno.EACCES, 'fixture denied')
            return real_open(path, flags, *args, **kwargs)
        with mock.patch.object(os, 'open', side_effect=denied):
            self.no_effect_error('bad_args', bridge.commands_dir, contract_file=str(self.contract))

    def test_a07_directory_symlink_is_refused(self):
        link = self.base / 'linked'
        link.symlink_to(self.channel, target_is_directory=True)
        self.no_effect_error('bad_args', bridge.commands_dir, commands_dir=str(link))

    def test_a07_symlinked_lexical_ancestor_is_refused(self):
        nested = self.channel / 'nested'
        nested.mkdir()
        link = self.base / 'ancestor'
        link.symlink_to(self.channel, target_is_directory=True)
        self.no_effect_error('bad_args', bridge.commands_dir, commands_dir=str(link / 'nested'))

    def test_a07_symlink_cannot_be_hidden_by_dot_dot(self):
        link = self.base / 'ancestor'
        link.symlink_to(self.channel, target_is_directory=True)
        unsafe = str(link / '..' / self.other.name)
        self.no_effect_error('bad_args', bridge.commands_dir, commands_dir=unsafe)

    def test_a07_contract_symlink_is_refused(self):
        link = self.base / 'contract-link'
        link.symlink_to(self.contract)
        self.no_effect_error('bad_args', bridge.commands_dir, contract_file=str(link))

    def test_a07_contract_ancestor_symlink_is_refused(self):
        directory = self.base / 'config'
        directory.mkdir()
        original = directory / 'contract.json'
        original.write_bytes(self.contract.read_bytes())
        link = self.base / 'config-link'
        link.symlink_to(directory, target_is_directory=True)
        self.no_effect_error('bad_args', bridge.commands_dir, contract_file=str(link / original.name))

    def test_a08_external_directory_is_allowed_without_home_confinement(self):
        """Positive real directory outside ctx.home; no publication or mkdir."""
        self.assertNotIn(self.home, self.channel.parents)
        before = image(self.base)
        actual = self.invoke(bridge.commands_dir, commands_dir=str(self.channel))
        self.assertIsInstance(actual, Path)
        self.assertEqual(actual, self.channel)
        self.assertEqual(image(self.base), before)

    def test_a05_relative_contract_directory_is_refused(self):
        """Amendment B4 resolution: no implicit current-directory base."""
        self.contract.write_bytes(canonical({'paths': {'commands_dir': 'commands'}}))
        self.no_effect_error('bad_args', bridge.commands_dir, contract_file=str(self.contract))


def invalid_path(self, text):
    os.environ[ENV] = str(self.other)
    self.no_effect_error('bad_args', bridge.commands_dir, commands_dir=text)


install_cases(ConfigurationOracle, 'test_a06_invalid_explicit_path_', {
    'empty': '', 'nul': 'commands\x00tail', 'newline': 'commands\ntail',
    'tab': 'commands\ttail', 'del': 'commands\x7ftail',
    'surrogate': '\ud800', 'too_long': 'x' * 4097,
}, invalid_path)


def invalid_contract(self, value):
    self.contract.write_bytes(canonical(value))
    self.no_effect_error('bad_args', bridge.commands_dir, contract_file=str(self.contract))


install_cases(ConfigurationOracle, 'test_a06_contract_shape_', {
    'root_array': [], 'root_null': None, 'missing_paths': {},
    'null_paths': {'paths': None}, 'array_paths': {'paths': []},
    'missing_directory': {'paths': {}}, 'null_directory': {'paths': {'commands_dir': None}},
    'empty_directory': {'paths': {'commands_dir': ''}},
    'boolean_directory': {'paths': {'commands_dir': True}},
    'integer_directory': {'paths': {'commands_dir': 1}},
}, invalid_contract)


def malformed_contract(self, raw):
    self.contract.write_bytes(raw)
    self.no_effect_error('bad_args', bridge.commands_dir, contract_file=str(self.contract))


install_cases(ConfigurationOracle, 'test_a06_contract_bytes_', {
    'duplicate_keys': b'{"paths":{},"paths":{}}',
    'nested_duplicate': b'{"paths":{"commands_dir":"a","commands_dir":"b"}}',
    'nan': b'{"paths":NaN}', 'infinity': b'{"paths":Infinity}',
    'overflow': b'{"paths":1e999}', 'invalid_utf8': b'{"paths":"\xff"}',
    'surrogate': b'{"paths":"\\ud800"}', 'trailing_json': b'{}{}',
    'truncated': b'{', 'over_byte_cap': b' ' * (TOOL_LIMIT + 1),
}, malformed_contract)
