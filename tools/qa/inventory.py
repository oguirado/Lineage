"""Conservative literal source evidence and three-way context comparisons."""
from __future__ import annotations
import re
from pathlib import Path
from .contracts import normalize_name
from .report import check


def _without_comments(text):
    # Preserve strings, remove comments lexically. Dynamic template literals
    # are retained as strings but never resolved into selectors.
    token=re.compile(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)|(//[^\n]*|/\*[\s\S]*?\*/)')
    return token.sub(lambda m:m[1] if m[1] is not None else ' '*len(m[0]),text)


def source_inventory(root: Path, *, contract):
    source=Path(root)/'ui/src';records=[];complete=source.is_dir();issues=[]
    if not complete: issues.append(check('dependency_missing','UI source unavailable.'))
    else:
        for path in sorted(source.rglob('*')):
            if path.suffix not in ('.ts','.tsx','.js','.jsx') or any(p in ('fixtures','__tests__') for p in path.parts) or '.test.' in path.name or '.spec.' in path.name: continue
            if path.is_symlink():
                complete=False;issues.append(check('evidence_missing','Source symlink is not followed.'));continue
            text=_without_comments(path.read_text('utf-8'))
            # A balanced JSX attribute scanner deliberately does not pretend to
            # parse arbitrary JavaScript. Unknown computations remain gaps.
            for m in re.finditer(r'\b(data-lin-[a-z-]+|name)\s*=\s*("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\{[^}]*\})',text):
                key,raw=m.groups()
                if raw.startswith('{'):
                    literal=re.fullmatch(r'\{\s*["\']([^"\']*)["\']\s*\}',raw)
                    value=literal[1] if literal else None
                else: value=raw[1:-1]
                if value is None:
                    complete=False;issues.append(check('evidence_missing','Computed selector is unresolved.'));continue
                records.append(dict(attribute=key,value=value,path=path.relative_to(root).as_posix(),line=text.count('\n',0,m.start())+1))
            # DOM builder APIs and attribute spreads are not JSX literals.
            if re.search(r'\b(?:setAttribute|dataset|createElement)\b|\{\.\.\.',text):
                complete=False;issues.append(check('evidence_missing','DOM builder declarations require runtime corroboration.'))
        if not records:
            complete=False;issues.append(check('evidence_missing','No literal UI vocabulary.'))
    return dict(complete=complete,records=records,checks=issues)


def compare_inventory(documented, source, observed):
    checks=[]
    def contexts(value):
        return {(ctx['route'],ctx['dialog']):ctx for ctx in value.get('contexts',[])}
    expected=contexts(documented)
    for label,value in (('source',source),('observed',observed)):
        if 'contexts' not in value:
            checks.append(check('evidence_missing',label+' context extraction incomplete.',requirement='O2'))
            continue
        actual=contexts(value)
        for key in expected.keys() | actual.keys():
            if key not in expected or key not in actual:
                checks.append(check('inventory_mismatch',label+' context missing or undocumented.',requirement='O2'));continue
            def project(ctx):
                return {(a['action'],a['entity'],a['id'],a['role'],normalize_name(a['name']),a['availability']) for a in ctx['actions']}
            if project(expected[key])!=project(actual[key]): checks.append(check('inventory_mismatch',label+' action set differs.',requirement='O2'))
        if value.get('complete') is False: checks.append(check('evidence_missing',label+' incomplete.',requirement='O2'))
    if not expected: checks.append(check('evidence_missing','No prepared contexts.',requirement='O2'))
    return checks
