"""Frozen specimen integrity and read-only source/document inventory checks.

HTML parsing here checks test data only. It is not a DOM accessibility observer.
"""
import copy
from html.parser import HTMLParser

from tools.qa import contracts, inventory
from tests.operability.test_contract import (OracleCase, CONTRACT_PATH, FIXTURES,
                                            loaded_inventory, walk)


class SpecimenParser(HTMLParser):
    def __init__(self,text):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.controls=[];self.articles=[];self.html={};self.headings=0
        self.feed(text)
    def handle_starttag(self,tag,attrs):
        attributes=dict(attrs)
        if tag=='html': self.html=attributes
        if tag=='h1': self.headings+=1
        if 'data-lin-action' in attributes:
            value=dict(attributes,tag=tag,ancestors=list(self.stack))
            self.controls.append(value)
            if 'article' in self.stack: self.articles.append(value)
        if tag not in ('input','meta','link','br','hr','img','source','wbr'):
            self.stack.append(tag)
    def handle_endtag(self,tag):
        if tag in self.stack:
            self.stack=self.stack[:len(self.stack)-1-self.stack[::-1].index(tag)]


class DOMSpecimenTests(OracleCase):
    def page(self,name):
        return SpecimenParser((FIXTURES/name).read_text('utf-8'))

    def test_a08_good_specimen_has_native_controls_and_no_article(self):
        contracts.normalize_name('Create agent')
        value=self.page('good.html')
        self.assertEqual(value.headings,1)
        self.assertFalse(value.articles)
        self.assertTrue(value.controls)
        self.assertTrue(all(c['tag'] in ('a','button','input','select') for c in value.controls))
        self.assertEqual(value.html['data-lin-rev'],'0')
        self.assertEqual(value.html['data-lin-ready'],'true')

    def test_a09_article_hostile_has_deep_native_essential_button(self):
        contracts.normalize_name('Create agent')
        value=self.page('article-control.html')
        self.assertTrue(any(c['tag']=='button' and c['data-lin-action']=='create-agent'
                            and 'div' in c['ancestors'] for c in value.articles))
        self.assertFalse(self.page('good.html').articles)

    def test_a10_generic_hostile_has_named_and_unnamed_role_variants(self):
        contracts.normalize_name('Create agent')
        value=self.page('clickable-div.html')
        generic=[c for c in value.controls if c['tag']=='div']
        self.assertTrue(any(c.get('role')=='button' for c in generic))
        self.assertTrue(any('role' not in c for c in generic))
        self.assertTrue(all(c.get('tabindex')=='0' for c in generic))

    def test_a11_unicode_hostile_has_normalized_collision(self):
        names=[c.get('aria-label','') for c in self.page('duplicate-names.html').controls
               if c['data-lin-action']=='open-agent']
        self.assertNotEqual(names[0],names[1])
        self.assertEqual(contracts.normalize_name(names[0]),contracts.normalize_name(names[1]))

    def test_a12_overlong_hostile_is_short_in_characters(self):
        name=next(c['aria-label'] for c in self.page('overlong-name.html').controls if c['data-lin-action']=='create-agent')
        normalized=contracts.normalize_name(name)
        self.assertLess(len(normalized),64)
        self.assertGreater(len(normalized.encode('utf-8')),64)

    def test_a07_stale_ready_has_newer_html_revision_than_display(self):
        contracts.normalize_name('Agents ready.')
        text=(FIXTURES/'stale-ready.html').read_text('utf-8')
        self.assertEqual(self.page('stale-ready.html').html['data-lin-rev'],'1')
        self.assertIn('Last confirmed revision 0.',text)

    def test_a26_missing_witness_specimen_only_claims_visible_success(self):
        contracts.normalize_name('Create agent recorded for alpha-root.')
        text=(FIXTURES/'missing-witness.html').read_text('utf-8')
        self.assertIn('Create agent recorded for alpha-root.',text)
        self.assertNotIn('lineage.event/v1',text)


class InventoryTests(OracleCase):
    def source(self,text):
        root=self.scratch();src=root/'ui/src';src.mkdir(parents=True)
        path=src/'Screen.tsx';path.write_text(text,encoding='utf-8')
        before=path.read_bytes()
        value=inventory.source_inventory(root,contract=contracts.load_contract(CONTRACT_PATH))
        self.assertEqual(path.read_bytes(),before)
        return value

    def test_a15_literal_source_values_are_extracted(self):
        value=self.source('export const Screen=()=> <main data-lin-screen="agents"><button type="button" data-lin-action="create-agent">Create agent</button></main>;')
        values=list(walk(value));self.assertIn('create-agent',values);self.assertIn('agents',values)

    def test_a15_comments_are_not_implementation_evidence(self):
        value=self.source('/* <button data-lin-action="invented-comment"/> */\nexport const Screen=()=> <main data-lin-screen="agents">{/* <button data-lin-action="comment-only"/> */}<button type="button" data-lin-action="create-agent">Create agent</button></main>;')
        values=list(walk(value));self.assertIn('create-agent',values)
        self.assertNotIn('invented-comment',values);self.assertNotIn('comment-only',values)

    def test_a15_computed_selector_is_explicitly_incomplete(self):
        value=self.source('export const Screen=({action})=> <button type="button" data-lin-action={action}>Action</button>;')
        records=[v for v in walk(value) if isinstance(v,dict)]
        self.assertTrue(any(v.get('complete') is False or v.get('status')=='INCONCLUSIVE' for v in records),value)

    def test_a15_static_form_names_are_extracted(self):
        value=self.source('export const Form=()=> <input name="agent_id" data-lin-action="edit-field" aria-label="Create Agent ID"/>;')
        self.assertIn('agent_id',list(walk(value)))

    def test_a15_matching_prepared_context_has_no_mismatch(self):
        value=loaded_inventory()
        self.assertEqual(inventory.compare_inventory(copy.deepcopy(value),copy.deepcopy(value),copy.deepcopy(value)),[])

    def test_a15_missing_required_applicable_action_is_mismatch(self):
        value=loaded_inventory();observed=copy.deepcopy(value)
        observed['contexts'][0]['actions']=[a for a in observed['contexts'][0]['actions'] if a['action']!='create-agent']
        result=inventory.compare_inventory(value,copy.deepcopy(value),observed)
        self.assertTrue(result)
        self.assertTrue(any(v.get('status')=='FAIL' for v in walk(result) if isinstance(v,dict)))

    def test_a15_undocumented_runtime_action_is_mismatch(self):
        value=loaded_inventory();observed=copy.deepcopy(value)
        observed['contexts'][0]['actions'].append(dict(observed['contexts'][0]['actions'][0],action='invented-action'))
        result=inventory.compare_inventory(value,copy.deepcopy(value),observed)
        self.assertTrue(any(v.get('status')=='FAIL' for v in walk(result) if isinstance(v,dict)))

    def test_a15_changed_native_role_is_mismatch(self):
        value=loaded_inventory();observed=copy.deepcopy(value)
        next(a for a in observed['contexts'][0]['actions'] if a['action']=='create-agent')['role']='generic'
        result=inventory.compare_inventory(value,copy.deepcopy(value),observed)
        self.assertTrue(any(v.get('status')=='FAIL' for v in walk(result) if isinstance(v,dict)))

    def test_a01_a30_absent_source_is_not_complete_screen_coverage(self):
        value=inventory.source_inventory(self.scratch(),contract=contracts.load_contract(CONTRACT_PATH))
        records=[v for v in walk(value) if isinstance(v,dict)]
        self.assertTrue(any(v.get('complete') is False or v.get('status')=='INCONCLUSIVE' for v in records),value)
