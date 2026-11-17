# A-U01R: Replace room fixtures with thin calls into the authoritative journal API.
"""Fixtures for the retained durability assertions; no room or plan emulation."""
from tests.core.regression._support import JournalCase

BEAT = {"note": "working"}


def memory(oid="memory0001", section="notes"):
    return {"identity": oid, "section": section, "text": "Decision"}


def fd_count():
    import os
    from pathlib import Path
    return len(os.listdir(Path(os.sep) / "proc" / "self" / "fd"))


class RoomCase(JournalCase):
    # A-U01R: Historical class name retained solely to keep selected test IDs stable.
    def post(self, payload):
        return self.append(payload=payload)

    def batch(self, payloads):
        # A-U01R: A grouped payload is one journal event, not a post_ops API.
        return [self.append(payload={"items": payloads})]
