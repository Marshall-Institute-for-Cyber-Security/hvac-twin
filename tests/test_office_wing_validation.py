"""One isolated room against outdoor, validated against the ASHRAE-
simplified first-order lumped-capacitance decay this project promised in
docs/ROADMAP.md Phase 1: dT/dt = -(T - T_out) / tau, closed form
T(t) = T_out + (T0 - T_out) * exp(-t / tau), tau = heat_capacity / conductance.

Temperatures are in degrees Fahrenheit; heat_capacity and conductance are
"per degree" rates, divided by 1.8 from their Celsius-based design values
rather than run through the C-to-F formula (see examples/office_wing.toml).
"""

from __future__ import annotations

import math

from digitwin.io import IOBus

from hvac_twin.plant.combinators import WeightedSum
from hvac_twin.plant.constant_signal import ConstantSignal
from hvac_twin.plant.thermal_links import HeatFlowLink
from hvac_twin.plant.thermal_node import ThermalNode


def test_isolated_room_matches_the_ashrae_simplified_decay_curve() -> None:
    heat_capacity = 50_000.0 / 1.8
    conductance = 50.0 / 1.8
    tau = heat_capacity / conductance
    t_out = 14.0  # -10 C
    t0 = 50.0  # 10 C

    io = IOBus()
    outdoor = ConstantSignal(output_signal="outdoor", value=t_out)
    room = ThermalNode(
        temp_signal="room", flux_signal="flux", heat_capacity=heat_capacity, temp=t0
    )
    loss = HeatFlowLink(
        temp_a_signal="room", temp_b_signal="outdoor", flow_signal="loss", conductance=conductance
    )
    net = WeightedSum(terms=[("loss", -1.0)], output_signal="flux")

    dt = 1.0
    for step in range(1, 12001):
        outdoor.step(dt, io)
        loss.step(dt, io)
        net.step(dt, io)
        room.step(dt, io)
        if step == 1000:  # one time constant in -- checks the curve's shape, not just its end
            analytic = t_out + (t0 - t_out) * math.exp(-step * dt / tau)
            assert math.isclose(room.temp, analytic, rel_tol=1e-2)

    assert math.isclose(room.temp, t_out, abs_tol=1e-3)  # 12 time constants: fully settled