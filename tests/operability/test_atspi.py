"""Offline native traversal specimens, independent of CDP and DOM."""
import copy
from types import SimpleNamespace
from unittest.mock import patch

from tools.qa import atspi_probe
from tests.operability.test_contract import OracleCase, walk

OWNER_PID = 42420  # Synthetic association; no process with this number is signalled.


class Accessible:
    """Minimal fake of the public AT-SPI Accessible interfaces."""
    def __init__(self, role, name='', children=(), pid=OWNER_PID, states=(), broken=False):
        self.role=role;self.name=name;self.children=list(children);self.pid=pid
        self.states=list(states);self.broken=broken;self.parent=None
        for child in self.children: child.parent=self

    @property
    def child_count(self): return len(self.children)
    def get_child_count(self): return len(self.children)
    def get_child_at_index(self,index):
        if self.broken: raise RuntimeError('Unavailable child')
        return self.children[index]
    def get_parent(self): return self.parent
    def get_role_name(self): return self.role
    def get_localized_role_name(self): return self.role
    def get_role(self):
        return SimpleNamespace(value_nick=self.role.replace(' ','-'),value_name='ATSPI_ROLE_'+self.role.upper().replace(' ','_'))
    def get_name(self): return self.name
    def get_description(self): return self.name
    def get_process_id(self): return self.pid
    def get_state_set(self):
        return SimpleNamespace(get_states=lambda:list(self.states))
    def get_attributes(self): return []
    def get_action_iface(self): return self
    def query_action(self): return self
    def get_n_actions(self): return 1 if self.role=='push button' else 0
    def get_action_name(self,index): return 'click'
    def do_action(self,index): self.states.append('checked');return True
    def get_component_iface(self): return self
    def grab_focus(self): return True


def desktop(*children):
    return Accessible('desktop','',children,pid=0)


def associated_document(*children):
    document=Accessible('document web','Lineage · Agents',children)
    return desktop(Accessible('application','Owned browser',[document]))


class NativeTests(OracleCase):
    def observe(self,tree,limit=50):
        return atspi_probe.observe(browser_pid=OWNER_PID,desktop=tree,
                                   timeout_ms=150,node_limit=limit)

    def test_a08_a21_complete_associated_document_has_native_names(self):
        tree=associated_document(Accessible('heading','Agents'),
                                 Accessible('push button','Create agent'))
        observation=self.observe(tree)
        self.assertEqual(set(observation),{'nodes','complete','truncated','document_found','owner_ref','raw_ref'})
        self.assertTrue(observation['complete'])
        self.assertTrue(observation['document_found'])
        self.assertFalse(observation['truncated'])
        self.assertIsNotNone(observation['owner_ref'])
        self.assertIn(('button','Create agent'),
                      {(n['role'],n['name']) for n in observation['nodes']})

    def test_a06_another_browser_document_is_not_associated(self):
        tree=desktop(Accessible('application','Other browser',[
            Accessible('document web','Other document',[Accessible('push button','Create agent',pid=OWNER_PID+1)],pid=OWNER_PID+1)],pid=OWNER_PID+1))
        result=self.observe(tree)
        self.assertFalse(result['document_found'])
        self.assertFalse(result['complete'])

    def test_a21_browser_only_root_is_not_a_document(self):
        value=self.observe(desktop(Accessible('application','Owned browser')))
        self.assertFalse(value['document_found'])
        self.assertFalse(value['complete'])

    def test_a21_no_document_is_incomplete(self):
        value=self.observe(desktop())
        self.assertFalse(value['document_found'])
        self.assertFalse(value['complete'])

    def test_a21_empty_document_is_not_complete_success(self):
        value=self.observe(associated_document())
        self.assertTrue(value['document_found'])
        self.assertFalse(value['complete'])

    def test_a22_node_limit_marks_truncation(self):
        tree=associated_document(*[Accessible('push button','Action '+str(n)) for n in range(8)])
        value=self.observe(tree,limit=2)
        self.assertFalse(value['complete'])
        self.assertTrue(value['truncated'])

    def test_a22_unreadable_child_marks_incomplete(self):
        tree=associated_document(Accessible('group','',[Accessible('push button','Create agent')],broken=True))
        self.assertFalse(self.observe(tree)['complete'])

    def test_a22_cycle_is_bounded_and_incomplete(self):
        child=Accessible('group','Cycle');child.children=[child]
        value=self.observe(associated_document(child))
        self.assertFalse(value['complete'])

    def test_a12_raw_platform_flags_are_not_invented_product_states(self):
        tree=associated_document(Accessible('push button','Create agent',states=['focusable','sensitive','enabled']))
        value=self.observe(tree)
        self.assertTrue(value['complete'])
        admitted={'busy','checked','current','disabled','expanded','hidden','pressed','selected'}
        for item in value['nodes']:
            self.assertLessEqual(set(item['states']),admitted)

    def test_a21_tree_traversal_does_not_consult_cdp(self):
        with patch('tools.qa.cdp_pipe.PipeClient',side_effect=AssertionError('Native traversal used CDP')):
            value=self.observe(associated_document(Accessible('push button','Create agent')))
        self.assertTrue(value['complete'])

    def test_a22_raw_static_text_not_falsely_reported_missing(self):
        value=self.observe(associated_document(Accessible('static','Readable constitution'),Accessible('push button','Create agent')))
        # Raw retention is an external artifact obligation. This observation
        # must still be complete if a canonical view omits static text.
        self.assertTrue(value['complete'])
        self.assertTrue(value['document_found'])


def invalid_limit_test(field,value):
    def test(self):
        args=dict(browser_pid=OWNER_PID,desktop=associated_document(),timeout_ms=100,node_limit=50)
        args[field]=value
        self.reject(atspi_probe.observe,**args)
    return test


for field in ('timeout_ms','node_limit'):
    for label,value in (('zero',0),('negative',-1),('boolean',True),('fractional',1.5)):
        setattr(NativeTests,'test_a33_'+field+'_'+label,invalid_limit_test(field,value))
