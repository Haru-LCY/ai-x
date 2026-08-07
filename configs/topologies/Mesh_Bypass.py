# Copyright (c) 2026
# All rights reserved.

"""Express-link augmented Mesh topology.

G1 deliberately supports only ``bypass_mode=none``.  In that mode this
topology delegates construction to Mesh_XY so that the baseline graph and all
Lab4 collective metadata have exactly one implementation.  Later acceptance
gates add links without changing Mesh_XY itself.
"""

from topologies.Mesh_XY import Mesh_XY


class Mesh_Bypass(Mesh_XY):
    description = "Mesh_Bypass"

    def makeTopology(self, options, network, IntLink, ExtLink, Router):
        mode = getattr(options, "bypass_mode", "none")
        if mode != "none":
            raise ValueError(
                "Mesh_Bypass currently implements only --bypass-mode=none "
                "(G1 baseline-equivalence gate)"
            )
        super().makeTopology(options, network, IntLink, ExtLink, Router)
