"""QuarkSum — Particle inventory and mass closure tool.

Counts every particle from structures down to quarks and proves
that the books close at each level.

Quick start::

    import quarksum

    # Single material
    s = quarksum.build_quick_structure("Iron", 1.0)
    result = quarksum.stoq(s)

    # From a built-in structure
    s = quarksum.load_structure("gold_ring")
    result = quarksum.stoq(s)

    # Full quark-chain reconstruction
    result = quarksum.quark_chain(s)
"""

__version__ = "1.0.0"

from quarksum.builder import (
    build_quick_structure,
    build_structure_from_spec,
    list_structures,
    load_structure,
    load_structure_spec,
)
from quarksum.behaviors import (
    apply_env as apply,
    behaviors,
)
from quarksum.behaviors.quark_behaviors import (
    compute_quark_behaviors as quark_behaviors,
)
from quarksum.checksum.particle_inventory import (
    compute_particle_inventory as inventory,
)
from quarksum.checksum.quark_chain import (
    compute_quark_chain_checksum as quark_chain,
)
from quarksum.checksum.stoq_checksum import (
    compute_stoq_checksum as stoq,
)
from quarksum.models.structure import Structure
from quarksum.resolver import resolve

__all__ = [
    "__version__",
    "apply",
    "behaviors",
    "resolve",
    "Structure",
    "build_quick_structure",
    "build_structure_from_spec",
    "stoq",
    "inventory",
    "list_structures",
    "load_structure",
    "load_structure_spec",
    "quark_behaviors",
    "quark_chain",
]
