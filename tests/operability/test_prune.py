"""Independent opaque-boundary and identity-survival examples."""
import copy

from tools.qa import prune
from tests.operability.test_contract import OracleCase, node, canonical


class PruneTests(OracleCase):
    def test_a08_a23_good_heading_and_native_button_survive(self):
        raw=[node('heading',role='heading',name='Agents',action=None),node()]
        before=copy.deepcopy(raw)
        transformed=prune.transform(raw)
        self.assertEqual({(n['role'],n['name']) for n in transformed},
                         {('heading','Agents'),('button','Create agent')})
        self.verdict(prune.compare(raw,transformed,required=raw,complete=True),'PASS')
        self.assertEqual(raw,before)

    def test_a09_article_removes_entire_descendant_subtree(self):
        raw=[node('article',role='article',name='',action=None),
             node('wrapper',parent='article',role='group',name='',action=None),
             node('deep',parent='wrapper')]
        transformed=prune.transform(raw)
        self.assertNotIn('deep',{n['id'] for n in transformed})
        self.assertNotIn('wrapper',{n['id'] for n in transformed})
        self.verdict(prune.compare(raw,transformed,required=[raw[-1]],complete=True),
                     'FAIL','article_control')

    def test_a09_moving_action_outside_article_restores_survival(self):
        raw=[node('article',role='article',name='',action=None),node()]
        transformed=prune.transform(raw)
        self.assertIn('button-1',{n['id'] for n in transformed})
        self.verdict(prune.compare(raw,transformed,required=[raw[-1]],complete=True),'PASS')

    def test_a23_transparent_ancestors_leave_valid_parent_links(self):
        raw=[node('heading',role='heading',name='Agents',action=None),
             node('wrapper',parent='heading',role='group',name='',action=None),
             node(parent='wrapper')]
        transformed=prune.transform(raw)
        ids={n['id'] for n in transformed}
        self.assertIn('button-1',ids)
        for n in transformed:
            self.assertTrue(n['parent'] is None or n['parent'] in ids)
            self.assertNotEqual(n['id'],n['parent'])
        self.assertEqual(prune.transform(raw),transformed)
        self.verdict(prune.compare(raw,transformed,required=[raw[0],raw[-1]],complete=True),'PASS')

    def test_a23_input_order_does_not_change_surviving_identity_set(self):
        raw=[node('one',name='First action'),node('two',name='Second action')]
        before=prune.transform(raw)
        after=prune.transform(list(reversed(raw)))
        project=lambda values:{(n['role'],n['name'],n['entity'],n['entity_id'],n['action']) for n in values}
        self.assertEqual(project(before),project(after))

    def test_a12_exact_byte_limit_is_not_character_limit(self):
        raw=[node(name='é'*32)]
        transformed=prune.transform(raw)
        self.assertEqual(transformed[0]['name'],'é'*32)
        self.verdict(prune.compare(raw,transformed,required=raw,complete=True),'PASS')

    def test_a12_over_budget_name_is_not_repaired_by_clipping(self):
        raw=[node(name='é'*32+'x')]
        self.verdict(prune.compare(raw,raw,required=raw,complete=True),'FAIL','name_too_long')

    def test_a12_a23_transform_cannot_silently_clip_invalid_identity(self):
        raw=[node(name='é'*32+'x')]
        try:
            transformed=prune.transform(raw)
        except NotImplementedError:
            raise
        except (ValueError,TypeError):
            return  # Explicit rejection is permitted; repair is not.
        self.assertEqual(transformed[0]['name'],raw[0]['name'])
        self.verdict(prune.compare(raw,transformed,required=raw,complete=True),
                     'FAIL','name_too_long')

    def test_a11_a23_transform_cannot_silently_deduplicate_targets(self):
        raw=[node('one',name='Create agent'),node('two',name='Create agent')]
        try:
            transformed=prune.transform(raw)
        except NotImplementedError:
            raise
        except (ValueError,TypeError):
            return
        self.assertEqual(len(transformed),len(raw))
        self.verdict(prune.compare(raw,transformed,required=raw,complete=True),
                     'FAIL','duplicate_name')

    def test_a12_multibyte_name_exceeds_limit(self):
        raw=[node(name='界'*22)]
        self.verdict(prune.compare(raw,raw,required=raw,complete=True),'FAIL','name_too_long')

    def test_a11_duplicates_collide_after_nfc_and_whitespace(self):
        raw=[node('one',name='Café action'),node('two',name=' Cafe\u0301\t action ')]
        self.verdict(prune.compare(raw,raw,required=raw,complete=True),'FAIL','duplicate_name')

    def test_a11_identity_bearing_names_do_not_collide(self):
        raw=[node('one',name='Open agent alpha-root',role='link',action='open-agent',entity='agent',entity_id='alpha-root'),
             node('two',name='Open agent beta-root',role='link',action='open-agent',entity='agent',entity_id='beta-root')]
        transformed=prune.transform(raw)
        self.verdict(prune.compare(raw,transformed,required=raw,complete=True),'PASS')

    def test_a12_allowed_product_states_are_preserved(self):
        raw=[node(states=['busy','checked','current','disabled','expanded','hidden','pressed','selected'])]
        transformed=prune.transform(raw)
        self.assertEqual(set(transformed[0]['states']),set(raw[0]['states']))

    def test_a12_unexpected_normalized_state_fails(self):
        raw=[node(states=['invented'])]
        self.verdict(prune.compare(raw,raw,required=raw,complete=True),'FAIL','invalid_state')

    def test_a23_names_are_normalized_before_comparison(self):
        raw=[node(name='  Cafe\u0301\t action  ')]
        transformed=prune.transform(raw)
        self.assertEqual(transformed[0]['name'],'Café action')
        self.verdict(prune.compare(raw,transformed,required=[dict(raw[0],name='Café action')],complete=True),'PASS')

    def test_a04_a22_complete_missing_raw_action_fails(self):
        self.verdict(prune.compare([],[],required=[node()],complete=True),'FAIL','missing_control')

    def test_a04_a22_incomplete_tree_cannot_prove_absence(self):
        self.verdict(prune.compare([],[],required=[node()],complete=False),'INCONCLUSIVE')

    def test_a04_a30_empty_required_actions_cannot_pass_coverage(self):
        self.verdict(prune.compare([node()],[node()],required=[],complete=True),'INCONCLUSIVE')

    def test_a23_dropped_essential_button_is_detected(self):
        raw=[node()]
        self.verdict(prune.compare(raw,[],required=raw,complete=True),'FAIL')

    def test_a23_dropped_essential_heading_is_detected(self):
        raw=[node('heading',role='heading',name='Agents',action=None)]
        self.verdict(prune.compare(raw,[],required=raw,complete=True),'FAIL')

    def test_a23_changed_full_identity_is_detected(self):
        raw=[node(entity='agent',entity_id='alpha-root',action='retire-agent',name='Retire agent alpha-root')]
        transformed=[dict(raw[0],entity_id='beta-root')]
        self.verdict(prune.compare(raw,transformed,required=raw,complete=True),'FAIL')

    def test_a23_different_observer_handles_do_not_change_semantic_identity(self):
        raw=[node()];transformed=[dict(raw[0],id='fresh-handle')]
        self.verdict(prune.compare(raw,transformed,required=raw,complete=True),'PASS')

    def test_a24_raw_and_transformed_observations_remain_separate(self):
        raw=[node(name='  Create   agent ')];before=canonical(raw)
        transformed=prune.transform(raw)
        self.assertEqual(canonical(raw),before)
        self.assertNotEqual(canonical(transformed),before)
        self.assertEqual(transformed[0]['name'],'Create agent')


def malformed_forest_test(raw):
    def test(self):
        self.reject(prune.transform,copy.deepcopy(raw))
    return test


for label,raw in {
    'cycle':[node('one',parent='two'),node('two',parent='one',name='Other action')],
    'self_cycle':[node(parent='button-1')],
    'dangling_parent':[node(parent='missing')],
    'duplicate_ids':[node(),node(name='Other action')],
    'extra_key':[dict(node(),private='extra')],
    'boolean_parent':[node(parent=True)],
    'entity_without_id':[node(entity='agent')],
    'duplicate_states':[node(states=['busy','busy'])],
}.items():
    setattr(PruneTests,'test_a03_invalid_forest_'+label,malformed_forest_test(raw))
