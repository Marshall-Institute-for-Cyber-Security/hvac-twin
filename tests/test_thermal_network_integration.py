"""Two ThermalNodes coupled through a HeatFlowLink and WeightedSum -- the
actual composition a multi-room project file will use -- settle at the same
capacity-weighted equilibrium the HeatFlowLink-only test checked by hand."""

from __future__ import annotations

import math

from digitwin.io import IOBus

from hvac_twin.plant.combinators import WeightedSum
from hvac_twin.plant.thermal_links import HeatFlowLink
from hvac_twin.plant.thermal_node import ThermalNode


def test_two_linked_nodes_settle_at_the_capacity_weighted_average() -> None:
    io = IOBus()
    node_a = ThermalNode(
        temp_signal="temp_a", flux_signal="flux_a", heat_capacity=500.0, temp=30.0
    )
    node_b = ThermalNode(
        temp_signal="temp_b", flux_signal="flux_b", heat_capacity=1500.0, temp=10.0
    )
    link = HeatFlowLink(
        temp_a_signal="temp_a", temp_b_signal="temp_b", flow_signal="link_flow", conductance=2.0
    )
    sum_a = WeightedSum(terms=[("link_flow", -1.0)], output_signal="flux_a")
    sum_b = WeightedSum(terms=[("link_flow", 1.0)], output_signal="flux_b")

    io.set("temp_a", node_a.temp)
    io.set("temp_b", node_b.temp)

    dt = 0.1
    for _ in range(200_000):
        link.step(dt, io)
        sum_a.step(dt, io)
        sum_b.step(dt, io)
        node_a.step(dt, io)
        node_b.step(dt, io)

    equilibrium = (500.0 * 30.0 + 1500.0 * 10.0) / (500.0 + 1500.0)
    assert math.isclose(node_a.temp, equilibrium, abs_tol=1e-6)
    assert math.isclose(node_b.temp, equilibrium, abs_tol=1e-6)
