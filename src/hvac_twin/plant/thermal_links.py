"""Thermal coupling between nodes: heat exchange through a shared wall, duct,
or boundary. The multi-room analog of PipeSegment, but symmetric -- no valve,
no forward-only clamp -- since heat moves whichever way is hotter, not along
a commanded direction.
"""

from __future__ import annotations

from dataclasses import dataclass

from digitwin.io import IOBus


@dataclass
class HeatFlowLink:
    """Heat flow between two nodes through a resistance: watts = conductance
    * (temp_a - temp_b), positive when flowing A -> B. Stateless.

    A node with more than one link (or an internal gain) combines them with
    WeightedSum before feeding the result into a ThermalNode.
    """

    temp_a_signal: str
    temp_b_signal: str
    flow_signal: str
    conductance: float = 1.0
    max_flow: float = float("inf")

    def step(self, dt: float, io: IOBus) -> None:
        temp_a = float(io.get(self.temp_a_signal, 0.0))
        temp_b = float(io.get(self.temp_b_signal, 0.0))
        flow = self.conductance * (temp_a - temp_b)
        io.set(self.flow_signal, max(-self.max_flow, min(self.max_flow, flow)))
