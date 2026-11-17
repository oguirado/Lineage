"""Owned pipe-only browser observation; no existing browser attachment."""
from __future__ import annotations
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlsplit, parse_qsl
from .cdp_pipe import PipeClient,PipeError
from .contracts import (STATES, canonical, decode, identity_key, load_contract,
                        normalize_name, positive, role_for, validate_inventory)
from .report import check,context_for,emit,make_report


DOM_SNAPSHOT = r'''(() => {
 const exposed=e=>!!e.getClientRects().length && getComputedStyle(e).visibility!=='hidden'
    && !e.closest('[inert],[hidden],dialog:not([open])');
 const all=[...document.querySelectorAll('*')];
 const rect=e=>{let r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}};
 return {url:location.href,ready:document.documentElement.getAttribute('data-lin-ready'),
 revision:document.documentElement.getAttribute('data-lin-rev'),
 screen:document.querySelector('main[data-lin-screen]')?.getAttribute('data-lin-screen')||null,
 title:document.title,lang:document.documentElement.lang,
 text:document.querySelector('main')?.innerText||'',
 h1:[...document.querySelectorAll('h1')].filter(exposed).map(e=>e.textContent),
 banner:document.querySelectorAll('header,[role="banner"]').length,
 main:document.querySelectorAll('main#main-content[tabindex="-1"]').length,
 primary:document.querySelectorAll('nav[aria-label="Primary"]').length,
 status:[...document.querySelectorAll('[role="status"]')].map(e=>({name:e.getAttribute('aria-label'),text:e.textContent})),
 width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,
 theme:document.documentElement.getAttribute('data-theme'),reduced:matchMedia('(prefers-reduced-motion:reduce)').matches,
 nodes:all.map((e,index)=>{const c=getComputedStyle(e),entity=e.closest('[data-lin-entity]');
 return {index,tag:e.localName,action:e.getAttribute('data-lin-action'),name:e.getAttribute('name'),
 exposed:exposed(e),article:!!e.closest('article'),role:e.getAttribute('role'),
 focusable:e.tabIndex>=0,onclick:e.hasAttribute('onclick')||typeof e.onclick==='function',
 type:e.getAttribute('type'),href:e.getAttribute('href'),disabled:!!e.disabled,
 entity:entity?.getAttribute('data-lin-entity')||null,id:entity?.getAttribute('data-lin-id')||null,
 description:(e.getAttribute('aria-describedby')||'').split(/\s+/).map(id=>document.getElementById(id)?.textContent||'').join(' '),
 rect:rect(e),color:c.color,background:c.backgroundColor,fontSize:c.fontSize,
 states:Object.fromEntries(['busy','checked','current','disabled','expanded','hidden','pressed','selected'].map(s=>[s,e.getAttribute('aria-'+s)]))}})};
})()'''



def _nested_userns_flags():
    """Chrome cannot build its own sandbox inside an unprivileged nested user
    namespace (the R44 test sandbox: unshare --user --pid). Only there, the
    headless loopback observer with a disposable profile runs --no-sandbox."""
    try:
        line=open('/proc/self/uid_map').read().split()
        nested=line[:3]!=['0','0','4294967295']
    except OSError:
        nested=False
    return ['--no-sandbox'] if nested else []

def _url(value):
    parsed=urlsplit(value)
    try:
        allowed=parsed.scheme in ('http','https') and parsed.hostname is not None and ipaddress.ip_address(parsed.hostname).is_loopback
        parsed.port
    except ValueError: allowed=False
    if not allowed or parsed.username is not None or parsed.password is not None:
        raise ValueError('bad_config: loopback URL required')
    return (parsed.scheme,parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80))


def _eval(client,session,expression):
    value=client.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True},session_id=session)
    if 'exceptionDetails' in value: raise PipeError('probe_internal')
    result=value.get('result',{})
    if 'value' not in result: raise PipeError('incomplete_tree')
    return result['value']


def _elements(root):
    result=[]
    def walk(node):
        if node.get('nodeType')==1: result.append(node)
        for child in node.get('children',[]): walk(child)
    walk(root)
    return result


def _origin_guard(client,session,origin):
    current=_eval(client,session,'location.href')
    if _url(current)!=origin: raise PipeError('wrong_target')
    return current


def _keyboard(client,session,key,code,virtual):
    for event in ('keyDown','keyUp'):
        client.call('Input.dispatchKeyEvent',dict(type=event,key=key,code=code,windowsVirtualKeyCode=virtual),session_id=session)


def _inspect(snapshot, ax, elements, inventory, contract):
    checks=[];observed=[]
    if len(elements)!=len(snapshot['nodes']):
        return [check('incomplete_tree','DOM changed during observation.')],[]
    ax_by_backend={n.get('backendDOMNodeId'):n for n in ax if not n.get('ignored')}
    names=set()
    for e,dom in zip(elements,snapshot['nodes']):
        if e['nodeName'].lower()!=dom['tag']:
            checks.append(check('incomplete_tree','DOM handle association changed.'));continue
        if not dom['exposed']: continue
        raw_ax=ax_by_backend.get(e['backendNodeId'])
        actionable=bool(dom['action']) or dom['onclick'] or (dom['focusable'] and dom['tag'] not in ('main','h1','dialog'))
        if actionable and dom['tag'] not in ('button','a','input','select'):
            checks.append(check('non_native_control',requirement='O4'))
        if actionable and dom['article']: checks.append(check('article_control',requirement='O1'))
        if not dom['action']: continue
        if raw_ax is None:
            checks.append(check('incomplete_tree','Computed accessibility node unavailable.',requirement='O3'));continue
        name=normalize_name(raw_ax.get('name',{}).get('value',''));role=raw_ax.get('role',{}).get('value','generic')
        if name in names: checks.append(check('duplicate_name',requirement='O3'))
        names.add(name)
        if not name: checks.append(check('missing_control','Unnamed exposed action.',requirement='O3'))
        if len(name.encode())>64: checks.append(check('name_too_long',requirement='O3'))
        definition=contract['actions'].get(dom['action'])
        if not definition: checks.append(check('inventory_mismatch','Undocumented action.',requirement='O2'))
        elif role not in ({role_for(definition['element'])} if dom['action']!='edit-field' else {'textbox','combobox','checkbox','spinbutton'}):
            checks.append(check('inventory_mismatch','Computed role differs from documented element.',requirement='O4'))
        if dom['tag']=='button' and dom['type']!=('submit' if dom['action']=='submit-dialog' else 'button'):
            checks.append(check('non_native_control','Button form behavior is undeclared.',requirement='O4'))
        if dom['entity'] and dom['id']:
            key=identity_key(dom['entity'],dom['id'])
            if key not in name: checks.append(check('identity_key_mismatch',requirement='O3'))
            if dom['id'] not in dom['description']: checks.append(check('identity_key_mismatch','Full identity missing from description.',requirement='O3'))
        observed.append(dict(action=dom['action'],entity=dom['entity'],id=dom['id'],role=role,name=name,
                             disabled=dom['disabled'],backend=e['backendNodeId']))
    if len(snapshot['h1'])!=1 or snapshot['banner']!=1 or snapshot['main']!=1 or snapshot['primary']!=1:
        checks.append(check('semantic_mismatch','Required shell landmarks or unique heading missing.',requirement='O5'))
    if len(snapshot['status'])!=1 or snapshot['status'][0]['name']!='Application updates':
        checks.append(check('announcement_mismatch',requirement='O8'))
    skip=[n for n in snapshot['nodes'] if n['action']=='skip-main' and n['exposed']]
    if len(skip)!=1 or skip[0]['href']!='#main-content': checks.append(check('focus_mismatch','Skip destination missing.',requirement='O5'))
    contexts=[c for c in inventory['contexts'] if c['screen']==snapshot['screen'] and c['dialog'] is None]
    if not contexts: checks.append(check('wrong_target','No prepared context for active screen.'));return checks,observed
    ctx=contexts[0];head=ctx['head'];revision=snapshot['revision']
    if (snapshot['ready']!='true' or head is None or revision!=str(head) or
        not re.fullmatch(r'0|[1-9][0-9]*',revision or '') or
        ('Last confirmed revision ' in snapshot['text'] and 'Last confirmed revision '+str(head)+'.' not in snapshot['text'])):
        checks.append(check('stale_ready',requirement='O9'))
    for action in ctx['actions']:
        matches=[o for o in observed if (o['action'],o['entity'],o['id'])==(action['action'],action['entity'],action['id'])]
        if action['availability']=='absent':
            if matches: checks.append(check('inventory_mismatch','Expected absent action exposed.',requirement='O2'))
            continue
        if len(matches)!=1: checks.append(check('missing_control',requirement='O4'));continue
        found=matches[0]
        if (found['role'],found['name'])!=(action['role'],normalize_name(action['name'])) or found['disabled']!=(action['availability']=='disabled'):
            checks.append(check('inventory_mismatch','Role, name or availability mismatch.',requirement='O2'))
    if snapshot['overflow']: checks.append(check('layout_mismatch','Document horizontal overflow.',requirement='O12'))
    return checks,observed


def _save_artifact(root,kind,value):
    from .evidence import _artifact_root,_artifact_bytes
    raw=canonical(json.loads(json.dumps(value,ensure_ascii=False,allow_nan=False)));digest=hashlib.sha256(raw).hexdigest();ref=kind+'-'+digest+'.json'
    directory=_artifact_root(root)
    try:
        try: fd=os.open(ref,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
        except FileExistsError:
            if _artifact_bytes(root,ref)!=raw: raise ValueError('evidence_mismatch')
        else:
            with os.fdopen(fd,'wb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.fsync(directory)
    finally: os.close(directory)
    return dict(ref=ref,sha256=digest,kind=kind,hash_basis='canonical_json')


def probe(*, url, browser, inventory, contract, timeout_ms):
    context=context_for();scope='selftest';checks=[];artifacts=[];client=None;profile_resource=None
    try:
        origin=_url(url);positive(timeout_ms);validate_inventory(inventory,contract=contract)
        context=context_for(inventory,contract);scope=inventory['scope']
        if not Path(browser).is_file() or not os.access(browser,os.X_OK):
            checks.append(check('observer_unavailable','Browser executable unavailable.'))
        else:
            profile_resource=tempfile.TemporaryDirectory(prefix='lineage-cdp-')
            profile=profile_resource.name
            client=PipeClient([str(browser),*_nested_userns_flags(),'--headless=new','--no-first-run','--no-default-browser-check',
                               '--disable-background-networking','--disable-extensions','--force-renderer-accessibility',
                               '--user-data-dir='+profile,'about:blank'],timeout_ms=timeout_ms)
            client.start()
            client.call('Target.setAutoAttach',{'autoAttach':True,'waitForDebuggerOnStart':False,'flatten':True})
            target=client.call('Target.createTarget',{'url':'about:blank'})['targetId']
            session=client.call('Target.attachToTarget',{'targetId':target,'flatten':True})['sessionId']
            for method in ('Page.enable','Runtime.enable','DOM.enable','Accessibility.enable','Network.enable'):
                client.call(method,{},session_id=session)
            # Intercept every navigation/network request before dispatch.
            # The observer never follows a redirect to another origin.
            def navigation_event(event):
                if event['method']!='Fetch.requestPaused': return
                if event.get('sessionId')!=session: raise PipeError('wrong_target')
                request=event['params'];request_url=request['request']['url']
                if request_url.startswith(('data:','about:','blob:')):
                    safe=request.get('resourceType')!='Document'
                else:
                    try: safe=_url(request_url)==origin
                    except ValueError: safe=False
                client.call('Fetch.continueRequest' if safe else 'Fetch.failRequest',
                            {'requestId':request['requestId'],**({} if safe else {'errorReason':'BlockedByClient'})},session_id=session)
                if not safe and request.get('resourceType')=='Document': raise PipeError('wrong_target')
            client.on_event=navigation_event
            client.call('Fetch.enable',{'patterns':[{'urlPattern':'*','requestStage':'Request'}]},session_id=session)
            client.call('Page.navigate',{'url':url},session_id=session)
            deadline=time.monotonic()+timeout_ms/1000;snapshot=None
            while time.monotonic()<deadline:
                current=_eval(client,session,'location.href')
                if current=='about:blank': continue
                if _url(current)!=origin: raise PipeError('wrong_target')
                snapshot=_eval(client,session,DOM_SNAPSHOT)
                if snapshot['ready']=='true': break
            if snapshot is None: raise PipeError('deadline')
            current=_origin_guard(client,session,origin)
            if (urlsplit(current).path,urlsplit(current).query,urlsplit(current).fragment)!=(urlsplit(url).path,urlsplit(url).query,urlsplit(url).fragment): raise PipeError('wrong_target')
            dom=client.call('DOM.getDocument',{'depth':-1,'pierce':False},session_id=session)['root']
            ax=client.call('Accessibility.getFullAXTree',{},session_id=session)['nodes']
            findings,observed=_inspect(snapshot,ax,_elements(dom),inventory,contract);checks.extend(findings)
            # Resolve every prepared selector against the same document.
            for ctx in inventory['contexts']:
                if ctx['screen']!=snapshot['screen'] or ctx['dialog'] is not None: continue
                for action in ctx['actions']:
                    match=client.call('DOM.querySelectorAll',{'nodeId':dom['nodeId'],'selector':action['selector']},session_id=session)['nodeIds']
                    if action['availability']!='absent' and len(match)!=1: checks.append(check('invalid_selector',requirement='O2'))
            for event in client.events:
                if event['method']=='Runtime.exceptionThrown' or (event['method']=='Runtime.consoleAPICalled' and event.get('params',{}).get('type') in ('error','assert')):
                    checks.append(check('unexpected_console','Browser reported an exception or console error.'))
            context.update(head=int(snapshot['revision']) if re.fullmatch(r'0|[1-9][0-9]*',snapshot['revision'] or '') else None,
                           viewport={'width':snapshot['width'],'height':snapshot['height']},reduced_motion=snapshot['reduced'],
                           owner_ref='owned-cdp')
            # Keyboard activation uses Input events. Tab to the exposed
            # skip link, activate it, and prove focus with route stability.
            active=None
            for _ in range(len(observed)+1 if not any(c['status']=='FAIL' for c in checks) else 0):
                _keyboard(client,session,'Tab','Tab',9)
                active=_eval(client,session,"document.activeElement?.getAttribute('data-lin-action')")
                if active=='skip-main': break
            if active=='skip-main':
                _keyboard(client,session,'Enter','Enter',13)
                if _eval(client,session,"document.activeElement?.id")!='main-content' or _origin_guard(client,session,origin)!=current:
                    checks.append(check('focus_mismatch',requirement='O7'))
            elif not any(c['status']=='FAIL' for c in checks): checks.append(check('focus_mismatch','Skip link is not keyboard reachable.',requirement='O7'))
            artifact_root=os.environ.get('LINEAGE_QA_ARTIFACT_ROOT')
            if artifact_root:
                root=Path(artifact_root)
                if root.is_symlink() or not root.is_dir(): raise ValueError('bad_config')
                # Raw DOM has session token metadata; retain structural DOM
                # snapshot instead, which never samples that metadata.
                artifacts.extend([_save_artifact(root,'dom',snapshot),_save_artifact(root,'cdp_ax',ax)])
            else: checks.append(check('evidence_missing','Caller-selected artifact directory required.'))
            if scope!='selftest':
                checks.append(check('evidence_missing','Full route/dialog keyboard, rendering matrix and authoritative live witnesses are unexecuted.'))
            client.close();client=None
    except (ValueError,TypeError): checks.append(check('bad_config','Invalid browser probe configuration.'))
    except PipeError as error: checks.append(check(error.code,'Pipe observation unavailable.'))
    except OSError: checks.append(check('observer_unavailable'))
    except Exception: checks.append(check('probe_internal'))
    finally:
        if client is not None:
            try: client.close()
            except Exception: checks.append(check('cleanup_incomplete'))
        if profile_resource is not None:
            try: profile_resource.cleanup()
            except OSError: checks.append(check('cleanup_incomplete'))
    if not checks: checks=[check()]
    return make_report(method='C',scope=scope,checks=checks,artifacts=artifacts,context=context)


def screen_ready_name(url):
    """Map a public hash route to its fixed AX completion name."""
    from urllib.parse import unquote
    parts=urlsplit(url).fragment.split('?',1)[0].strip('/').split('/')
    screen=parts[0] or 'agents'
    if screen=='agents' and len(parts)==2:
        screen='agent '+identity_key('agent',unquote(parts[1]))
    elif screen=='arena' and len(parts)==2:
        screen='arena '+identity_key('bench',unquote(parts[1]))
    return 'Screen '+screen+' ready'


def owned_page(browser, url, timeout_ms):
    """Own one private headless browser; never attach to an operator browser."""
    from contextlib import contextmanager
    @contextmanager
    def opened():
        _url(url);positive(timeout_ms)
        with tempfile.TemporaryDirectory(prefix='lineage-ax-') as profile:
            client=PipeClient([str(browser),*_nested_userns_flags(),'--headless=new','--no-first-run',
                '--no-default-browser-check','--disable-background-networking',
                '--disable-extensions','--force-renderer-accessibility',
                '--user-data-dir='+profile,'about:blank'],timeout_ms=timeout_ms)
            try:
                client.start()
                target=client.call('Target.createTarget',{'url':'about:blank'})['targetId']
                session=client.call('Target.attachToTarget',{'targetId':target,'flatten':True})['sessionId']
                for method in ('Page.enable','Runtime.enable','Accessibility.enable'):
                    client.call(method,{},session_id=session)
                client.call('Page.navigate',{'url':url},session_id=session)
                yield client,session
            finally:
                client.close()
    return opened()


def wait_ready(client, session, url, timeout_ms):
    """Completion depends only on pruned roles, names, states and quiet hashes."""
    import select
    from .ax_prune import prune, tree_hash
    deadline=time.monotonic()+timeout_ms/1000;previous=None;quiet=0
    while time.monotonic()<deadline:
        nodes=prune(client.call('Accessibility.getFullAXTree',{},session_id=session)['nodes'])
        ready=any(n['role']=='status' and n['name']==screen_ready_name(url) for n in nodes)
        busy=any(n['role']=='progressbar' or dict(n['attrs']).get('busy')=='true' for n in nodes)
        digest=tree_hash(nodes)
        quiet=quiet+1 if ready and not busy and digest==previous else 0
        if quiet>=2:
            return nodes
        previous=digest
        select.select([],[],[],min(0.05,max(0,deadline-time.monotonic())))
    error=PipeError('deadline')
    error.nodes=nodes
    raise error


def viewpoint_probe(*, url, browser, timeout_ms, artifact_root=None):
    from .ax_prune import violations
    checks=[];artifacts=[];context=context_for()
    try:
        with owned_page(browser,url,timeout_ms) as (client,session):
            nodes=wait_ready(client,session,url,timeout_ms)
            current=_origin_guard(client,session,_url(url))
            # Only the URL is sampled outside AX. A session credential is never a route.
            parsed=urlsplit(current)
            credential_keys={'token','session','session_token','lineage-session-token'}
            queries=(parsed.query,parsed.fragment.partition('?')[2])
            if any(key.casefold() in credential_keys for query in queries for key,_ in parse_qsl(query)):
                checks.append(check('unsafe_content','Session credentials must not be in the URL.'))
            for failure in violations(nodes,screen_ready_name(url)):
                if failure=='missing_current_navigation':
                    checks.append(check('incomplete_tree','Chrome omits aria-current from the CDP full AX response; current navigation state cannot be proven through the pruned tree.'))
                else:
                    checks.append(check('semantic_mismatch',failure))
            if artifact_root is not None:
                artifacts.append(_save_artifact(Path(artifact_root),'pruned',nodes))
            context['owner_ref']='owned-cdp'
    except PipeError as error:
        checks.append(check(error.code,'AX completion unavailable: '+error.code))
    except (ValueError,TypeError):
        checks.append(check('bad_config','Invalid AX probe input.'))
    except OSError:
        checks.append(check('observer_unavailable','Browser executable or pipe unavailable.'))
    return make_report(method='C',scope='selftest',checks=checks or [check()],artifacts=artifacts,context=context)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self,message):
        raise ValueError('bad_config')


def _parser(description):
    parser=_ArgumentParser(description=description)
    parser.add_argument('--url',required=True);parser.add_argument('--browser',required=True,type=Path)
    parser.add_argument('--inventory',type=Path);parser.add_argument('--contract',type=Path)
    parser.add_argument('--viewpoint',action='store_true');parser.add_argument('--artifacts',type=Path)
    parser.add_argument('--timeout-ms',required=True,type=int)
    return parser


def main(argv=None):
    try:
        args=_parser(__doc__).parse_args(argv)
        if args.viewpoint:
            result=viewpoint_probe(url=args.url,browser=args.browser,timeout_ms=args.timeout_ms,artifact_root=args.artifacts)
        else:
            if args.inventory is None or args.contract is None: raise ValueError('bad_config')
            result=probe(url=args.url,browser=args.browser,inventory=decode(args.inventory.read_bytes()),
                         contract=load_contract(args.contract),timeout_ms=args.timeout_ms)
    except (ValueError,TypeError,OSError):
        result=make_report(method='C',scope='selftest',checks=[check('bad_config','Invalid probe input.')],artifacts=[],context=context_for())
    return emit(result,write=lambda b:sys.stdout.write(b.decode('utf-8')))

if __name__=='__main__': raise SystemExit(main())
