"""examples/office_wing_controlled.toml, loaded through the real
project-file pipeline: with the office wing's bang-bang heating loop
running in each zone, all three rooms should cycle in a comfortable band
around setpoint and never trip the freeze alarm -- directly contrasting
office_wing.toml, which (with no heat source at all) settles at the cold
outdoor boundary instead.

Commissions each zone's setpoint over a real loopback Modbus write
first, same reason as test_server_closet_controlled.py: ModbusSlaveServer
.sync() overwrites every accept-mapped tag from its register store every
tick regardless of whether a client ever connects, so an uncommissioned
zone would see a 0F setpoint from tick 1 and never heat at all -- see
examples/office_wing_controlled.toml's [modbus.slave_server] comment."""

from __future__ import annotations

import socket
import time
from pathlib import Path
from typing import Any

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)

_PROJECT_PATH = (
    Path(__file__).resolve().parents[1] / "examples" / "office_wing_controlled.toml"
)


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


def test_controlled_office_wing_holds_setpoint_band_and_never_freezes() -> None:
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
        for address in (0, 1, 2):
            client.write_registers(address=address, values=[720], device_id=1)
    finally:
        client.close()

    try:
        sim.run(20_000)

        for room in ("room_1", "room_2", "room_3"):
            temp = float(sim.bus.get(f"{room}_temp"))
            assert 68.0 <= temp <= 76.0
            assert sim.plc.tags[f"{room}_freeze_alarm"].value is False
    finally:
        sim.modbus_slave.stop()
