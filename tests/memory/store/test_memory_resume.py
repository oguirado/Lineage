"""Frozen extension seam and integration gates; never substitute legacy APIs."""
import ast
import copy
import importlib
import inspect
import io
import itertools
import json
import os
import shutil
import sys
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock
from lineage.domain.memory import entry, store, bootcheck
from lineage.ext import memory_resume
from tests.memory.store import (OracleCase, ROOT, AGENT, Counter, canonical,
                                sha, tool_schemas, unit_record, alias_patch, version)


class MemoryResumeOracle(OracleCase):
    def transaction_context(self, counter=None):
        registry, journal, app = self.require_k0()
        ids = itertools.count(self.snapshot.head+1)
        # A-U11: U10 admission consumes an agents fold; U12 is not integrated.
        # Supply only its prerequisite fixture, keeping the real U10 memory fold,
        # validators, journal, entry builder and projection publication in use.
        loaded = registry.load()
        def fixture_agents(state, event):
            payload = event['payload']
            agents = state.setdefault('agents', {})
            if event['kind'] == 'agent.born':
                record = copy.deepcopy(payload['record'])
                agents[record['agent_id']] = record
            elif event['kind'] == 'agent.status':
                agents[payload['agent_id']]['status'] = payload['to']
            for agent_id, record in agents.items():
                memory = state.get('memory', {}).get(agent_id)
                if memory is not None:
                    record['memory_gen'] = memory['memory_gen']
                    record['agent_version'] = version(record)
        folds = dict(loaded.folds)
        folds['agents'] = registry.FoldSpec(frozenset({'agent.born', 'agent.status',
            'memory.put', 'memory.retire'}), 40, fixture_agents)
        integrated = registry.Registry(loaded.tools, loaded.validators, folds)
        services = registry.Services(home=self.home, repo_root=self.repo, registry=integrated,
            clock=lambda: 100, id_factory=lambda: 'e-%016x' % next(ids),
            token_count=counter or Counter())
        return registry.Context(services=services, actor=AGENT, authority='tool', transport='library')

    def command(self, registry, unit, op_id):
        # A-U11: native journal operation identities require at least eight characters.
        op_id = 'oracle-' + op_id
        return registry.Command(tool='memory_put', args={'agent_id':AGENT, 'unit':copy.deepcopy(unit),
            'agent':AGENT, 'op_id':op_id}, agent=AGENT, op_id=op_id)

    def test_a26_exact_extension_inventory_and_frozen_discovery_schemas(self):
        tools = tuple(memory_resume.TOOLS)
        self.assertEqual({t.name for t in tools}, {'memory_route','memory_bootcheck'})
        self.assertEqual(len(tools),2)
        self.assertEqual(dict(memory_resume.VALIDATORS),{})
        self.assertEqual(dict(memory_resume.FOLDS),{})
        for spec in tools:
            self.assertEqual(spec.effect,'read')
            self.assertEqual(spec.input_schema, tool_schemas(spec.name)[0])
            params = list(inspect.signature(spec.handler).parameters.values())
            self.assertEqual([p.name for p in params], ['args','ctx'])
            self.assertTrue(all(p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for p in params))

    def test_a26_handlers_delegate_positionally_and_return_inner_data(self):
        tools = {t.name:t for t in memory_resume.TOOLS}
        route = importlib.import_module('lineage.domain.memory.route')
        data={'units':[],'answer':'NOT IN MEMORY','head':1}
        args={'agent_id':AGENT,'query':'needle','limit':10,'agent':'system'}
        with alias_patch(route,'route',mock.Mock(return_value=copy.deepcopy(data))) as target:
            result=tools['memory_route'].handler(args,self.ctx)
        self.assertEqual(result,data); target.assert_called_once_with(AGENT,'needle',limit=10,ctx=self.ctx)
        observation={'agent_version':'0'*64,'memory_gen':0,'head':1,'entry_sha256':'0'*64}
        success={'passed':True,'code':'OK','checks':[{'id':'fixture','passed':True}],'head':1}
        with alias_patch(bootcheck,'check',mock.Mock(return_value=copy.deepcopy(success))) as target:
            result=tools['memory_bootcheck'].handler({'agent_id':AGENT,'observed':observation},self.ctx)
        self.assertEqual(result,success); target.assert_called_once_with(AGENT,observation,ctx=self.ctx)

    def test_a26_registry_load_has_one_owner_and_read_effects(self):
        tools=tuple(memory_resume.TOOLS)
        registry,_,_=self.require_k0(); loaded=registry.load()
        for tool in tools:
            self.assertIs(loaded.tools[tool.name].handler,tool.handler)
            # A-U11: native Registry copies expose read effects as mutating=False.
            self.assertIs(loaded.tools[tool.name].mutating, False)
        source=ast.parse((ROOT/'lineage/ext/memory_resume.py').read_text())
        imports=[n.module or '' for n in ast.walk(source) if isinstance(n,ast.ImportFrom)]
        imports += [a.name for n in ast.walk(source) if isinstance(n,ast.Import) for a in n.names]
        self.assertFalse(any(n.startswith(('lineage.core.app','lineage.core.mcp','lineage.serve','lineage.core.cli','lineage.core.jsonlane')) for n in imports))

    def test_a04_overflow_before_append_then_same_operation_can_commit(self):
        self.publish(); registry,journal,_=self.require_k0()
        units=importlib.import_module('lineage.domain.memory.units')
        candidate=unit_record('Candidate1','candidate changes static entry',level=2)
        ctx=self.transaction_context(lambda text:4001 if 'Candidate1' in text else 1)
        command=self.command(registry,candidate,'admission-retry')
        before=self.ledger.read_bytes(); prefix=journal.snapshot(ctx=ctx)
        artifacts={k:(self.memory/k).read_bytes() for k in self.generated()}
        state=copy.deepcopy(prefix.state)
        self.domain_error('memory_debt',lambda:units.put(AGENT,candidate,command=command,ctx=ctx))
        self.assertEqual(self.ledger.read_bytes(),before)
        self.assertEqual(journal.snapshot(ctx=ctx).head,prefix.head)
        self.assertEqual(journal.snapshot(ctx=ctx).state,state)
        self.assertEqual({k:(self.memory/k).read_bytes() for k in artifacts},artifacts)
        # Same validated request/op_id after capacity is restored: rejection left no dedup witness.
        ctx=self.transaction_context(Counter())
        committed=units.put(AGENT,candidate,command=command,ctx=ctx)
        self.assertEqual(committed.head,prefix.head+1)
        self.assertEqual(committed.value['unit'],candidate)
        self.assertEqual(journal.snapshot(ctx=ctx).head,prefix.head+1)
        self.assertEqual(store.verify_projection(AGENT,snapshot=journal.snapshot(ctx=ctx),ctx=ctx),())

    def test_a04_real_transaction_byte_overflow_appends_nothing(self):
        self.publish(); registry,journal,_=self.require_k0()
        units=importlib.import_module('lineage.domain.memory.units'); ctx=self.transaction_context()
        first=unit_record('Large0001','a'*3000,level=2)
        units.put(AGENT,first,command=self.command(registry,first,'first-large'),ctx=ctx)
        before=self.ledger.read_bytes(); artifacts=self.disk_tree(self.memory)
        prefix=journal.snapshot(ctx=ctx); state=copy.deepcopy(prefix.state)
        overflowing=unit_record('Large0002','b'*3000,level=2)
        self.domain_error('memory_debt',lambda:units.put(AGENT,overflowing,
            command=self.command(registry,overflowing,'second-large'),ctx=ctx))
        self.assertEqual(self.ledger.read_bytes(),before)
        self.assertEqual(self.disk_tree(self.memory),artifacts)
        self.assertEqual(journal.snapshot(ctx=ctx).state,state)
        fitting=unit_record('Small0001','fits the remaining static entry capacity',level=2)
        committed=units.put(AGENT,fitting,command=self.command(registry,fitting,'fitting'),ctx=ctx)
        self.assertEqual(committed.head,prefix.head+1)
        self.assertEqual(store.verify_projection(AGENT,snapshot=journal.snapshot(ctx=ctx),ctx=ctx),())

    def test_a10_postcommit_failure_replay_preserves_original_commit_prefix(self):
        self.publish(); registry,journal,_=self.require_k0()
        units=importlib.import_module('lineage.domain.memory.units')
        candidate=unit_record('Candidate1','durable event despite projection failure',level=2)
        ctx=self.transaction_context(); command=self.command(registry,candidate,'postcommit-retry')
        initial=journal.snapshot(ctx=ctx)
        clean_home=self.base/'clean-execution'; shutil.copytree(self.home,clean_home)
        original_home=self.home
        try:
            self.home=clean_home; clean_ctx=self.transaction_context()
        finally:
            self.home=original_home
        clean=units.put(AGENT,candidate,command=command,ctx=clean_ctx)
        with alias_patch(store,'rebuild',mock.Mock(side_effect=OSError('synthetic projection I/O'))):
            self.domain_error('internal',lambda:units.put(AGENT,candidate,command=command,ctx=ctx))
        durable=journal.snapshot(ctx=ctx)
        self.assertEqual(durable.head,initial.head+1)
        self.assertEqual(durable.events[-1]['payload']['unit'],candidate)
        ledger=self.ledger.read_bytes()
        replay=units.put(AGENT,candidate,command=command,ctx=ctx)
        again=units.put(AGENT,candidate,command=command,ctx=ctx)
        self.assertEqual(replay.value,again.value)
        self.assertEqual(replay.value,clean.value)
        self.assertEqual(self.ledger.read_bytes(),ledger)
        self.assertEqual(replay.value['commit'], {'event_ids':[durable.events[-1]['id']],
             'head':durable.head,'sha256':durable.events[-1]['sha256']})
        self.assertEqual(store.verify_projection(AGENT,snapshot=durable,ctx=ctx),())
        # A later unrelated commit cannot change this operation's replay prefix.
        extra=unit_record('Later0001','later memory event',level=2)
        units.put(AGENT,extra,command=self.command(registry,extra,'later-event'),ctx=ctx)
        self.assertEqual(units.put(AGENT,candidate,command=command,ctx=ctx).value,replay.value)

    def test_a30_admission_is_pure_under_lock_and_publication_follows_unlock(self):
        self.publish(); registry,journal,_=self.require_k0()
        units=importlib.import_module('lineage.domain.memory.units')
        locking=importlib.import_module('lineage.core.locking')
        locked=set(); builder_calls=[]; publications=[]
        lock,unlock=locking.lock_exclusive,locking.unlock
        real_build,real_rebuild=entry.build,store.rebuild
        def acquire(fd,*a,**k):
            value=lock(fd,*a,**k); locked.add(fd); return value
        def release(fd,*a,**k):
            value=unlock(fd,*a,**k); locked.discard(fd); return value
        def pure(*a,**k):
            self.assertTrue(locked,'admission builder ran outside the transaction lock'); builder_calls.append(True)
            with mock.patch('builtins.open',side_effect=AssertionError('admission filesystem I/O')), \
                 mock.patch.object(Path,'open',side_effect=AssertionError('admission filesystem I/O')), \
                 mock.patch.object(journal,'transact',side_effect=AssertionError('nested transaction')):
                return real_build(*a,**k)
        def publish(*a,**k):
            self.assertFalse(locked,'projection publication held the ledger lock'); publications.append(True)
            # Rebuild also renders entry outside the ledger lock; instrument only admission.
            with alias_patch(entry,'build',real_build): return real_rebuild(*a,**k)
        candidate=unit_record('Candidate1',level=2); ctx=self.transaction_context()
        with alias_patch(locking,'lock_exclusive',acquire), \
             alias_patch(locking,'unlock',release), \
             alias_patch(entry,'build',pure), \
             alias_patch(store,'rebuild',publish):
            units.put(AGENT,candidate,command=self.command(registry,candidate,'lock-boundary'),ctx=ctx)
        self.assertTrue(builder_calls); self.assertTrue(publications); self.assertFalse(locked)

    def test_a30_concurrent_same_prefix_publications_are_serialized(self):
        self.publish(); prefix=self.snapshot; gate=threading.Barrier(3,timeout=1)
        outcomes=[]
        def rebuild():
            try:
                gate.wait(); outcomes.append(('ok',store.rebuild(AGENT,snapshot=prefix,ctx=self.ctx)))
            except Exception as exc: outcomes.append(('error',exc))
        threads=[threading.Thread(target=rebuild,daemon=True) for _ in range(2)]
        for thread in threads: thread.start()
        gate.wait()
        for thread in threads: thread.join(1)
        self.assertTrue(all(not t.is_alive() for t in threads))
        self.assertEqual(len(outcomes),2); self.assertTrue(any(k=='ok' for k,_ in outcomes))
        for kind,value in outcomes:
            if kind=='error': self.assertIn(getattr(value,'code',None),{'busy','stale_rev'})
        self.assertEqual(store.verify_projection(AGENT,snapshot=prefix,ctx=self.ctx),())

    def test_a21_dispatch_preserves_bootcheck_diagnostic_prefix(self):
        before=self.disk_tree()
        result=self.dispatch('memory_bootcheck',{'agent_id':AGENT,'observed':{}})
        self.assertEqual(result['code'],'bad_args'); self.assertIs(result['ok'],False)
        self.assertTrue(result['detail'].startswith('E_BOOTCHECK'))
        self.assertEqual(self.disk_tree(),before)

    def test_a21_dispatch_missing_observed_uses_bootcheck_prefix(self):
        result=self.dispatch('memory_bootcheck',{'agent_id':AGENT})
        self.assertIs(result['ok'],False); self.assertEqual(result['code'],'bad_args')
        self.assertTrue(result['detail'].startswith('E_BOOTCHECK'))

    def test_b10_operator_read_cannot_create_a_level_one_write(self):
        self.publish(); registry,journal,app=self.require_k0(); ctx=self.transaction_context()
        unit=unit_record('Ruling001','forged operator command',kind='ruling',level=1,actor='operator')
        before=self.ledger.read_bytes()
        result=app.dispatch('memory_put',{'agent_id':AGENT,'unit':unit,'agent':'operator','op_id':'forged-ruling'},ctx=ctx)
        self.assertEqual(result['code'],'forbidden_level'); self.assertIs(result['ok'],False)
        self.assertEqual(self.ledger.read_bytes(),before)

    def test_b10_strict_wire_decoder_rejects_duplicate_nonfinite_and_nul_inputs(self):
        tuple(memory_resume.TOOLS)
        self.require_k0(); schema=importlib.import_module('lineage.core.schema')
        documents=[b'{"observed":{"head":1,"head":2}}', b'{"observed":{"head":NaN}}',
                   b'{"observed":{"head":Infinity}}', b'{"observed":{"head":-Infinity}}',
                   b'{"observed":\x00}',b'{"observed":"\\ud800"}',b'{"observed":"\xff"}']
        for raw in documents:
            self.domain_error('bad_args',lambda raw=raw:schema.decode(raw))

    def test_a27_transport_agreement_without_network_or_child_processes(self):
        # Full real adapter framing with in-memory streams and an HTTP fake socket.
        # No legacy adapter, subprocess, live socket, or fabricated token provenance.
        self.publish(); registry,journal,app=self.require_k0()
        ctx=self.transaction_context(); observed=self.observed()
        wrong=dict(observed,memory_gen=observed['memory_gen']+1)
        calls=[('memory_route',{'agent_id':AGENT,'query':'needle'}),
               ('memory_route',{'agent_id':AGENT,'query':'unmatched'}),
               ('memory_bootcheck',{'agent_id':AGENT,'observed':observed}),
               ('memory_bootcheck',{'agent_id':AGENT,'observed':wrong})]
        baseline=[app.dispatch(name,args,ctx=ctx) for name,args in calls]
        before=self.disk_tree()
        # Explicit endpoint configuration is a test/runtime artifact, never repository data.
        # A-U11: integrated mailbox checks directory/config ownership and write modes.
        family=self.home/'family'/'fixture-target'
        family.parent.mkdir(mode=0o700,exist_ok=True); family.mkdir(mode=0o700,exist_ok=True)
        (family/'config.json').write_bytes(canonical({'endpoint':'fixture-target','sources':['fixture-source'],
            'tools':['memory_route','memory_bootcheck']})+b'\n')
        (family/'config.json').chmod(0o600)
        original_init=registry.Services.__init__; signature=inspect.signature(original_init)
        def injected(instance,*args,**kwargs):
            bound=signature.bind(instance,*args,**kwargs)
            bound.arguments.update(home=self.home,repo_root=self.repo,token_count=Counter())
            original_init(*bound.args,**bound.kwargs)
        def streams(main,argv,raw):
            stdin=io.TextIOWrapper(io.BytesIO(raw),encoding='utf-8')
            out_bytes=io.BytesIO(); stdout=io.TextIOWrapper(out_bytes,encoding='utf-8',write_through=True)
            with mock.patch('sys.stdin',stdin),mock.patch('sys.stdout',stdout),redirect_stderr(io.StringIO()):
                rc=main(argv) if argv is not None else main()
            return rc,out_bytes.getvalue()
        cli=importlib.import_module('lineage.core.cli'); mcp=importlib.import_module('lineage.core.mcp')
        jsonlane=importlib.import_module('lineage.core.jsonlane')
        with mock.patch.object(registry.Services,'__init__',injected), \
             mock.patch('socket.socket',side_effect=AssertionError('transport used live network')):
            for i,(name,args) in enumerate(calls):
                rc,raw=streams(cli.main,['--home',str(self.home),'call',name,'--json',canonical(args).decode()],b'')
                self.assertEqual(json.loads(raw),baseline[i]); self.assertEqual(rc,3 if i==3 else 0)
                envelope={'schema':'lineage.family/1','id':'Request%02d'%i,'source':'fixture-source',
                          'target':'fixture-target','kind':'call','agent':AGENT,'payload':{'tool':name,'args':args}}
                with mock.patch.dict(os.environ,{'LINEAGE_HOME':str(self.home)}):
                    _,raw=streams(jsonlane.main,[],canonical(envelope))
                self.assertEqual(json.loads(raw)['result'],baseline[i])
            requests=[{'jsonrpc':'2.0','id':'init','method':'initialize','params':{'protocolVersion':'2024-11-05',
                       'capabilities':{},'clientInfo':{'name':'fixture','version':'1'}}}]
            requests += [{'jsonrpc':'2.0','id':i,'method':'tools/call','params':{'name':name,'arguments':args}}
                         for i,(name,args) in enumerate(calls)]
            with mock.patch.dict(os.environ,{'LINEAGE_HOME':str(self.home)}):
                _,raw=streams(mcp.main,None,b''.join(canonical(x)+b'\n' for x in requests))
            responses={x['id']:x for x in map(json.loads,raw.splitlines())}
            for i in range(4):
                framed=responses[i]['result']
                self.assertEqual(json.loads(framed['content'][0]['text']),baseline[i])
                self.assertEqual(framed['isError'],i==3)
            self.assertEqual(self.http_results(ctx,calls),baseline)
        # Family config/retention is transport-owned; authoritative and memory bytes remain untouched.
        after=self.disk_tree()
        for path,value in before.items(): self.assertEqual(after[path],value)

    def http_results(self,ctx,calls):
        # A-U11: restore transport-module bindings so later isolated adapter
        # fixtures cannot inherit modules bound to this test's integrated APIs.
        package = importlib.import_module('lineage.serve')
        names = ('http', 'session', 'static', 'fixtures')
        missing = object()
        attributes = {name: getattr(package, name, missing) for name in names}
        modules = {name: sys.modules.get('lineage.serve.' + name, missing) for name in names}
        def restore():
            for name in names:
                if attributes[name] is missing:
                    if hasattr(package, name):
                        delattr(package, name)
                else:
                    setattr(package, name, attributes[name])
                if modules[name] is missing:
                    sys.modules.pop('lineage.serve.' + name, None)
                else:
                    sys.modules['lineage.serve.' + name] = modules[name]
        self.addCleanup(restore)
        http=importlib.import_module('lineage.serve.http'); packets=[]
        class Socket:
            def __init__(self,raw): self.raw=io.BytesIO(raw); self.output=bytearray()
            def makefile(self,*a,**k): return self.raw
            def sendall(self,data): self.output.extend(data)
            def close(self): pass
            def setsockopt(self,*a): pass
            def settimeout(self,*a): pass
            def getsockname(self): return ('127.0.0.1',12345)
        class Server:
            def __init__(self,address,handler,*a,**k):
                self.server_address=('127.0.0.1',12345); self.server_name='127.0.0.1'; self.server_port=12345
                self.handler=handler; self.socket=Socket(b'')
            def __enter__(self): return self
            def __exit__(self,*a): return False
            def server_close(self): pass
            def shutdown(self): pass
            def serve_forever(self,*a,**k):
                for name,args in calls:
                    body=canonical({'tool':name,'args':args})
                    raw=(b'POST /api/call HTTP/1.1\r\nHost: 127.0.0.1:12345\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body)
                    sock=Socket(raw); self.handler(sock,('127.0.0.1',54321),self)
                    packets.append(bytes(sock.output).split(b'\r\n\r\n',1)[1])
        # A-U11: integrated schema.decode takes raw only; adapt HTTP's max_bytes
        # keyword without replacing its strict decoder or changing the byte cap.
        schema = importlib.import_module('lineage.core.schema')
        errors = importlib.import_module('lineage.core.errors')
        def decode(raw, *, max_bytes):
            if len(raw) > max_bytes:
                raise errors.LineageError('bad_args')
            return schema.decode(raw)
        # A-U11: integrated HTTP owns its Context/_Services and forwards a native
        # CallContext to shared dispatch; preserve that real adapter boundary.
        app = importlib.import_module('lineage.core.app')
        call_context = app.create_context(ctx.services.home, registry=ctx.services.registry,
                                          actor=ctx.actor)
        http_ctx = http.Context(http._Services(ctx.services.home, ctx.services.repo_root,
            ctx.services.registry, call_context, ctx.services.repo_root/'ui'/'dist',
            None, io.StringIO()))
        # A-U11: inject the integrated _Server factory; do not mutate HTTPServer's allocator.
        with mock.patch.object(http,'_Server',Server), \
             mock.patch.object(http,'decode',decode), redirect_stderr(io.StringIO()):
            # A-U11: pass the HTTP-owned integrated context constructed above.
            http.serve(ctx=http_ctx,port=0)
        self.assertEqual(len(packets),4)
        return [json.loads(raw) for raw in packets]

    def test_a31_byte_refusal_mutant_causes_assertion_failure(self):
        raw=entry.build(self.agent,[unit_record()],token_count=Counter())
        from tests.memory.store.test_entry import EntryOracle
        case=EntryOracle('test_a02_exact_configured_byte_ceiling')
        with mock.patch.object(entry,'build',return_value=raw):
            self.assert_mutant_assertion(case)

    def test_a31_token_refusal_mutant_causes_assertion_failure(self):
        raw=entry.build(self.agent,[unit_record()],token_count=Counter())
        from tests.memory.store.test_entry import EntryOracle
        case=EntryOracle('test_a02_exact_token_ceiling_and_next_token')
        with mock.patch.object(entry,'build',return_value=raw): self.assert_mutant_assertion(case)

    def test_a31_privacy_mutant_causes_assertion_failure(self):
        route=importlib.import_module('lineage.domain.memory.route')
        with self.reading(): route.route(AGENT,'needle',ctx=self.ctx)
        from tests.memory.store.test_route import RouteOracle
        case=RouteOracle('test_a16_private_inactive_and_scope_mismatches_are_excluded')
        def leak(*args,**kwargs):
            units=sorted((u for u in case.units if u['status']=='active' and u['scope']=={'workflow':'develop','language':'python'}),key=lambda u:u['id'])
            return {'units':units,'answer':units[0]['statement'],'head':case.snapshot.head}
        with mock.patch.object(route,'route',side_effect=leak): self.assert_mutant_assertion(case)

    def test_a31_rank_mutant_causes_assertion_failure(self):
        route=importlib.import_module('lineage.domain.memory.route')
        with self.reading(): route.route(AGENT,'needle',ctx=self.ctx)
        from tests.memory.store.test_route import RouteOracle
        case=RouteOracle('test_a14_coverage_descending_then_lexical_id')
        def wrong_rank(*args,**kwargs):
            units=sorted((u for u in case.units if 'alpha' in u['statement']),key=lambda u:u['id'],reverse=True)
            return {'units':units,'answer':units[0]['statement'],'head':case.snapshot.head}
        with mock.patch.object(route,'route',side_effect=wrong_rank): self.assert_mutant_assertion(case)

    def test_a31_manifest_only_mutant_causes_assertion_failure(self):
        self.publish()
        from tests.memory.store.test_projection_safety import ProjectionSafetyOracle
        case=ProjectionSafetyOracle('test_a12_forged_unit_and_self_consistent_manifest_are_rejected')
        with mock.patch.object(store,'verify_projection',return_value=()): self.assert_mutant_assertion(case)

    def test_a31_missing_evidence_mutant_causes_assertion_failure(self):
        self.publish()
        from tests.memory.store.test_bootcheck import BootcheckOracle
        case=BootcheckOracle('test_a22_receipt_delete')
        with mock.patch.object(bootcheck,'check',return_value={'passed':True,'code':'OK','checks':[{'id':'forged','passed':True}],'head':1}):
            self.assert_mutant_assertion(case)

    def assert_mutant_assertion(self,case):
        result=unittest.TestResult(); case.run(result)
        self.assertFalse(result.errors,'A mutant must be killed by an assertion, not import/stub/setup errors')
        self.assertTrue(result.failures,'The invalid variant left its acceptance assertion green')
        self.assertFalse(result.skipped)


class OracleStructure(unittest.TestCase):
    def test_a32_every_numbered_acceptance_has_an_explicit_mapping(self):
        import re
        oracle=(Path(__file__).parent/'ORACLE.md').read_text()
        mappings=re.findall(r'^\| A(\d+) \| ([^|]+)\|',oracle,re.M)
        self.assertEqual([number for number, _ in mappings],[str(n) for n in range(1,33)])
        for number, cases in mappings:
            identifiers=re.findall(r'`(test_[^`]+)`',cases)
            self.assertTrue(identifiers, 'unmapped acceptance A'+number)
        self.assertIn('Amendment B',oracle)

    def test_a32_imports_are_stdlib_or_project_and_package_discovery_is_closed(self):
        files=list(Path(__file__).parent.glob('*.py'))
        # New authorized oracle modules may join this package without changing a pin.
        self.assertIn('__init__.py',{p.name for p in files})
        self.assertTrue(any(p.name.startswith('test_') for p in files))
        import sys
        for file in files:
            for node in ast.walk(ast.parse(file.read_text())):
                names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                for name in names:
                    self.assertIn(name.split('.')[0],sys.stdlib_module_names|{'lineage','tests'})


def _dispatch_observed(observed):
    def test(self):
        before=self.disk_tree()
        result=self.dispatch('memory_bootcheck',{'agent_id':AGENT,'observed':copy.deepcopy(observed)})
        self.assertEqual(result['code'],'bad_args'); self.assertIs(result['ok'],False)
        self.assertTrue(result['detail'].startswith('E_BOOTCHECK'))
        self.assertEqual(self.disk_tree(),before)
    return test


from tests.memory.store.test_bootcheck import _CASES as _BAD_OBSERVATIONS
for _name,_observed in _BAD_OBSERVATIONS.items():
    setattr(MemoryResumeOracle,'test_a21_dispatch_'+_name,_dispatch_observed(_observed))
