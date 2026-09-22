"""examples/server_closet_controlled.toml, loaded through the real
project-file pipeline: with the CRAC bang-bang loop running, the closet
should cycle near setpoint and never cross its damage threshold --
directly contrasting Phase 1's uncontrolled server_closet.toml, where it
runs away and saturates the damage accumulator.

Commissions the setpoint and the alarm threshold over real loopback
Modbus writes first, the same "like an HMI would on startup" step
test_server_closet_modbus.py uses. Both are accept-mapped, and
ModbusSlaveServer.sync() runs every tick regardless of whether a client
ever connects, unconditionally pulling from its internal register store
(0 for any address nothing has written) over each tag's TOML `initial =`.
Skip the setpoint commission and the closet never sees the intended
setpoint at all -- it runs the CRAC full-blast from tick 1 and crashes
toward the 41F outdoor temperature instead of the documented ~75F cycle,
which the old, loose `< 90.0` bound here didn't catch (both outcomes
satisfy it). Skip the alarm-threshold commission and high_temp_alarm
trips immediately and stays tripped (0 as a threshold means "always
over")."""

from __future__ import annotations

import math
import socket
import time
from pathlib import Path
from typing import Any

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)

_PROJECT_PATH = Path(__file__).resolve().parents[1] / "examples" / "server_closet_controlled.toml"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _connect(client: Any) -> None:
    deadline = time.monotonic() + 3.0
    while not client.connect():
        if time.monotonic() > deadline:
            pytest.fail("real pymodbus server never accepted a connection")
        time.sleep(0.05)


def test_controlled_closet_holds_setpoint_and_never_damages() -> None:
    pytest.importorskip("pymodbus")
    from pymodbus.client import ModbusTcpClient

    sim = load_project(_PROJECT_PATH)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()

    client: Any = ModbusTcpClient("127.0.0.1", port=sim.modbus_slave.port, timeout=1.0)
    try:
        _connect(client)
        client.write_registers(address=0, values=[750], device_id=1)  # commission setpoint
        client.write_registers(address=3, values=[950], device_id=1)  # commission alarm threshold
    finally:
        client.close()

    try:
        sim.run(20_000)

        temp = float(sim.bus.get("closet_temp"))
        assert 70.0 <= temp <= 80.0  # genuinely cycling near 75F, not crashed toward outdoor
        assert math.isclose(float(sim.bus.get("closet_damage")), 0.0)
        assert sim.plc.read("high_temp_alarm") is False
    finally:
        sim.modbus_slave.stop()
