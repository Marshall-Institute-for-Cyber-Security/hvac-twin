"""A fixed value written to the bus every tick -- the outdoor boundary
signal a HeatFlowLink connects each room to, so "outside" needs no special
case: it's a node with infinite capacity, expressed simply as a value
nothing changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from digitwin.io import IOBus


@dataclass
class ConstantSignal:
    output_signal: str
    value: float = 0.0

    def step(self, dt: float, io: IOBus) -> None:
        io.set(self.output_signal, self.value)