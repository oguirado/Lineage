"""Execute every documented example rather than maintaining parallel samples."""
import json
import re
import subprocess
import sys

from .support import CommsCase, ENV, ROOT


class GuideTests(CommsCase):
    def test_complete_headless_walkthrough_and_four_surface_discovery_parity(self):
        text = (ROOT / 'docs/HEADLESS.md').read_text()
        blocks = re.findall(r'```python\n(.*?)\n```', text, re.S)
        self.assertTrue(blocks)
        for block in blocks:
            result = subprocess.run([sys.executable, '-B', '-c', block], cwd=ROOT,
                                    env=ENV, text=True, capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), 'Headless guide examples passed')
        self.assertEqual(len(re.findall(r'```', text)), 2 * len(blocks))

    def test_every_mcp_example_and_all_existing_and_new_prompts(self):
        self.birth()
        before = self.tree()
        text = (ROOT / 'docs/MCP.md').read_text()
        blocks = re.findall(r'```json\n(.*?)\n```', text, re.S)
        requests = [json.loads(line) for block in blocks for line in block.splitlines()]
        responses = self.rpc(requests)
        self.assertEqual(len(responses), len(requests))
        for sent, received in zip(requests, responses):
            self.assertEqual(sent['id'], received['id'])
            self.assertIn('result', received, received)
        self.assertEqual(self.tree(), before)
        prompts = next(item['result']['prompts'] for item in responses
                       if 'prompts' in item.get('result', {}))
        self.assertEqual({item['name'] for item in prompts}, {
            'create_agent_from_spec', 'breed_from_best', 'run_benchmark',
            'resume_agent_from_memory', 'operate_lineage'})
        self.assertEqual(len(re.findall(r'```', text)), 2 * len(blocks))
