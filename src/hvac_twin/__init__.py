"""HVAC digital twin: multi-room thermal physics, attack scenarios, and HMI.

Built on top of the `digitwin` soft-PLC + physics framework. See
docs/ROADMAP.md for the layer split and phase plan.
"""

from __future__ import annotations

from . import registry  # noqa: F401  (side effect: registers components with DigiTwin)
