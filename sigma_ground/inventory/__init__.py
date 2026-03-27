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

from sigma_ground.inventory.builder import (
    build_quick_structure,
    build_structure_from_spec,
    list_structures,
    load_structure,
    load_structure_spec,
)
from sigma_ground.inventory.behaviors import (
    apply_env as apply,
    behaviors,
)
from sigma_ground.inventory.behaviors.quark_behaviors import (
    compute_quark_behaviors as quark_behaviors,
)
from sigma_ground.inventory.checksum.particle_inventory import (
    compute_particle_inventory as inventory,
)
from sigma_ground.inventory.checksum.quark_chain import (
    compute_quark_chain_checksum as quark_chain,
)
from sigma_ground.inventory.checksum.stoq_checksum import (
    compute_stoq_checksum as stoq,
)
from sigma_ground.inventory.models.structure import Structure
from sigma_ground.inventory.resolver import resolve
from sigma_ground.inventory.physics import (
    compute_physics as physics,
    compute_tangle as tangle,
)
from sigma_ground.inventory.defaults import (
    LOADS as default_loads,
    DEFAULT_ID as default_load_id,
    default_load,
    by_id as load_by_id,
)

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
    # Physics
    "physics",
    "tangle",
    # Defaults
    "default_loads",
    "default_load_id",
    "default_load",
    "load_by_id",
]
