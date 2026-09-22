"""Registers this repo's plant components and control programs with
DigiTwin's project loader.

Neither `digitwin.config._PLANT_COMPONENTS` nor `digitwin.programs._REGISTRY`
has a public registration API -- this reaches into both directly, which is
a wart, not a design choice. The clean fix is a public hook in DigiTwin
itself -- worth proposing there once a second consumer needs the same
thing. Until then: importing anything under `hvac_twin` runs this via
`__init__.py`, so these are loadable from a project file's
`[[plant.components]]` / `[plc] program = "..."` before
`digitwin.config.load_project` is ever called.
"""

from __future__ import annotations

from digitwin.config import _PLANT_COMPONENTS
from digitwin.programs import _REGISTRY as _PROGRAM_REGISTRY

from hvac_twin.plant.combinators import WeightedSum
from hvac_twin.plant.constant_signal import ConstantSignal
from hvac_twin.plant.excess import Excess
from hvac_twin.plant.thermal_links import HeatFlowLink
from hvac_twin.plant.thermal_node import ThermalNode
from hvac_twin.programs.crac_bang_bang import CracBangBangProgram
from hvac_twin.programs.office_wing_bang_bang import OfficeWingBangBangProgram

_PLANT_COMPONENTS.update(
    {
        "HeatFlowLink": HeatFlowLink,
        "ThermalNode": ThermalNode,
        "WeightedSum": WeightedSum,
        "Excess": Excess,
        "ConstantSignal": ConstantSignal,
    }
)

_PROGRAM_REGISTRY.update(
    {
        "crac_bang_bang": lambda _dt: CracBangBangProgram(),
        "office_wing_bang_bang": lambda _dt: OfficeWingBangBangProgram(),
    }
)
