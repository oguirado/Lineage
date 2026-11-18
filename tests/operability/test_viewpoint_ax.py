"""Real browser gate using only prune_ax_v1 roles, names and ARIA states."""
from __future__ import annotations
from contextlib import nullcontext
from io import StringIO
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.request import urlopen

from tools.qa.ax_prune import (ACTIONABLE_ROLES, CHASSIS_ROLES, STATE_ATTRS,
                                canonical_tree, normalize_name, prune, violations)
from tools.qa import cdp_probe
from tools.qa.cdp_probe import (owned_page, screen_ready_name, wait_ready,
                                viewpoint_probe, _eval)
from tools.qa.cdp_pipe import PipeError, _decode_frame

ROOT = Path(__file__).resolve().parents[2]
BROWSER = next((shutil.which(n) for n in ('google-chrome', 'chromium', 'chromium-browser')
                if shutil.which(n)), None)


class PruneTests(unittest.TestCase):
    def test_document_order_ignored_ancestors_and_opaque_articles(self):
        def node(n, role, children=(), **kw):
            return dict(nodeId=n, role={'value':role}, name={'value':n}, childIds=list(children), **kw)
        raw=[node('button','button'), node('root','RootWebArea',['generic','article']),
             node('article','article',['hidden-control']), node('hidden-control','button'),
             node('generic','generic',['button'])]
        result=prune(raw)
        self.assertEqual([(n['role'],n['depth']) for n in result],
                         [('RootWebArea',0),('button',1),('article',1)])
        self.assertNotIn('hidden-control',[n['name'] for n in result])
        raw[2]['ignored']=True
        self.assertIn('hidden-control',[n['name'] for n in prune(raw)])

    def test_utf8_serialized_names_states_and_quiet_hash(self):
        self.assertEqual(normalize_name('  e\u0301 \n x|y\\z '),'é x\\|y\\\\z')
        for text in ('é'*40,'a'*63+'|','a'*62+'\\','🙂'*20):
            normalized=normalize_name(text)
            self.assertLessEqual(len(normalized.encode()),64)
            self.assertEqual((len(normalized)-len(normalized.rstrip('\\')))%2,0)
        raw=[dict(nodeId='root',role={'value':'button'},name={'value':'Commit'},
                  properties=[{'name':k,'value':{'value':True}} for k in (*STATE_ATTRS,'focused','focusable')])]
        first=prune(raw)
        self.assertEqual([k for k,v in first[0]['attrs']],list(STATE_ATTRS))
        raw[0]['backendDOMNodeId']=77
        raw[0]['properties'].append({'name':'focused','value':{'value':False}})
        self.assertEqual(canonical_tree(first),canonical_tree(prune(raw)))
        self.assertNotIn('table',CHASSIS_ROLES)

    def test_mutants_do_not_pass_the_gate(self):
        self.assertIn('empty_tree',violations([],'Screen agents ready'))
        raw=[dict(nodeId='r',role={'value':'RootWebArea'},childIds=['a','b']),
             dict(nodeId='a',role={'value':'button'},name={'value':'Duplicate'}),
             dict(nodeId='b',role={'value':'button'},name={'value':'Duplicate'})]
        self.assertTrue(any(v.startswith('duplicate_action') for v in violations(prune(raw),'Screen agents ready')))

    def test_browser_frames_exceed_ledger_cap_without_relaxing_strict_json(self):
        value={'id':1,'result':{'text':'x'*70000}}
        self.assertEqual(_decode_frame(json.dumps(value).encode()),value)
        for raw in (b'{"id":1,"id":2}',b'{"x":NaN}',b'{"x":1e999}',b'{"x":"\\ud800"}'):
            with self.assertRaises(ValueError):
                _decode_frame(raw)


class ViewPointProbeControls(unittest.TestCase):
    base = 'http://127.0.0.1:1/'
    agents = base + '#/agents'
    credential_suffixes = (
        '#/agents?q=alpha#token=placeholder',
        '#/agents?q=alpha;token=placeholder',
        '#/agents#access_token=placeholder',
        '#/agents&token=placeholder',
        '#/token=placeholder',
        '#%2Ftoken=placeholder',
        ';session_token=placeholder#/agents',
        '?access-token=placeholder#/agents',
        '?q=alpha;%20APIKEY%20=placeholder#/agents',
        '#/agents?lineage_session_token=placeholder',
        '??token=placeholder#/agents',
        '?next=/agents?lineage_session_token=placeholder',
        '#/agents%3Ftoken=placeholder',
        '?%26token=placeholder#/agents',
        '#/agents%3Bauth-token=placeholder',
        '#/agents%23%72efresh_token=placeholder',
        'token=placeholder#/agents',
        'first=value/token=placeholder#/agents',
    )

    def setUp(self):
        self.artifacts = Path(self.enterContext(tempfile.TemporaryDirectory()))

    @staticmethod
    def ready_tree(ready_name='Screen agents ready'):
        # The page title models an AX name that could echo a URL value.
        return [
            dict(nodeId='root', role={'value': 'RootWebArea'}, name={'value': 'placeholder'},
                 childIds=['banner', 'navigation', 'main', 'footer', 'ready']),
            dict(nodeId='banner', role={'value': 'banner'}),
            dict(nodeId='navigation', role={'value': 'navigation'}, childIds=['link']),
            dict(nodeId='link', role={'value': 'link'}, name={'value': 'Agents navigation'},
                 properties=[dict(name='current', value={'value': 'page'})]),
            dict(nodeId='main', role={'value': 'main'}, name={'value': 'Agents'}),
            dict(nodeId='footer', role={'value': 'contentinfo'}),
            dict(nodeId='ready', role={'value': 'status'}, name={'value': ready_name}),
        ]

    def observe(self, supplied, *, observed=None, ticks=None, nodes=None):
        locations = None if isinstance(observed, (str, type(None))) else iter(observed)
        current = supplied if observed is None else observed
        tree = self.ready_tree() if nodes is None else nodes
        sample = Mock(return_value={'nodes': tree})

        def call(method, params, *, session_id):
            self.assertEqual(session_id, 'page')
            if method == 'Runtime.evaluate':
                self.assertEqual(params['expression'], 'location.href')
                location = current if locations is None else next(locations, supplied)
                return {'result': {'value': location}}
            self.assertEqual(method, 'Accessibility.getFullAXTree')
            return sample()

        if ticks is None:
            ticks = [0] * 8 + [1, 1]
        clock = SimpleNamespace(monotonic=Mock(side_effect=ticks))
        with (patch('tools.qa.cdp_probe.owned_page',
                    return_value=nullcontext((SimpleNamespace(call=call), 'page'))) as opened,
              patch('tools.qa.cdp_probe.time', clock),
              patch('select.select')):
            report = viewpoint_probe(url=supplied, browser='unused', timeout_ms=1000,
                                     artifact_root=self.artifacts)
        return report, opened, sample

    def assert_unsafe(self, report):
        self.assertEqual((report['status'], report['rc']), ('FAIL', 1))
        self.assertEqual([c['code'] for c in report['checks']], ['unsafe_content'])
        self.assertNotIn('placeholder', json.dumps(report))
        self.assertEqual(report['artifacts'], [])
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def run_viewpoint_cli(self, *args):
        output = StringIO()
        with patch('sys.stdout', output):
            rc = cdp_probe.main(['--viewpoint', '--url', self.agents,
                                 '--browser', 'unused', '--timeout-ms', '1000', *args])
        report = json.loads(output.getvalue())
        self.assertEqual(report['schema'], 'lineage.qa.report/v1')
        self.assertEqual(rc, report['rc'])
        return report

    def test_owned_page_refuses_credentials_before_allocating_profile(self):
        with patch('tools.qa.cdp_probe.tempfile.TemporaryDirectory',
                   side_effect=AssertionError('Browser profile allocated')) as profile:
            with self.assertRaises(PipeError) as caught:
                with owned_page('unused', self.base + '#token=placeholder', 1000):
                    self.fail('Credential-bearing page opened')
        self.assertEqual(caught.exception.code, 'unsafe_content')
        self.assertNotIn('placeholder', str(caught.exception))
        profile.assert_not_called()

    def test_invalid_artifact_roots_are_refused_before_opening_browser(self):
        directory = self.artifacts / 'directory'
        directory.mkdir()
        symlink = self.artifacts / 'symlink'
        symlink.symlink_to(self.artifacts, target_is_directory=True)
        file = self.artifacts / 'file'
        file.touch()
        for root in ('', self.artifacts / 'missing', symlink, symlink / 'directory', file):
            for cli in (False, True):
                with self.subTest(root=root, cli=cli), patch(
                    'tools.qa.cdp_probe.owned_page',
                    side_effect=AssertionError('Browser opened with invalid artifact root'),
                ) as opened:
                    if cli:
                        report = self.run_viewpoint_cli('--artifacts', str(root))
                    else:
                        report = viewpoint_probe(url=self.agents, browser='unused',
                                                 timeout_ms=1000, artifact_root=root)
                    self.assertEqual((report['status'], report['rc']), ('INCONCLUSIVE', 2))
                    self.assertEqual([c['code'] for c in report['checks']], ['bad_config'])
                    self.assertEqual(report['artifacts'], [])
                    opened.assert_not_called()
        self.assertEqual(list(directory.iterdir()), [])

    def test_malformed_ax_response_returns_one_cli_report(self):
        def call(method, params, *, session_id):
            if method == 'Runtime.evaluate':
                return {'result': {'value': self.agents}}
            self.assertEqual(method, 'Accessibility.getFullAXTree')
            return {}

        client = Mock()
        client.call.side_effect = call
        with patch('tools.qa.cdp_probe.owned_page',
                   return_value=nullcontext((client, 'page'))):
            report = self.run_viewpoint_cli('--artifacts', str(self.artifacts))
        self.assertEqual(client.call.call_count, 2)
        self.assertEqual((report['status'], report['rc']), ('INCONCLUSIVE', 2))
        self.assertEqual([c['code'] for c in report['checks']], ['probe_internal'])
        self.assertEqual(report['artifacts'], [])
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_deadline_before_first_sample(self):
        client = Mock()
        clock = SimpleNamespace(monotonic=Mock(side_effect=[0, 1]))
        with patch('tools.qa.cdp_probe.time', clock):
            with self.assertRaises(PipeError) as caught:
                wait_ready(client, 'page', self.agents, 1000)
        self.assertEqual(caught.exception.code, 'deadline')
        self.assertEqual(caught.exception.nodes, [])
        client.call.assert_not_called()

        report, _, sample = self.observe(self.agents, ticks=[0, 1])
        self.assertEqual((report['status'], report['rc']), ('INCONCLUSIVE', 2))
        self.assertEqual([c['code'] for c in report['checks']], ['deadline'])
        self.assertEqual(report['artifacts'], [])
        sample.assert_not_called()

    def test_deadline_after_reads_keeps_last_sample(self):
        first = self.ready_tree('First sample')
        last = self.ready_tree('Last sample')
        client = Mock()
        client.call.side_effect = [{'nodes': first}, {'nodes': last}]
        clock = SimpleNamespace(monotonic=Mock(side_effect=[0, 0, 0, 0, 1, 1]))
        with patch('tools.qa.cdp_probe.time', clock), patch('select.select'):
            with self.assertRaises(PipeError) as caught:
                wait_ready(client, 'page', self.agents, 1000)
        self.assertEqual(caught.exception.code, 'deadline')
        self.assertEqual(caught.exception.nodes, prune(last))
        self.assertEqual(client.call.call_count, 2)

    def test_pipe_deadline_keeps_last_available_sample(self):
        first = self.ready_tree('First sample')
        for samples, expected in (([], []), ([{'nodes': first}], prune(first))):
            with self.subTest(reads=len(samples)):
                expiry = PipeError('deadline')
                client = Mock()
                client.call.side_effect = [*samples, expiry]
                clock = SimpleNamespace(monotonic=Mock(return_value=0))
                with patch('tools.qa.cdp_probe.time', clock), patch('select.select'):
                    with self.assertRaises(PipeError) as caught:
                        wait_ready(client, 'page', self.agents, 1000)
                self.assertIs(caught.exception, expiry)
                self.assertEqual(caught.exception.code, 'deadline')
                self.assertEqual(caught.exception.nodes, expected)
                self.assertEqual(client.call.call_count, len(samples) + 1)

    def test_supplied_credentials_refused_before_browser_launch(self):
        for suffix in ('#token=placeholder', '#/agents?access_token=placeholder',
                       '#/agents?token=placeholder', '?%74oKeN=placeholder#/agents',
                       '#%74oken=placeholder', '#/agents?%61ccess%5Ftoken=placeholder',
                       '?session_token=placeholder#/agents', '#/agents?token=',
                       *self.credential_suffixes):
            with self.subTest(suffix=suffix):
                report, opened, sample = self.observe(self.base + suffix)
                self.assert_unsafe(report)
                opened.assert_not_called()
                sample.assert_not_called()

    def test_observed_credentials_refused_before_first_ax_read(self):
        for suffix in ('#token=placeholder', '#/agents?access_token=placeholder',
                       '#/agents?token=placeholder', '?%74oken=placeholder#/agents',
                       *self.credential_suffixes):
            with self.subTest(suffix=suffix):
                report, _, sample = self.observe(self.agents, observed=self.base + suffix,
                                                 ticks=[0, 1])
                self.assert_unsafe(report)
                sample.assert_not_called()

    def test_userinfo_is_refused_without_disclosing_its_value(self):
        url = self.agents.replace('://', '://user:placeholder@')
        report, opened, sample = self.observe(url)
        self.assertEqual((report['status'], report['rc']), ('INCONCLUSIVE', 2))
        self.assertEqual([c['code'] for c in report['checks']], ['bad_config'])
        self.assertNotIn('placeholder', json.dumps(report))
        self.assertEqual(report['artifacts'], [])
        self.assertEqual(list(self.artifacts.iterdir()), [])
        opened.assert_not_called()
        sample.assert_not_called()

        report, _, sample = self.observe(self.agents, observed=url)
        self.assert_unsafe(report)
        sample.assert_not_called()

    def test_credentials_observed_during_polling_win_over_deadline(self):
        report, _, sample = self.observe(
            self.agents, observed=[self.agents, self.base + '#token=placeholder'],
            ticks=[0, 0, 1, 1], nodes=self.ready_tree('Still loading'))
        self.assert_unsafe(report)
        sample.assert_called_once()

    def test_filters_keyless_components_and_identity_routes_pass(self):
        for suffix, ready_name in (
            ('#/agents?q=alpha', 'Screen agents ready'),
            ('#/agents?q=token%3Dplaceholder', 'Screen agents ready'),
            ('#/agents?q=example%3Ftoken%3Dplaceholder', 'Screen agents ready'),
            ('?placeholder#/agents?token', 'Screen agents ready'),
            ('#placeholder', 'Screen placeholder ready'),
            ('#/agents/token-agent', 'Screen agent token-agent ready'),
        ):
            with self.subTest(suffix=suffix):
                url = self.base + suffix
                report, _, sample = self.observe(url, observed=['about:blank', url],
                                                 nodes=self.ready_tree(ready_name))
                self.assertEqual((report['status'], report['rc']), ('PASS', 0), report['checks'])
                self.assertEqual([c['code'] for c in report['checks']], ['ok'])
                self.assertEqual([a['kind'] for a in report['artifacts']], ['pruned'])
                self.assertEqual(sample.call_count, 3)

    def test_observed_origin_mismatch_is_still_refused(self):
        for url in ('http://127.0.0.1:2/#/agents', 'http://localhost:1/#/agents',
                    'https://example.com/#/agents', 'chrome-error://chromewebdata/'):
            with self.subTest(url=url):
                report, _, sample = self.observe(self.agents, observed=url)
                self.assert_wrong_target(report)
                sample.assert_not_called()

    def test_blank_observed_after_readiness_is_wrong_target(self):
        report, _, sample = self.observe(
            self.agents, observed=[self.agents] * 4 + ['about:blank'])
        self.assert_wrong_target(report)
        self.assertEqual(sample.call_count, 3)

    def assert_wrong_target(self, report):
        self.assertEqual((report['status'], report['rc']), ('INCONCLUSIVE', 2))
        self.assertEqual([c['code'] for c in report['checks']], ['wrong_target'])
        self.assertEqual(report['artifacts'], [])
        self.assertEqual(list(self.artifacts.iterdir()), [])


@unittest.skipUnless(BROWSER, 'Chrome binary unavailable')
@unittest.skipUnless((ROOT / 'node_modules' / '.bin' / 'vite').exists(),
                     'UI toolchain (node_modules/.bin/vite) unavailable')
class ViewPointBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resource=tempfile.TemporaryDirectory(prefix='viewpoint-',dir=ROOT/'tests'/'operability')
        cls.addClassCleanup(cls.resource.cleanup)
        cls.temp=Path(cls.resource.name)
        cls.home=cls.temp/'home'
        cls.env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        # Build into the test capsule and load the config without a temporary bundle.
        build=subprocess.run(['../node_modules/.bin/vite','build','--configLoader','runner',
                              '--outDir',str(cls.temp/'ui-dist'),'--emptyOutDir'],
                             cwd=ROOT/'ui',env=cls.env,capture_output=True,text=True,timeout=60)
        if build.returncode:
            raise AssertionError('UI build failed: '+build.stderr)
        def cli(tool,args):
            result=subprocess.run([sys.executable,'-m','lineage','--home',str(cls.home),
                                   'call',tool,'--json',json.dumps(args)],cwd=ROOT,env=cls.env,
                                  capture_output=True,text=True,timeout=20)
            if result.returncode:
                raise AssertionError(tool+': '+result.stdout+' '+result.stderr)
            return json.loads(result.stdout)['untrusted']
        references=[]
        for ref_id in ('gold_s1','memory_v21'):
            reference=cli('reference_get',{'ref_id':ref_id})['reference']
            references.append(dict(id=ref_id,sha256=reference['sha256']))
        cls.agent_ids=('test-py-oracle','test-py-review','token-agent')
        for agent_id in cls.agent_ids:
            cli('agent_create',dict(agent_id=agent_id,display_name=agent_id,workflow='test',
                language='python',allowed_seats=[dict(model='test-model',effort='medium',mode='headless')],
                references=references,skills=[],agent='system',op_id='ops1-create-'+agent_id))
        cls.server=subprocess.Popen([sys.executable,'-m','lineage','--home',str(cls.home),
            'serve','--port','0','--ui-dist',str(cls.temp/'ui-dist')],cwd=ROOT,env=cls.env,
            stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        cls.addClassCleanup(cls.reap,cls.server)
        if not select.select([cls.server.stderr],[],[],10)[0]:
            raise AssertionError('Server startup deadline')
        startup=json.loads(cls.server.stderr.readline())
        cls.origin='http://127.0.0.1:'+str(startup['port'])
        with urlopen(cls.origin+'/api/health',timeout=5) as response:
            if not json.load(response)['ok']:
                raise AssertionError('Server unhealthy')
        cls.page=owned_page(BROWSER,cls.origin+'/#/agents',10000)
        cls.client,cls.session=cls.page.__enter__()
        cls.addClassCleanup(cls.page.__exit__,None,None,None)

    @staticmethod
    def reap(process):
        if process.pid<=1:
            raise AssertionError('Unsafe owned process identity')
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=5)
        if process.stderr is not None:
            process.stderr.close()

    def navigate(self,route):
        url=self.origin+'/'+route
        self.client.call('Page.navigate',{'url':url},session_id=self.session)
        try:
            nodes=wait_ready(self.client,self.session,url,10000)
        except Exception as error:
            self.fail(str(error)+' '+repr([(n['role'],n['name']) for n in getattr(error,'nodes',[])]))
        artifact=self.temp/('pruned-'+route.replace('/','_').replace('#','')+'.json')
        artifact.write_text(json.dumps(nodes,ensure_ascii=False,indent=2),encoding='utf-8')
        return url,nodes

    def test_every_route_is_drivable_through_pruned_ax(self):
        for route in ('#/agents','#/agents/test-py-oracle','#/lineage','#/arena',
                      '#/arena/OPS1bench','#/ledger','#/agents/token-agent'):
            with self.subTest(route=route):
                url,nodes=self.navigate(route)
                failures=violations(nodes,screen_ready_name(url))
                # CDP's AXPropertyName omits aria-current on this Chrome build.
                # Keep the limitation explicit; verify the actual ARIA attribute
                # separately on the AX-identified link, without inventing a state.
                self.assertFalse([f for f in failures if f!='missing_current_navigation'])
                owner='Agents' if route.startswith('#/agents') else 'Arena' if route.startswith('#/arena') else 'Lineage' if route=='#/lineage' else 'Ledger'
                nav=next(n for n in nodes if n['role']=='link' and n['name']==owner+' navigation')
                dom=self.client.call('DOM.describeNode',{'backendNodeId':nav['backend_id']},session_id=self.session)['node']
                attributes=dict(zip(dom['attributes'][::2],dom['attributes'][1::2]))
                self.assertEqual(attributes.get('aria-current'),'page')
                if 'missing_current_navigation' not in failures:
                    self.assertEqual(dict(nav['attrs']).get('current'),'page')
                self.assertFalse(any(n['role']=='progressbar' for n in nodes))
                if route in ('#/agents','#/lineage'):
                    for agent_id in self.agent_ids:
                        self.assertTrue(any(n['role'] in ('button','link','option') and agent_id in n['name'] for n in nodes),agent_id)
                current=_eval(self.client,self.session,'location.href')
                self.assertEqual(current,url)
                # The bootstrap secret is checked privately, never written to evidence.
                with urlopen(self.origin+'/index.html',timeout=5) as response:
                    import re
                    token=re.search(r'name="lineage-session-token" content="([^"]+)"',response.read().decode())[1]
                self.assertNotIn(token,current)
                actions=[(n['role'],n['name']) for n in nodes if n['role'] in ACTIONABLE_ROLES]
                self.assertEqual(len(actions),len(set(actions)))

    def test_error_is_a_persistent_named_alert(self):
        url,nodes=self.navigate('#/arena/absent01')
        # This integrated host may lack bench_status entirely; both refusals are visible.
        alerts=[n for n in nodes if n['role']=='alert']
        self.assertTrue(any('Error:' in n['name'] for n in alerts),nodes)
        later=prune(self.client.call('Accessibility.getFullAXTree',{},session_id=self.session)['nodes'])
        self.assertEqual([(n['role'],n['name']) for n in alerts],
                         [(n['role'],n['name']) for n in later if n['role']=='alert'])

    def test_committed_search_value_is_readable_as_status_name(self):
        _,nodes=self.navigate('#/agents')
        search=next(n for n in nodes if n['role']=='searchbox' and n['name']=='Find agents')
        handle=self.client.call('DOM.resolveNode',{'backendNodeId':search['backend_id']},session_id=self.session)['object']['objectId']
        self.client.call('Runtime.callFunctionOn',{'objectId':handle,
            'functionDeclaration':"function(){this.value='oracle';this.dispatchEvent(new Event('input',{bubbles:true}));}"},session_id=self.session)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            nodes=prune(self.client.call('Accessibility.getFullAXTree',{},session_id=self.session)['nodes'])
            if any(n['role']=='status' and n['name']=='Find agents: oracle' for n in nodes):
                break
            select.select([],[],[],0.02)
        self.assertTrue(any(n['role']=='status' and n['name']=='Find agents: oracle' for n in nodes))

    def test_public_cdp_gate_reports_only_measured_ax_limitations(self):
        result=viewpoint_probe(url=self.origin+'/#/agents',browser=BROWSER,timeout_ms=10000,artifact_root=self.temp)
        if result['status']=='INCONCLUSIVE':
            self.assertEqual([c['code'] for c in result['checks']],['incomplete_tree'])
            self.assertIn('aria-current',result['checks'][0]['detail'])
        else:
            self.assertEqual((result['status'],result['rc']),('PASS',0),result['checks'])


    def test_native_gate_never_passes_an_empty_tree(self):
        from tools.qa import atspi_probe
        result=atspi_probe.viewpoint_probe(url=self.origin+'/#/agents',browser=BROWSER,
            xvfb=shutil.which('Xvfb') or 'missing-xvfb',
            session_bus=shutil.which('dbus-daemon') or 'missing-dbus',
            timeout_ms=12000,node_limit=10000,artifact_root=self.temp,
            expected_buttons=('Create agent','Open agent test-py-oracle'))
        self.assertIn(result['status'],('PASS','INCONCLUSIVE'),result['checks'])
        if result['status']=='INCONCLUSIVE':
            self.assertTrue(all(c['detail'] for c in result['checks']))
        else:
            self.assertTrue(result['artifacts'])
