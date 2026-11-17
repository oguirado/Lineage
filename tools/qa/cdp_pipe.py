"""Owned Chromium inherited-pipe transport, with bounded NUL framing."""
from __future__ import annotations
import fcntl
import json
import math
import os
import select
import subprocess
import sys
import threading
import time
from .contracts import canonical, positive


def _decode_frame(raw):
    """Browser frames have their own bound, independent of journal JSON limits."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate_key')
            result[key] = value
        return result
    def number(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError('non_finite')
        return value
    def constant(_):
        raise ValueError('non_finite')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                       parse_float=number, parse_constant=constant)
    # Refuse unpaired surrogate escapes as well as invalid UTF-8 input.
    json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
    return value


class PipeError(RuntimeError):
    """Public diagnostic only; raw protocol data stays private."""
    def __init__(self, code):
        self.code=code
        super().__init__(code)


class PipeClient:
    def __init__(self, argv, *, timeout_ms):
        self.timeout_ms=positive(timeout_ms)
        if isinstance(argv,(str,bytes)) or not argv or any(type(x) is not str or '\0' in x for x in argv):
            raise ValueError('bad_config')
        if any(x.startswith('--remote-debugging-port') for x in argv): raise ValueError('bad_config')
        self.argv=list(argv)
        if '--remote-debugging-pipe' not in self.argv: self.argv.append('--remote-debugging-pipe')
        self.process=None;self.writer=None;self.reader=None;self.buffer=b'';self.events=[]
        self.sequence=0;self.lock=threading.RLock()
        self.pending={};self.responses={};self.on_event=None

    def start(self):
        if self.process is not None: raise PipeError('bad_config')
        owned=[]
        try:
            read_cmd,write_cmd=os.pipe();owned.extend((read_cmd,write_cmd))
            read_resp,write_resp=os.pipe();owned.extend((read_resp,write_resp))
            # High descriptor copies avoid clashes with 3/4. Remapping in an
            # exec trampoline avoids unsafe preexec_fn in a threaded host.
            cmd=fcntl.fcntl(read_cmd,fcntl.F_DUPFD_CLOEXEC,10);owned.append(cmd)
            resp=fcntl.fcntl(write_resp,fcntl.F_DUPFD_CLOEXEC,10);owned.append(resp)
            launcher=('import os,sys; a=int(sys.argv[1]); b=int(sys.argv[2]); '
                      'os.dup2(a,3,inheritable=True); os.dup2(b,4,inheritable=True); '
                      'os.close(a); os.close(b); os.execvpe(sys.argv[3],sys.argv[3:],os.environ)')
            self.process=subprocess.Popen([sys.executable,'-c',launcher,str(cmd),str(resp),*self.argv],
                                          pass_fds=(cmd,resp),stdin=subprocess.DEVNULL,
                                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if self.process.pid<=1: raise PipeError('observer_unavailable')
            self.writer=write_cmd;self.reader=read_resp
            os.set_blocking(self.writer,False);os.set_blocking(self.reader,False)
            owned.remove(write_cmd);owned.remove(read_resp)
        except Exception:
            self.close();raise
        finally:
            for fd in owned: os.close(fd)

    def _remaining(self,deadline):
        remaining=deadline-time.monotonic()
        if remaining<=0: raise PipeError('deadline')
        return remaining

    def _frame(self,deadline):
        self._remaining(deadline)
        while b'\0' not in self.buffer:
            if self.reader is None: raise PipeError('observer_unavailable')
            ready,_,_=select.select([self.reader],[],[],self._remaining(deadline))
            if not ready: raise PipeError('deadline')
            chunk=os.read(self.reader,65536)
            if not chunk: raise PipeError('observer_unavailable')
            self.buffer+=chunk
            if len(self.buffer)>1048576: raise PipeError('probe_internal')
        frame,self.buffer=self.buffer.split(b'\0',1)
        try:
            value=_decode_frame(frame)
        except (ValueError,TypeError,RecursionError): raise PipeError('probe_internal') from None
        if not isinstance(value,dict): raise PipeError('probe_internal')
        return value

    def call(self, method, params, *, session_id=None):
        if type(method) is not str or not method or type(params) is not dict or (session_id is not None and (type(session_id) is not str or not session_id)):
            raise ValueError('bad_config')
        with self.lock:
            if self.process is None or self.writer is None: raise PipeError('observer_unavailable')
            deadline=time.monotonic()+self.timeout_ms/1000
            self.sequence+=1;request_id=self.sequence
            self.pending[request_id]=session_id
            request=dict(id=request_id,method=method,params=params)
            if session_id is not None: request['sessionId']=session_id
            data=canonical(request)+b'\0'
            try:
                while data:
                    _,ready,_=select.select([],[self.writer],[],self._remaining(deadline))
                    if not ready: raise PipeError('deadline')
                    n=os.write(self.writer,data);data=data[n:]
                while request_id not in self.responses:
                    response=self._frame(deadline)
                    if 'id' not in response:
                        if not isinstance(response.get('method'),str): raise PipeError('probe_internal')
                        if len(self.events)>=10000: raise PipeError('incomplete_tree')
                        self.events.append(response)
                        if self.on_event is not None: self.on_event(response)
                        continue
                    reply_id=response['id']
                    if (type(reply_id) is not int or reply_id not in self.pending or
                            response.get('sessionId')!=self.pending[reply_id] or reply_id in self.responses):
                        raise PipeError('wrong_target')
                    self.responses[reply_id]=response
                response=self.responses.pop(request_id)
                del self.pending[request_id]
                if 'error' in response: raise PipeError('probe_internal')
                if not isinstance(response.get('result'),dict): raise PipeError('probe_internal')
                return response['result']
            except (ValueError,OSError) as exc:
                raise PipeError('observer_unavailable') from None

    def close(self):
        if self.process is not None and self.process.poll() is None and self.writer is not None:
            try:
                self.call('Browser.close', {})
                self.process.wait(timeout=min(2, self.timeout_ms/1000))
            except (PipeError, OSError, subprocess.TimeoutExpired):
                pass
        failed=False
        for attr in ('writer','reader'):
            fd=getattr(self,attr)
            setattr(self,attr,None)
            if fd is not None:
                try: os.close(fd)
                except OSError: failed=True
        process=self.process
        if process is not None:
            try:
                if process.poll() is None:
                    if process.pid<=1: raise PipeError('cleanup_incomplete')
                    process.terminate()
                try: process.wait(timeout=self.timeout_ms/1000)
                except subprocess.TimeoutExpired:
                    if process.poll() is None:
                        if process.pid<=1: raise PipeError('cleanup_incomplete')
                        process.kill()
                    process.wait(timeout=self.timeout_ms/1000)
            except (OSError,subprocess.TimeoutExpired): failed=True
        self.buffer=b'';self.pending.clear();self.responses.clear()
        if failed: raise PipeError('cleanup_incomplete')
