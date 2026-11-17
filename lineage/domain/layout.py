"""Pure canonical paths for every per-agent projection and memory generation."""
from hashlib import sha256
from pathlib import Path
import re

PROJECTION_FILES = ('agent.json', 'CONSTITUTION.md', 'BRIEF_HEAD.md', 'scorecard.json')
_WORKFLOWS = frozenset(('develop', 'test', 'review', 'harden', 'research', 'orchestrate'))


def language_component(language: str) -> str:
    """Keep safe language names, hashing all other UTF-8 language values."""
    return (language if re.fullmatch(r'[A-Za-z0-9_-]+', language, flags=re.ASCII)
            else 'lang-' + sha256(language.encode('utf-8')).hexdigest())


def agent_dir(home, *, workflow: str, language: str, agent_id: str) -> Path:
    """Build the canonical home lexically; callers own no-follow I/O checks."""
    if (workflow not in _WORKFLOWS
            or re.fullmatch(r'[a-z][a-z0-9-]{2,63}', agent_id) is None
            or agent_id in ('operator', 'system')):
        raise ValueError('invalid agent path identity')
    return Path(home) / 'agents' / workflow / language_component(language) / agent_id


def memory_dir(home, *, workflow: str, language: str, agent_id: str) -> Path:
    """Keep the generation layout beneath its canonical agent directory."""
    return agent_dir(home, workflow=workflow, language=language, agent_id=agent_id) / 'memory'
