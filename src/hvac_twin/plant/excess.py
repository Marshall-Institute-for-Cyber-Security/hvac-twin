"""A one-sided threshold: out = max(0, in - threshold). Stateless.

Exists so a value that only matters once it crosses some limit -- an
over-temperature amount, say -- can be fed into an Integrator (from
digitwin.plant) to build a monotonic "how much and how long" accumulator,
without a bespoke damage-tracking primitive.
"""

from __future__ import annotations

from dataclasses import dataclass

from digitwin.io import IOBus


@dataclass
class Excess:
    input_signal: str
    output_signal: str
    threshold: float = 0.0

    def step(self, dt: float, io: IOBus) -> None:
        value = float(io.get(self.input_signal, 0.0)) - self.threshold
        io.set(self.output_signal, max(0.0, value))
