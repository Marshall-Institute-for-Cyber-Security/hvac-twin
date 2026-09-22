"""A room (or any other lumped mass) as one thermal node: temperature moves
in response to a single net heat input, in watts. Losses to outdoors, gains
from neighbors, occupancy, sunlight -- all of that is just another
contributor to that one input, combined upstream with WeightedSum. Nothing
about "ambient" or "loss" is special-cased here, unlike ThermalMass.
"""

from __future__ import annotations

from dataclasses import dataclass

from digitwin.io import IOBus


@dataclass
class ThermalNode:
    """dT/dt = flux_signal / heat_capacity. Integrated with explicit Euler.

    flux_signal is the *net* heat input in watts -- positive heats the node,
    negative cools it. Leave it unset (None) for a node with no external
    drive at all (temp stays constant); mainly useful in tests.
    """

    temp_signal: str
    flux_signal: str | None = None
    heat_capacity: float = 4184.0
    temp: float = 20.0

    def __post_init__(self) -> None:
        if self.heat_capacity <= 0:
            raise ValueError(f"heat_capacity must be positive, got {self.heat_capacity!r}")

    def step(self, dt: float, io: IOBus) -> None:
        flux = float(io.get(self.flux_signal, 0.0)) if self.flux_signal is not None else 0.0
        self.temp += dt * flux / self.heat_capacity
        io.set(self.temp_signal, self.temp)
