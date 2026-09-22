"""examples/office_wing.toml, loaded through the real project-file pipeline:
three rooms, no controller, no heat source at all -- so the only physically
sane outcome is every room settling exactly at the outdoor boundary,
regardless of the interior wiring between them.
"""

from __future__ import annotations

import math
from pathlib import Path

from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)

_PROJECT_PATH = Path(__file__).resolve().parents[1] / "examples" / "office_wing.toml"


def test_office_wing_settles_at_outdoor_temperature_with_no_heat_source() -> None:
    sim = load_project(_PROJECT_PATH)
    sim.run(20_000)

    outdoor = 41.0
    for room in ("room_1", "room_2", "room_3"):
        assert math.isclose(float(sim.bus.get(f"{room}_temp")), outdoor, abs_tol=1e-3)
