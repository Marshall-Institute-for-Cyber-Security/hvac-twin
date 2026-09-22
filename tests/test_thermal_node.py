"""ThermalNode, checked against an exact linear ramp under constant flux."""

from __future__ import annotations

import math

from digitwin.io import IOBus

from hvac_twin.plant.thermal_node import ThermalNode


def test_constant_flux_is_a_linear_ramp() -> None:
    io = IOBus()
    io.set("flux", 500.0)
    node = ThermalNode(temp_signal="t", flux_signal="flux", heat_capacity=100.0, temp=20.0)

    dt = 0.1
    for _ in range(50):
        node.step(dt, io)

    expected = 20.0 + (500.0 / 100.0) * (50 * dt)  # rate * elapsed
    assert math.isclose(node.temp, expected)
    assert math.isclose(float(io.get("t")), expected)


def test_no_flux_signal_leaves_temperature_unchanged() -> None:
    io = IOBus()
    node = ThermalNode(temp_signal="t", temp=20.0)
    for _ in range(10):
        node.step(0.1, io)
    assert node.temp == 20.0
