"""Real inherited pipes with a deterministic offline fake Chromium child.

No process groups, network sockets or sleep calls are used. Child descriptors
follow Chromium's protocol: commands on descriptor 3, responses on descriptor 4.
"""
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from tools.qa.cdp_pipe import PipeClient
from tests.operability.test_contract import OracleCase, walk


CHILD = r'''
import json, os, sys
mode=sys.argv[1]
buffer=b''
while True:
    chunk=os.read(3,4096)
    if not chunk: break
    buffer+=chunk
    while b'\0' in buffer:
        frame,buffer=buffer.split(b'\0',1)
        request=json.loads(frame)
        if mode=='eof': sys.exit(0)
        if mode=='stall': continue
        if mode=='malformed':
            os.write(4,b'{broken\0'); continue
        response={'id':request['id'],'result':{'marker':'echo-ok','params':request.get('params',{}),'argv':sys.argv[2:]}}
        if 'sessionId' in request: response['sessionId']=request['sessionId']
        if mode=='wrong-id': response['id']+=1000
        if mode=='wrong-session': response['sessionId']='other-session'
        if mode=='protocol-error':
            response.pop('result');response['error']={'code':-32601,'message':'Unsupported method'}
        event={'method':'Runtime.consoleAPICalled','params':{'type':'log','args':[]}}
        if 'sessionId' in request: event['sessionId']=request['sessionId']
        data=json.dumps(event).encode()+b'\0'+json.dumps(response).encode()+b'\0'
        if mode=='fragmented':
            for byte in data: os.write(4,bytes([byte]))
        else: os.write(4,data)
'''


class PipeTests(OracleCase):
    def owned(self, mode='normal', timeout_ms=150, extra=()):
        processes=[]
        original=subprocess.Popen
        def record(*args, **kwargs):
            process=original(*args, **kwargs)
            self.assertGreater(process.pid,1)
            processes.append(process)
            self.addCleanup(self.reap,process)
            return process
        # Patching the standard subprocess constructor tracks only children
        # created by this invocation; it does not prescribe transport internals.
        scope=patch('subprocess.Popen',side_effect=record)
        scope.start();self.addCleanup(scope.stop)
        client=PipeClient([sys.executable,'-u','-c',CHILD,mode,*extra],timeout_ms=timeout_ms)
        self.addCleanup(client.close)
        client.start()
        return client,processes

    @staticmethod
    def reap(process):
        if process.poll() is None:
            if process.stdin is not None: process.stdin.close()
            try:
                process.wait(timeout=0.3)
            except subprocess.TimeoutExpired:
                if process.pid <= 1: raise AssertionError('Unsafe child identity')
                process.terminate()
                try: process.wait(timeout=0.3)
                except subprocess.TimeoutExpired:
                    if process.pid <= 1: raise AssertionError('Unsafe child identity')
                    process.kill();process.wait(timeout=0.3)
        for stream in (process.stdin,process.stdout,process.stderr):
            if stream is not None: stream.close()

    def echo(self, client, session=None):
        return client.call('Test.echo',{'text':'é'},session_id=session)

    def test_a05_fragmented_nul_frames_and_interleaved_events(self):
        client,_=self.owned('fragmented')
        value=self.echo(client,'page-session')
        self.assertIn('echo-ok',list(walk(value)))
        self.assertIn('é',list(walk(value)))
        second=self.echo(client,'page-session')
        self.assertIn('echo-ok',list(walk(second)))

    def test_a05_response_session_and_request_ids_are_correlated(self):
        client,_=self.owned()
        for session in (None,'page-session','another-page-session'):
            self.assertIn('echo-ok',list(walk(self.echo(client,session))))

    def test_a05_no_debugging_port_fallback(self):
        client,_=self.owned()
        response=self.echo(client)
        strings=[v for v in walk(response) if isinstance(v,str)]
        self.assertIn('--remote-debugging-pipe',strings)
        self.assertFalse(any(v.startswith('--remote-debugging-port') for v in strings))

    def test_a05_a33_close_reaps_only_owned_child(self):
        client,children=self.owned()
        self.echo(client)
        self.assertTrue(children,'Owned child was not observable')
        client.close()
        for process in children:
            self.assertIsNotNone(process.poll(),'Owned child survived close')
        client.close()  # Cleanup is idempotent.

    def test_a33_unrelated_sentinel_survives_transport_cleanup(self):
        sentinel=subprocess.Popen([sys.executable,'-c','import sys; sys.stdin.buffer.read()'],stdin=subprocess.PIPE)
        self.assertGreater(sentinel.pid,1)
        self.addCleanup(self.reap,sentinel)
        client,_=self.owned()
        self.echo(client);client.close()
        self.assertIsNone(sentinel.poll())

    def test_a33_shell_text_is_an_argument_and_never_executed(self):
        marker=self.scratch()/'sentinel'
        client,_=self.owned(extra=('$(touch '+str(marker)+')',))
        self.assertIn('echo-ok',list(walk(self.echo(client))))
        client.close();self.assertFalse(marker.exists())


def refusal_test(mode):
    def test(self):
        client,_=self.owned(mode,timeout_ms=80)
        try:
            reply=self.echo(client,'page-session')
        except NotImplementedError:
            raise
        except (ValueError,TypeError,OSError,RuntimeError):
            client.close()
            return
        self.assertIsInstance(reply,dict)
        self.assertNotIn('echo-ok',list(walk(reply)))
        self.assertTrue(any(isinstance(v,dict) and
                            ('error' in v or 'code' in v or
                             v.get('status') in ('FAIL','INCONCLUSIVE'))
                            for v in walk(reply)),reply)
        client.close()
    return test


for mode in ('wrong-id','wrong-session','malformed','eof','stall','protocol-error'):
    setattr(PipeTests,'test_a05_refuse_'+mode.replace('-','_'),refusal_test(mode))


def invalid_timeout_test(value):
    def test(self):
        self.reject(PipeClient,[sys.executable,'-u','-c',CHILD,'normal'],timeout_ms=value)
    return test


for label,value in (('zero',0),('negative',-1),('boolean',True),('fractional',1.5)):
    setattr(PipeTests,'test_a33_invalid_timeout_'+label,invalid_timeout_test(value))
