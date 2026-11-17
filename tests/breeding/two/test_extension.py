"""Closed discovery, inputs, source membership and shared transports: A1-A4."""
from copy import deepcopy
import inspect
import io
import json
from pathlib import Path

from lineage.core import app, cli, mcp, registry
from lineage.domain.breeding import cross, mutate, specialize
from lineage.ext import breeding2

from .helpers import ACTOR, HERE, ROOT, TOOLS, OracleCase, arguments, canonical, frozen_schema


class ExtensionTests(OracleCase):
    def test_a01_exact_domain_signatures_and_importable_surface(self):
        expected={cross.cross:["parent_ids","child_id","display_name","command","ctx"],
                  mutate.mutate:["parent_id","child_id","change","display_name","command","ctx"],
                  specialize.specialize:["parent_id","child_id","language","display_name","command","ctx"]}
        for function,names in expected.items():
            with self.subTest(function=function.__name__):
                actual=inspect.signature(function)
                self.assertEqual(list(actual.parameters),names)
                for name in ("display_name","command","ctx"):
                    self.assertEqual(actual.parameters[name].kind,inspect.Parameter.KEYWORD_ONLY)
                self.assertIsNone(actual.parameters["display_name"].default)
        self.assertTrue((HERE/"__init__.py").is_file())
        self.assertTrue((HERE.parent/"__init__.py").is_file())
        self.module("lineage.domain.breeding.inherit")
        self.module("lineage.domain.agents")

    def test_a04_registry_has_exact_tools_no_duplicate_validator_or_fold(self):
        r=self.runtime()
        self.assertEqual({t.name for t in breeding2.TOOLS},set(TOOLS))
        self.assertEqual(len(breeding2.TOOLS),len(TOOLS))
        self.assertEqual(breeding2.VALIDATORS,{})
        self.assertEqual(breeding2.FOLDS,{})
        for tool in TOOLS:
            self.assertTrue(r.tools[tool].mutating)
            self.assertEqual(r.tools[tool].input_schema,frozen_schema(tool))
        self.assertIn("agent.born",r.validators,"HOLD: shared U12 validator is AUSENTE")

    def test_a02_missing_actor_and_operation_identity_reject(self):
        self.parents()
        for tool in TOOLS:
            for key in ("agent","op_id"):
                with self.subTest(tool=tool,key=key):
                    args=arguments(tool);del args[key]
                    self.reject("bad_args",tool,args=args)

    def test_a02_null_name_boolean_head_unknown_top_level_and_claimed_gates(self):
        self.parents()
        for tool in TOOLS:
            for extra in ({"display_name":None},{"expected_head":True},{"unknown":1},
                          {"inherited_units":[]},{"status":"promoted"},{"gate":{"passed":True}},
                          {"fitness":1},{"authority":"operator"}):
                with self.subTest(tool=tool,extra=extra):
                    self.reject("bad_args",tool,args=arguments(tool,**extra))

    def test_a02_nested_skill_change_unknown_keys_and_mixed_branches(self):
        self.parent()
        change=arguments("agent_mutate")["change"]
        for bad in (dict(change,action="replace"),dict(change,text="add"),[change],
                    dict(change,to=dict(change["to"],second_pin=change["to"])),
                    {"kind":"rule","rule_id":"I1","text":"remove","skill_id":"some-skill"}):
            with self.subTest(change=bad):
                self.reject("bad_args","agent_mutate",change=bad)

    def test_a02_blank_or_control_display_names_reject(self):
        self.parents()
        for name in ("", " ","\t","name\nrole=orchestrate","name\r","name\x00","name\x1f","name\x7f"):
            with self.subTest(display_name=name):
                self.reject("bad_args",display_name=name)

    def test_a02_shared_strict_cli_rejects_duplicate_keys_and_bad_unicode(self):
        self.parents()
        for raw in ('{"agent":"creator-agent","agent":"operator"}',
                    '{"display_name":"\\ud800"}',
                    '{"change":{"kind":"rule","text":"add","text":"remove"}}'):
            with self.subTest(raw=raw):
                output=io.StringIO();err=io.StringIO()
                before=self.ledger_bytes()
                code=cli.main(["--home",str(self.home),"call","agent_cross","--json",raw],
                              stdout=output,stderr=err,registry=self.reg)
                self.assertEqual(code,2)
                self.assertEqual(json.loads(output.getvalue())["code"],"bad_args")
                self.assertEqual(before,self.ledger_bytes())

    def test_a03_missing_parent_and_source_ownership(self):
        self.parent()
        self.reject("no_agent",parent_ids=["parent-one","missing-parent"])
        self.reject("bad_args",inherited_units=[{"source_agent_id":"unrelated-agent"}])

    def test_a03_existing_child_and_self_parent_are_conflict(self):
        self.parents()
        self.reject("conflict",child_id="parent-one")
        self.op()
        self.reject("conflict",op_id="distinct-operation")

    def test_a03_reserved_children_and_duplicate_parents_reject(self):
        self.parents()
        for child in ("operator","system","Upper-case","ab","valid-id\n","x"*65):
            with self.subTest(child=child):
                self.reject("bad_args",child_id=child)
        self.reject("bad_args",parent_ids=["parent-one","parent-one"])

    def test_a03_actor_is_same_user_assertion_without_parent_membership(self):
        self.parents()
        self.parent("retired-creator");self.retire("retired-creator")
        for n,actor in enumerate((ACTOR,"operator","system","unregistered-creator","retired-creator")):
            with self.subTest(actor=actor):
                data=self.op(agent=actor,child_id="actor-child-"+str(n),op_id="actor-op-"+str(n))
                event=self.witness(data)
                self.assertEqual(event["agent"],actor)
                self.assertEqual(data["record"]["status"],"draft")
                self.assertTrue(all(w["unit"]["level"]==2 for w in data["inherited_units"]))

    def test_a04_cli_and_mcp_replay_exact_inner_result_and_one_wrapper(self):
        self.parents()
        args=arguments("agent_cross")
        data=self.op()
        expected={"untrusted":data}
        output=io.StringIO()
        code=cli.main(["--home",str(self.home),"call","agent_cross","--json",canonical(args).decode()],
                      stdout=output,stderr=io.StringIO(),registry=self.reg)
        self.assertEqual(code,0);self.assertEqual(json.loads(output.getvalue()),expected)
        request={"jsonrpc":"2.0","id":"oracle-call","method":"tools/call",
                 "params":{"name":"agent_cross","arguments":args}}
        output=io.StringIO()
        mcp.main(context=self.context,registry=self.reg,stdin=io.BytesIO(canonical(request)+b"\n"),
                 stdout=output,stderr=io.StringIO())
        rpc=json.loads(output.getvalue())
        self.assertFalse(rpc["result"]["isError"])
        self.assertEqual(json.loads(rpc["result"]["content"][0]["text"]),expected)
        self.assertEqual(len([e for e in self.history() if e["payload"].get("record",{}).get("agent_id")=="child-agent"]),1)

    def test_a04_json_lane_uses_computed_identity_and_shared_policy(self):
        self.parents()
        lane=self.module("lineage.core.jsonlane")
        wire=self.module("lineage.core.envelope")
        args=arguments("agent_cross");args.pop("agent");args.pop("op_id")
        envelope={"schema":"lineage.family/1","id":"request_0001","source":"source","target":"target",
                  "kind":"call","agent":ACTOR,"payload":{"tool":"agent_cross","args":args}}
        config={"endpoint":"target","sources":["source"],"tools":["agent_cross"]}
        endpoint=self.home/"family/target"
        # A-U18: mailbox admission requires private control directories/files.
        endpoint.mkdir(parents=True,mode=0o700)
        endpoint.parent.chmod(0o700)
        (endpoint/"config.json").write_bytes(canonical(config)+b"\n")
        (endpoint/"config.json").chmod(0o600)
        result=lane.dispatch(envelope,config,ctx=self.context)
        expected=self.success("agent_cross",dict(args,agent=ACTOR,op_id=wire.operation_id(envelope)))
        self.assertEqual(result,{"untrusted":expected})
        self.witness(expected)

    def test_a01_selector_and_shared_validator_are_real_admission_witnesses(self):
        self.parents()
        inherit=self.module("lineage.domain.breeding.inherit")
        from .helpers import seam
        from unittest import mock
        selector=mock.Mock(wraps=inherit.select)
        validator=mock.Mock(wraps=self.reg.validators["agent.born"])
        # Rebuild immutable registry/context with an instrumented real callback;
        # never replace it with a permissive test validator.
        validators=dict(self.reg.validators);validators["agent.born"]=validator
        self.reg=registry.Registry(self.reg.tools,validators,self.reg.folds)
        self.context=app.create_context(self.home,registry=self.reg)
        with seam(inherit,"select",selector):
            data=self.op()
        self.witness(data)
        self.assertGreaterEqual(selector.call_count,1)
        self.assertGreaterEqual(validator.call_count,1)
        for call in selector.call_args_list:
            self.assertIsNone(call.kwargs["selected_ids"])

    def test_a04_real_http_handler_replays_shared_result_without_network(self):
        from email.message import Message
        from types import SimpleNamespace
        self.parents()
        expected={"untrusted":self.op()}
        http=self.module("lineage.serve.http")
        services=http._Services(self.home,ROOT,self.reg,self.context,ROOT/"ui/dist",io.StringIO(),io.StringIO())
        server=SimpleNamespace(ctx=http.Context(services),fixture_data=None,token="fixture-session-token",
                               authority="127.0.0.1:8000")
        body=canonical({"tool":"agent_cross","args":arguments("agent_cross")})
        handler=http._Handler.__new__(http._Handler)
        handler.server=server;handler.command="POST";handler.path="/api/call"
        handler.request_version="HTTP/1.1";handler.requestline="POST /api/call HTTP/1.1"
        # A-U18: the integrated router reads the raw request target.
        handler.raw_requestline=b"POST /api/call HTTP/1.1\r\n"
        handler.rfile=io.BytesIO(body);handler.wfile=io.BytesIO();handler.headers=Message()
        for key,value in {"Host":server.authority,"Origin":"http://"+server.authority,
                          "X-Lineage-Session":server.token,"Content-Type":"application/json",
                          "Content-Length":str(len(body))}.items():handler.headers[key]=value
        handler._handle()
        raw=handler.wfile.getvalue()
        head,response=raw.split(b"\r\n\r\n",1)
        self.assertIn(b" 200 ",head.split(b"\r\n",1)[0])
        self.assertEqual(json.loads(response),expected)
