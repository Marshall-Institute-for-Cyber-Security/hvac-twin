"""WeightedSum, checked against an exact calculation."""

from __future__ import annotations

import math

from digitwin.io import IOBus

from hvac_twin.plant.combinators import WeightedSum


def test_sum_applies_weights_and_bias() -> None:
    io = IOBus()
    io.set("a", 10.0)
    io.set("b", 4.0)
    combiner = WeightedSum(terms=[("a", 1.0), ("b", -2.0)], output_signal="out", bias=1.0)
    combiner.step(0.1, io)
    assert math.isclose(float(io.get("out")), 3.0)  # 1 + 1*10 - 2*4


def test_missing_signal_defaults_to_zero() -> None:
    io = IOBus()
    combiner = WeightedSum(terms=[("missing", 5.0)], output_signal="out")
    combiner.step(0.1, io)
    assert io.get("out") == 0.0
