"""Public probe refusals and explicitly separate optional browser witnesses."""
import copy
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.qa import cdp_probe, atspi_probe, contracts
from tests.operability.test_contract import (OracleCase, CONTRACT_PATH,
                                            loaded_inventory)


class ProbeRefusalTests(OracleCase):
    def test_a01_missing_browser_is_inconclusive_not_empty_success(self):
        value=cdp_probe.probe(url='http://127.0.0.1:1/#/agents',
            browser=self.scratch()/'missing-browser',inventory=loaded_inventory(),
            contract=contracts.load_contract(CONTRACT_PATH),timeout_ms=100)
        self.verdict(value,'INCONCLUSIVE')
        self.assertEqual(value['rc'],2)

    def test_a21_absent_native_dependencies_are_inconclusive(self):
        directory=self.scratch()
        value=atspi_probe.probe(url='http://127.0.0.1:1/#/agents',
            browser=directory/'missing-browser',xvfb=directory/'missing-display',
            session_bus=directory/'missing-bus',inventory=loaded_inventory(),
            contract=contracts.load_contract(CONTRACT_PATH),timeout_ms=100,node_limit=50)
        self.assertEqual((value['method'],value['status'],value['rc']),('A','INCONCLUSIVE',2))

    def test_a06_nonloopback_url_is_refused_before_launch(self):
        with patch('subprocess.Popen',side_effect=AssertionError('Unsafe target launched')):
            value=cdp_probe.probe(url='http://192.0.2.1/#/agents',
                browser=self.scratch()/'missing-browser',inventory=loaded_inventory(),
                contract=contracts.load_contract(CONTRACT_PATH),timeout_ms=100)
        self.assertEqual((value['status'],value['rc']),('INCONCLUSIVE',2))

    def test_a06_file_url_is_refused_before_launch(self):
        with patch('subprocess.Popen',side_effect=AssertionError('Unsafe target launched')):
            value=cdp_probe.probe(url='file:'+chr(47)*3+'specimen.html',
                browser=self.scratch()/'missing-browser',inventory=loaded_inventory(),
                contract=contracts.load_contract(CONTRACT_PATH),timeout_ms=100)
        self.assertEqual((value['status'],value['rc']),('INCONCLUSIVE',2))

    def test_a06_native_probe_rejects_nonloopback_before_launch(self):
        directory=self.scratch()
        with patch('subprocess.Popen',side_effect=AssertionError('Unsafe target launched')):
            value=atspi_probe.probe(url='http://192.0.2.1/#/agents',
                browser=directory/'browser',xvfb=directory/'display',session_bus=directory/'bus',
                inventory=loaded_inventory(),contract=contracts.load_contract(CONTRACT_PATH),
                timeout_ms=100,node_limit=50)
        self.assertEqual((value['status'],value['rc']),('INCONCLUSIVE',2))


class RealBrowserTests(OracleCase):
    """Opt-in only: callers supply an already served disposable loopback page.

    Default discovery does not start a server or make a network request. A
    configured fixture run remains selftest and never establishes live gates.
    """
    def configured(self):
        browser=os.environ.get('U27_BROWSER')
        origin=os.environ.get('U27_SELFTEST_ORIGIN')
        if not browser or not origin:
            self.skipTest('INCONCLUSIVE: owned browser and disposable selftest origin not supplied; C unexecuted')
        return Path(browser),origin.rstrip('/')

    def run_page(self,name,scenario='good'):
        browser,origin=self.configured()
        value=loaded_inventory();value['scenario']=scenario
        return cdp_probe.probe(url=origin+'/'+name+'#/agents',browser=browser,
            inventory=value,contract=contracts.load_contract(CONTRACT_PATH),timeout_ms=1000)

    def test_a05_a08_real_pipe_good_specimen(self):
        result=self.run_page('good.html')
        self.assertEqual((result['method'],result['scope'],result['status'],result['rc']),
                         ('C','selftest','PASS',0))

    def test_a09_real_article_hostile(self):
        result=self.run_page('article-control.html','article-control')
        self.verdict(result,'FAIL','article_control')

    def test_a10_real_generic_control_hostile(self):
        result=self.run_page('clickable-div.html','clickable-div')
        self.verdict(result,'FAIL','non_native_control')

    def test_a11_real_normalized_duplicate_hostile(self):
        result=self.run_page('duplicate-names.html','duplicate-names')
        self.verdict(result,'FAIL','duplicate_name')

    def test_a12_real_overlong_name_hostile(self):
        result=self.run_page('overlong-name.html','overlong-name')
        self.verdict(result,'FAIL','name_too_long')

    def test_a07_real_stale_ready_hostile(self):
        result=self.run_page('stale-ready.html','stale-ready')
        self.verdict(result,'FAIL','stale_ready')


class UnavailableLiveWitnessTests(OracleCase):
    """Explicit unavailable gates; these are not successful instrument checks."""
    def test_a06_a14_refreshed_origin_route_and_identity_association(self):
        self.skipTest('INCONCLUSIVE: prepared reload/filter/reorder/redirect browser contexts AUSENTE')
    def test_a13_injected_identity_collision(self):
        self.skipTest('INCONCLUSIVE: collision injection seam and rendered collision specimen AUSENTE')
    def test_a16_keyboard_modal_containment_and_heading_fallback(self):
        self.skipTest('INCONCLUSIVE: U06/U21 and independent live C/A keyboard capsules AUSENTE')
    def test_a17_persistent_status_transition_sequence(self):
        self.skipTest('INCONCLUSIVE: live Lamport transitions and status-node observations AUSENTE')
    def test_a18_failure_recovery_and_unchanged_retry(self):
        self.skipTest('INCONCLUSIVE: prepared response-loss/panel/draft recovery frames AUSENTE')
    def test_a19_history_route_query_and_skip_focus(self):
        self.skipTest('INCONCLUSIVE: live route/history/query fixtures AUSENTE')
    def test_a20_actual_zoom_geometry_contrast_and_motion_matrix(self):
        self.skipTest('INCONCLUSIVE: rendered matrix, alpha composition and zoom procedure unpinned')
    def test_a21_native_action_changes_checked_state(self):
        self.skipTest('INCONCLUSIVE: GI/private display/bus/native browser capsule AUSENTE')
    def test_a25_manifest_clock_frame_repeatability(self):
        self.skipTest('INCONCLUSIVE: U21 manifest/datasets/declared frames AUSENTE')
    def test_a27_cursor_paging_and_resync_live_witness(self):
        self.skipTest('INCONCLUSIVE: seeded public cursor service and export manifest AUSENTE')
    def test_a28_live_memory_required_debt_and_valid_failure_close(self):
        self.skipTest('INCONCLUSIVE: U29 live seed and real HTTP close/memory witnesses AUSENTE')
    def test_a29_real_http_token_origin_and_actor_binding(self):
        self.skipTest('INCONCLUSIVE: U06 shared HTTP dispatcher and bootstrap token AUSENTE')
    def test_a30_all_screens_and_conditional_dialogs(self):
        self.skipTest('INCONCLUSIVE: agents/agent/lineage/arena/bench/ledger live route matrix AUSENTE')
