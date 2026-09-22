"""ConstantSignal, checked against an exact calculation."""

from __future__ import annotations

from digitwin.io import IOBus

from hvac_twin.plant.constant_signal import ConstantSignal


def test_writes_its_fixed_value_every_step() -> None:
    io = IOBus()
    signal = ConstantSignal(output_signal="outdoor", value=5.0)
    for _ in range(3):
        signal.step(0.1, io)
    assert io.get("outdoor") == 5.0