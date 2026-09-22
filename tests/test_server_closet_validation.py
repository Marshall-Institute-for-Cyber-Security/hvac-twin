"""The server closet's flagship damage scenario: how long an unattended IT
closet with no active cooling takes to cross a safe-operating threshold,
validated against the closed-form decay to a heat-source-shifted
equilibrium (see docs/ROADMAP.md's flagship scenario)."""

from __future__ import annotations

import math

from digitwin.io import IOBus

from hvac_twin.plant.combinators import WeightedSum
from hvac_twin.plant.constant_signal import ConstantSignal
from hvac_twin.plant.thermal_links import HeatFlowLink
from hvac_twin.plant.thermal_node import ThermalNode


def test_time_to_cross_the_damage_threshold_matches_the_closed_form() -> None:
    heat_capacity = 400_000.0 / 1.8
    conductance = 45.0 / 1.8
    it_load = 2000.0  # watts -- a power, not a per-degree rate, so no /1.8
    t_out = 41.0
    t0 = 71.6
    threshold = 95.0

    t_eq = t_out + it_load / conductance  # equilibrium the IT load pushes the room to
    tau = heat_capacity / conductance
    analytic_t_thresh = tau * math.log((t0 - t_eq) / (threshold - t_eq))

    io = IOBus()
    outdoor = ConstantSignal(output_signal="outdoor", value=t_out)
    room = ThermalNode(
        temp_signal="room", flux_signal="flux", heat_capacity=heat_capacity, temp=t0
    )
    loss = HeatFlowLink(
        temp_a_signal="room", temp_b_signal="outdoor", flow_signal="loss", conductance=conductance
    )
    net = WeightedSum(terms=[("loss", -1.0)], output_signal="flux", bias=it_load)

    dt = 1.0
    step = 0
    while room.temp < threshold:
        outdoor.step(dt, io)
        loss.step(dt, io)
        net.step(dt, io)
        room.step(dt, io)
        step += 1

    assert math.isclose(step * dt, analytic_t_thresh, rel_tol=1e-2)