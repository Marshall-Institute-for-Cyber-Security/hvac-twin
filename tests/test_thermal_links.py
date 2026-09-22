"""HeatFlowLink, checked against an exact single-step calculation and a
two-node relaxation to the capacity-weighted equilibrium temperature."""

from __future__ import annotations

import math

from digitwin.io import IOBus

from hvac_twin.plant.thermal_links import HeatFlowLink


def test_flow_is_conductance_times_temperature_difference() -> None:
    io = IOBus()
    io.set("a", 25.0)
    io.set("b", 20.0)
    link = HeatFlowLink(temp_a_signal="a", temp_b_signal="b", flow_signal="flow", conductance=3.0)
    link.step(0.1, io)
    assert math.isclose(float(io.get("flow")), 15.0)  # 3 * (25 - 20)


def test_flow_reverses_sign_with_temperature_and_clamps_to_max_flow() -> None:
    io = IOBus()
    io.set("a", 20.0)
    io.set("b", 25.0)
    link = HeatFlowLink(
        temp_a_signal="a", temp_b_signal="b", flow_signal="flow", conductance=3.0, max_flow=10.0
    )
    link.step(0.1, io)
    assert io.get("flow") == -10.0  # 3 * (20 - 25) = -15, clamped to -max_flow


def test_two_node_exchange_settles_at_the_capacity_weighted_average() -> None:
    io = IOBus()
    heat_capacity_a, heat_capacity_b = 500.0, 1500.0
    temp_a, temp_b = 30.0, 10.0
    link = HeatFlowLink(temp_a_signal="a", temp_b_signal="b", flow_signal="flow", conductance=2.0)

    io.set("a", temp_a)
    io.set("b", temp_b)
    dt = 0.1
    for _ in range(200_000):
        link.step(dt, io)
        flow = float(io.get("flow"))
        temp_a -= dt * flow / heat_capacity_a
        temp_b += dt * flow / heat_capacity_b
        io.set("a", temp_a)
        io.set("b", temp_b)

    equilibrium = (heat_capacity_a * 30.0 + heat_capacity_b * 10.0) / (
        heat_capacity_a + heat_capacity_b
    )
    assert math.isclose(temp_a, equilibrium, abs_tol=1e-6)
    assert math.isclose(temp_b, equilibrium, abs_tol=1e-6)
