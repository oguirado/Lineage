"""Independent native accessibility traversal and private-session probe."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
from .contracts import STATES, canonical, decode, load_contract, normalize_name, positive, validate_inventory
from .report import check, context_for, emit, make_report

ROLE_MAP={'push button':'button','document web':'document','document frame':'document',
          'entry':'textbox','text':'text','static':'text','check box':'checkbox',
          'combo box':'combobox','list item':'listitem','section':'group',
          'panel':'group','label':'text','frame':'group','application':'group',
          'desktop':'group','landmark':'group','paragraph':'text','image':'img'}
# ViewPoint native chassis mapping, with semantic web roles retained from
# AT-SPI xml-roles. The upstream native map omits live-region roles.
ATSPI_ROLE_MAP = {
    'push button':'button', 'toggle button':'button', 'check box':'checkbox',
    'radio button':'radio', 'text':'textbox', 'entry':'textbox',
    'combo box':'combobox', 'list':'listbox', 'list item':'option',
    'menu bar':'menubar', 'menu':'menu', 'menu item':'menuitem',
    'page tab list':'tablist', 'page tab':'tab', 'slider':'slider',
    'spin button':'spinbutton', 'tool bar':'toolbar', 'dialog':'dialog',
    'heading':'heading', 'link':'link', 'frame':'application', 'window':'application',
    'status bar':'status', 'notification':'status', 'alert':'alert',
}
RAW_OBSERVATIONS={}
LAST_NATIVE_REASON=''


def native_prune(observation, raw):
    from .ax_prune import CHASSIS_ROLES, STATE_ATTRS, normalize_name
    owned={n['id'] for n in observation['nodes']}
    result=[];depths={};opaque=set()
    for node in raw:
        if node['id'] not in owned:
            continue
        if node['parent'] in opaque:
            opaque.add(node['id']);continue
        attributes=node['attributes']
        semantic=next((r for r in attributes.get('xml-roles','').split() if r in CHASSIS_ROLES),None)
        role=semantic or ATSPI_ROLE_MAP.get(node['role'])
        depth=depths.get(node['parent'],0)
        depths[node['id']]=depth
        if role is None:
            continue
        states={key:'true' for key in node['states'] if key in STATE_ATTRS}
        for key in STATE_ATTRS:
            if attributes.get(key) in ('true','false','page','mixed'):
                states[key]=attributes[key]
        if attributes.get('current'):
            states['current']=attributes['current']
        result.append(dict(role=role,name=normalize_name(node['name']),depth=depth,
                           attrs=tuple((k,states[k]) for k in STATE_ATTRS if k in states)))
        depths[node['id']]=depth+1
        if role=='article':
            opaque.add(node['id'])
    return result



def _role(node):
    raw=node.get_role_name().lower()
    return raw,ROLE_MAP.get(raw,raw)


def _owned_pid(pid,browser_pid):
    if pid==browser_pid: return True
    # Renderer processes may own the native document. Verify ancestry against
    # the recorded browser, without using or signalling unrelated processes.
    visited=set()
    while type(pid) is int and pid>1 and pid not in visited:
        visited.add(pid)
        try:
            text=(Path(os.sep)/'proc'/str(pid)/'stat').read_text()
            pid=int(text[text.rfind(')')+2:].split()[1])
        except (OSError,ValueError,IndexError): return False
        if pid==browser_pid: return True
    return False


def observe(*, browser_pid, desktop, timeout_ms, node_limit):
    global LAST_NATIVE_REASON
    LAST_NATIVE_REASON=''
    positive(timeout_ms);positive(node_limit);positive(browser_pid)
    deadline=time.monotonic()+timeout_ms/1000;seen=set();raw=[];nodes=[]
    complete=True;truncated=False;document_found=False;document_children=0
    stack=[(desktop,None,False)];objects=[]
    while stack:
        if time.monotonic()>=deadline or len(seen)>=node_limit:
            complete=False;truncated=True;LAST_NATIVE_REASON='Traversal deadline reached.' if time.monotonic()>=deadline else 'Native node limit reached.';break
        current,parent,in_document=stack.pop()
        handle=id(current)
        if handle in seen:
            complete=False;truncated=True;LAST_NATIVE_REASON='Repeated native accessible encountered.';continue
        seen.add(handle);objects.append(current)
        operation='get_role_name/get_process_id'
        try:
            raw_role,role=_role(current);pid=current.get_process_id()
            if role=='document':
                if not _owned_pid(pid,browser_pid): continue
                document_found=True;in_document=True
            record_id='n'+str(len(raw))
            operation='get_name';name=current.get_name() or ''
            operation='get_state_set';state_set=current.get_state_set().get_states()
            raw_states=[s if isinstance(s,str) else getattr(s,'value_nick',str(s)) for s in state_set]
            states=[]
            for state in raw_states:
                token=state.lower().replace('atspi_state_','').replace('-','_')
                if token in STATES and token not in states: states.append(token)
            try:
                action_iface=current.get_action_iface();count=action_iface.get_n_actions()
                action_names=[action_iface.get_action_name(j) for j in range(count)]
            except (AttributeError,NotImplementedError): action_names=[]
            operation='get_attributes';attributes=current.get_attributes()
            if isinstance(attributes,list): attributes=dict(a.split(':',1) for a in attributes if isinstance(a,str) and ':' in a)
            if not isinstance(attributes,dict): attributes={}
            raw.append(dict(id=record_id,parent=parent,role=raw_role,name=name,states=raw_states,actions=action_names,pid=pid,attributes=attributes))
            if in_document:
                entity=attributes.get('data-lin-entity');entity_id=attributes.get('data-lin-id')
                if bool(entity)!=bool(entity_id): complete=False;entity=entity_id=None
                nodes.append(dict(id=record_id,parent=parent if parent in {n['id'] for n in nodes} else None,
                                  role=role,name=normalize_name(name),states=states,actionable=bool(action_names),
                                  entity=entity,entity_id=entity_id,action=attributes.get('data-lin-action')))
                if role!='document': document_children+=1
            operation='get_child_count';children=current.get_child_count()
            for index in reversed(range(children)):
                try:
                    child=current.get_child_at_index(index)
                    if child is None: complete=False;truncated=True;LAST_NATIVE_REASON='Native child lookup returned no accessible.'
                    else: stack.append((child,record_id,in_document))
                except Exception as error: complete=False;truncated=True;LAST_NATIVE_REASON='Native get_child_at_index failed: '+type(error).__name__+'.'
        except Exception as error:
            complete=False;truncated=True;LAST_NATIVE_REASON='Native '+operation+' failed: '+type(error).__name__+'.'
    raw_ref='native-'+hashlib.sha256(canonical(raw)).hexdigest()
    RAW_OBSERVATIONS.clear();RAW_OBSERVATIONS[raw_ref]=raw
    return dict(nodes=nodes,complete=complete and document_found and document_children>0,
                truncated=truncated,document_found=document_found,
                owner_ref='native-owner-'+hashlib.sha256(str(browser_pid).encode()).hexdigest() if document_found else None,raw_ref=raw_ref)


def _reap(process,timeout):
    if process.poll() is None:
        if process.pid<=1: raise RuntimeError('cleanup_incomplete')
        process.terminate()
        try: process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                if process.pid<=1: raise RuntimeError('cleanup_incomplete')
                process.kill()
            process.wait(timeout=timeout)
    for stream in (process.stdout,process.stderr):
        if stream is not None: stream.close()


def _line(stream, deadline):
    data=b''
    while not data.endswith(b'\n'):
        left=deadline-time.monotonic()
        if left<=0 or not select.select([stream],[],[],left)[0]: raise TimeoutError()
        part=os.read(stream.fileno(),1)
        if not part or len(data)>4096: raise RuntimeError('observer_unavailable')
        data+=part
    return data.decode().strip()


def _probe(*, url, browser, xvfb, session_bus, inventory=None, contract=None, timeout_ms, node_limit, viewpoint=False, artifact_root=None, expected_buttons=()):
    from .cdp_probe import _url
    checks=[];context=context_for();scope='selftest';owned=[];observation=None;artifacts=[];profile_resource=None
    try:
        positive(timeout_ms);positive(node_limit);_url(url)
        if not viewpoint:
            validate_inventory(inventory,contract=contract);scope=inventory['scope'];context=context_for(inventory,contract)
        if any(not Path(p).is_file() or not os.access(p,os.X_OK) for p in (browser,xvfb,session_bus)):
            checks.append(check('observer_unavailable','Native session executables unavailable.'))
        elif Path(session_bus).name!='dbus-daemon':
            checks.append(check('bad_config','Session bus executable must provide the documented dbus-daemon foreground contract.'))
        else:
            # Refuse before spawning if the native import cannot be supplied.
            import importlib.util
            if importlib.util.find_spec('gi') is None:
                checks.append(check('observer_unavailable','Python GI module unavailable; AT-SPI observation cannot start.'))
            else:
                deadline=time.monotonic()+timeout_ms/1000
                profile_resource=tempfile.TemporaryDirectory(prefix='lineage-native-')
                profile=profile_resource.name
                display_r,display_w=os.pipe()
                try:
                    display=subprocess.Popen([str(xvfb),'-displayfd',str(display_w),'-screen','0','1440x900x24','-nolisten','tcp'],pass_fds=(display_w,),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    owned.append(display);os.close(display_w);display_w=None
                    with os.fdopen(display_r,'rb',buffering=0) as stream: display_number=_line(stream,deadline)
                    display_r=None
                finally:
                    if display_w is not None: os.close(display_w)
                    if display_r is not None:
                        try: os.close(display_r)
                        except OSError: pass
                if not display_number.isdecimal(): raise ValueError('bad_config')
                bus=subprocess.Popen([str(session_bus),'--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
                owned.append(bus);address=_line(bus.stdout,deadline)
                env=dict(os.environ,DISPLAY=':'+display_number,DBUS_SESSION_BUS_ADDRESS=address,NO_AT_BRIDGE='0',GTK_A11Y='always',GDK_BACKEND='x11')
                for inherited in ('AT_SPI_BUS_ADDRESS','DBUS_STARTER_ADDRESS','DBUS_STARTER_BUS_TYPE','WAYLAND_DISPLAY'):
                    env.pop(inherited,None)
                # New interpreter isolates GI's process-global bus connection.
                program=('import sys; from tools.qa.atspi_probe import _native_worker; '
                         '_native_worker(sys.argv[1:])')
                browser_process=subprocess.Popen([str(browser),'--ozone-platform=x11','--force-renderer-accessibility','--no-first-run','--user-data-dir='+profile,url],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                owned.append(browser_process)
                worker=subprocess.Popen([sys.executable,'-c',program,str(browser_process.pid),str(max(1,timeout_ms-1000)),str(node_limit),url if viewpoint else ''],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
                owned.append(worker)
                output,_=worker.communicate(timeout=max(0.001,deadline-time.monotonic()))
                from .cdp_pipe import _decode_frame
                if len(output)>4194304: raise RuntimeError('native_observation_too_large')
                worker_data=_decode_frame(output)
                if worker_data.get('error'):
                    checks.append(check('observer_unavailable',worker_data['error']))
                    return make_report(method='A',scope=scope,checks=checks,artifacts=[],context=context)
                observation=worker_data['observation']
                raw_native=worker_data['raw']
                if viewpoint:
                    from .cdp_probe import screen_ready_name
                    nodes=native_prune(observation,raw_native)
                    if not observation['document_found']:
                        checks.append(check('no_document','Private session AT-SPI registry exposed no document owned by the launched Chrome process.'))
                    elif not observation['complete'] or not nodes:
                        checks.append(check('incomplete_tree' if observation['truncated'] else 'empty_tree',
                            worker_data.get('diagnostic') or ('Owned Chrome document contains no mapped native accessibility nodes.' if not nodes else 'Native enumeration did not complete.')))
                    else:
                        seen={(n['role'],n['name']) for n in nodes}
                        required=[('status',screen_ready_name(url)),*[('button',n) for n in expected_buttons]]
                        for role,name in required:
                            if (role,name) not in seen and not (role=='button' and ('link',name) in seen):
                                checks.append(check('missing_control',f'Native AX missing {role}: {name}',requirement='O4'))
                        if any(n['role']=='progressbar' for n in nodes):
                            checks.append(check('stale_ready','Native AX still exposes a progressbar.'))
                    if artifact_root is not None:
                        from .cdp_probe import _save_artifact
                        artifacts.append(_save_artifact(Path(artifact_root),'pruned',nodes))
                else:
                    from .contracts import schema,validate_shape
                    validate_shape(observation,schema('report')['$defs']['observation'])
                    if not observation['document_found']: checks.append(check('no_document','Owned browser document absent from the private AT-SPI registry.'))
                    elif not observation['complete']: checks.append(check('incomplete_tree' if observation['truncated'] else 'empty_tree','Owned document has no complete native accessibility tree.'))
                    else:
                        required=[a for c in inventory['contexts'] for a in c['actions'] if a['availability']!='absent']
                        seen={(n['role'],n['name']) for n in observation['nodes']}
                        for a in required:
                            if (a['role'],normalize_name(a['name'])) not in seen: checks.append(check('missing_control',requirement='O4'))
                        checks.append(check('evidence_missing','Native action journey and retained raw artifacts required.'))
                context['owner_ref']=observation['owner_ref']
                artifact_root=os.environ.get('LINEAGE_QA_ARTIFACT_ROOT')
                if artifact_root:
                    from .cdp_probe import _save_artifact
                    root=Path(artifact_root)
                    if root.is_symlink() or not root.is_dir(): raise ValueError('bad_config')
                    artifacts.append(_save_artifact(root,'atspi_raw',raw_native))
                elif not viewpoint: checks.append(check('evidence_missing','Durable raw native artifact required.'))
                for process in reversed(owned): _reap(process,timeout_ms/1000)
                owned.clear()
    except (ValueError,TypeError): checks.append(check('bad_config','Invalid native probe configuration.'))
    except (TimeoutError,subprocess.TimeoutExpired): checks.append(check('deadline','Private Xvfb/dbus/Chrome accessibility observation exceeded the deadline.'))
    except (OSError,ImportError,RuntimeError) as error: checks.append(check('observer_unavailable','Native session setup or observation failed: '+type(error).__name__))
    except Exception: checks.append(check('probe_internal'))
    finally:
        for process in reversed(owned):
            try: _reap(process,timeout_ms/1000)
            except Exception: checks.append(check('cleanup_incomplete'))
            for stream in (process.stdout,process.stderr):
                if stream is not None: stream.close()
        if profile_resource is not None:
            try: profile_resource.cleanup()
            except OSError: checks.append(check('cleanup_incomplete'))
    return make_report(method='A',scope=scope,checks=checks or [check() if viewpoint else check('evidence_missing')],artifacts=artifacts,context=context)


def probe(*, url, browser, xvfb, session_bus, inventory, contract, timeout_ms, node_limit):
    """Preserve the frozen inventory-probe API."""
    return _probe(url=url,browser=browser,xvfb=xvfb,session_bus=session_bus,
                  inventory=inventory,contract=contract,timeout_ms=timeout_ms,node_limit=node_limit)


def viewpoint_probe(*, url, browser, xvfb, session_bus, timeout_ms, node_limit,
                    artifact_root=None, expected_buttons=()):
    return _probe(url=url,browser=browser,xvfb=xvfb,session_bus=session_bus,
                  timeout_ms=timeout_ms,node_limit=node_limit,viewpoint=True,
                  artifact_root=artifact_root,expected_buttons=expected_buttons)


def _native_worker(args):
    browser_pid,timeout,limit=map(int,args[:3]);url=args[3] if len(args)>3 else ''
    try:
        import gi
        gi.require_version('Atspi','2.0')
        from gi.repository import Atspi
    except (ImportError,ValueError) as error:
        sys.stdout.buffer.write(canonical({'error':'AT-SPI GI namespace unavailable: '+type(error).__name__}))
        return
    deadline=time.monotonic()+timeout/1000;result=None;previous=None;quiet=0
    from .ax_prune import canonical_tree
    from .cdp_probe import screen_ready_name
    while time.monotonic()<deadline:
        result=observe(browser_pid=browser_pid,desktop=Atspi.get_desktop(0),timeout_ms=max(1,int((deadline-time.monotonic())*1000)),node_limit=limit)
        if not url and result['document_found']: break
        raw=RAW_OBSERVATIONS.get(result['raw_ref'],[])
        nodes=native_prune(result,raw)
        ready=any(n['role']=='status' and n['name']==screen_ready_name(url) for n in nodes)
        snapshot=canonical_tree(nodes)
        quiet=quiet+1 if ready and snapshot==previous else 0
        if quiet>=2: break
        previous=snapshot
        select.select([],[],[],min(0.05,max(0,deadline-time.monotonic())))
    sys.stdout.buffer.write(canonical({'observation':result,'raw':RAW_OBSERVATIONS.get(result['raw_ref'],[]),'diagnostic':LAST_NATIVE_REASON}))


def main(argv=None):
    from .cdp_probe import _parser
    parser=_parser('Native AT-SPI probe')
    parser.add_argument('--xvfb',required=True,type=Path);parser.add_argument('--session-bus',required=True,type=Path)
    parser.add_argument('--node-limit',required=True,type=int)
    parser.add_argument('--expect-button',action='append',default=[])
    try:
        args=parser.parse_args(argv)
        if args.viewpoint:
            result=viewpoint_probe(url=args.url,browser=args.browser,xvfb=args.xvfb,session_bus=args.session_bus,
                                  timeout_ms=args.timeout_ms,node_limit=args.node_limit,artifact_root=args.artifacts,
                                  expected_buttons=args.expect_button)
        else:
            if args.inventory is None or args.contract is None: raise ValueError('bad_config')
            result=probe(url=args.url,browser=args.browser,xvfb=args.xvfb,session_bus=args.session_bus,
                         inventory=decode(args.inventory.read_bytes()),contract=load_contract(args.contract),
                         timeout_ms=args.timeout_ms,node_limit=args.node_limit)
    except (ValueError,TypeError,OSError):
        result=make_report(method='A',scope='selftest',checks=[check('bad_config')],artifacts=[],context=context_for())
    return emit(result,write=lambda b:sys.stdout.write(b.decode()))

if __name__=='__main__': raise SystemExit(main())
