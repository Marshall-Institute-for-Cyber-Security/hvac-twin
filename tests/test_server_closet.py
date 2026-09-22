"""examples/server_closet.toml, loaded through the real project-file
pipeline: no controller, no active cooling -- the room crosses its safe
threshold and the damage accumulator saturates, exactly the flagship
"nothing stops this without a controller" point Phase 2 exists to fix."""

from __future__ import annotations

import math
from pathlib import Path

from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)

_PROJECT_PATH = Path(__file__).resolve().parents[1] / "examples" / "server_closet.toml"


def test_server_closet_overheats_and_damage_saturates_with_no_cooling() -> None:
    sim = load_project(_PROJECT_PATH)
    sim.run(20_000)

    assert float(sim.bus.get("closet_temp")) > 95.0  # past the safe-operating threshold
    assert math.isclose(float(sim.bus.get("closet_damage")), 100.0)  # accumulator saturated
