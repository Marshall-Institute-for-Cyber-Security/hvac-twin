"""The registry makes these components loadable through DigiTwin's own
load_project -- the integration point that actually matters, not just
checking the lookup dict directly."""

from __future__ import annotations

import math
from pathlib import Path

from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)

_PROJECT = """\
version = 1
name = "registry-smoke"

[plc]
model = "Generic"
program = "noop"

[executive]
dt = 0.1

[[plant.components]]
type = "HeatFlowLink"
temp_a_signal = "temp_a"
temp_b_signal = "temp_b"
flow_signal = "link_flow"
conductance = 2.0

[[plant.components]]
type = "WeightedSum"
terms = [["link_flow", -1.0]]
output_signal = "flux_a"

[[plant.components]]
type = "WeightedSum"
terms = [["link_flow", 1.0]]
output_signal = "flux_b"

[[plant.components]]
type = "ThermalNode"
temp_signal = "temp_a"
flux_signal = "flux_a"
heat_capacity = 500.0
temp = 30.0

[[plant.components]]
type = "ThermalNode"
temp_signal = "temp_b"
flux_signal = "flux_b"
heat_capacity = 1500.0
temp = 10.0
"""


def test_thermal_components_load_and_settle_through_a_real_project_file(
    tmp_path: Path,
) -> None:
    project = tmp_path / "registry_smoke.toml"
    project.write_text(_PROJECT, encoding="utf-8")

    sim = load_project(project)
    sim.run(200_000)

    equilibrium = (500.0 * 30.0 + 1500.0 * 10.0) / (500.0 + 1500.0)
    assert math.isclose(float(sim.bus.get("temp_a")), equilibrium, abs_tol=1e-6)
    assert math.isclose(float(sim.bus.get("temp_b")), equilibrium, abs_tol=1e-6)
