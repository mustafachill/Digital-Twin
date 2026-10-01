"""Host-agnostic tooling for the CITE Digital Twin.

This package implements the L0 layer's non-runtime half: schema validation for
the facility model, generation of the artifacts derived from it, and the asset
pipeline. It deliberately imports nothing from ROS, so that the model can be
validated on any machine — including one that could never build the ROS stack.

See `what-we-are-doing.md` §5 (L0) for what this layer is responsible for.
"""

__version__ = "0.1.0"
