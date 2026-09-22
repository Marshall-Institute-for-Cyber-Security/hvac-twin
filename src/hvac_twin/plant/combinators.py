"""Generic signal combinator: not thermal-specific, but the piece that lets
a ThermalNode with several heat contributors (multiple HeatFlowLinks plus an
occupancy/solar/equipment gain) present them as the single flux_signal it
reads.
"""

from __future__ import annotations

from dataclasses import dataclass

from digitwin.io import IOBus


@dataclass
class WeightedSum:
    """out = bias + sum(weight * in) over `terms`. Stateless.

    Each term is (signal_name, weight); a HeatFlowLink's flow_signal is
    typically weighted +1 on one side of the link and -1 on the other, since
    the same flow value is "arriving" at one node and "leaving" the other.
    """

    terms: list[tuple[str, float]]
    output_signal: str
    bias: float = 0.0

    def step(self, dt: float, io: IOBus) -> None:
        total = self.bias
        for signal, weight in self.terms:
            total += weight * float(io.get(signal, 0.0))
        io.set(self.output_signal, total)
