"""Excess, checked against an exact calculation at, above, and below
threshold, plus the actual reason it exists: feeding an Integrator to build
a monotonic, never-reset damage accumulator."""

from __future__ import annotations

import math

from digitwin.io import IOBus
from digitwin.plant import Integrator

from hvac_twin.plant.excess import Excess


def test_below_threshold_is_zero() -> None:
    io = IOBus()
    io.set("t", 24.0)
    excess = Excess(input_signal="t", output_signal="over", threshold=27.0)
    excess.step(0.1, io)
    assert io.get("over") == 0.0


def test_at_threshold_is_zero() -> None:
    io = IOBus()
    io.set("t", 27.0)
    excess = Excess(input_signal="t", output_signal="over", threshold=27.0)
    excess.step(0.1, io)
    assert io.get("over") == 0.0


def test_above_threshold_is_the_difference() -> None:
    io = IOBus()
    io.set("t", 30.0)
    excess = Excess(input_signal="t", output_signal="over", threshold=27.0)
    excess.step(0.1, io)
    assert math.isclose(float(io.get("over")), 3.0)


def test_feeds_a_monotonic_damage_accumulator_that_does_not_reset() -> None:
    io = IOBus()
    excess = Excess(input_signal="temp", output_signal="over", threshold=27.0)
    damage = Integrator(input_signal="over", output_signal="damage", out_max=100.0)

    dt = 0.1
    io.set("temp", 32.0)  # 5 degrees over, for 10 simulated seconds
    for _ in range(100):
        excess.step(dt, io)
        damage.step(dt, io)
    accumulated = damage.value
    assert accumulated > 0.0

    io.set("temp", 20.0)  # fully recovers -- damage must NOT go back down
    for _ in range(100):
        excess.step(dt, io)
        damage.step(dt, io)
    assert math.isclose(damage.value, accumulated)
    assert damage.value > 0.0
