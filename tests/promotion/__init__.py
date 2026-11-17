"""U19 oracles use the integrated memory facade before descriptor binding.

The installed memory package adds compatibility types to registry/app/journal.
Loading it first preserves the real registry's descriptor class identity.
"""
from lineage.domain import memory as _integrated_memory_facade
