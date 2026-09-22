"""examples/server_closet_controlled.toml, reachable over a real Modbus TCP
socket -- this is what turns the attack surface from an in-process tag
write into something actually on the wire. Mirrors DigiTwin's own
test_slave_server_serves_a_real_pymodbus_client_end_to_end pattern."""

from __future__ import annotations

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


def test_a_plain_modbus_client_can_commission_and_read_back_the_closet() -> None:
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

        # Real commissioning writes: set the setpoint and the alarm
        # threshold over the wire before the twin has run at all, exactly
        # like an HMI would on startup -- both are accept-mapped, so
        # ModbusSlaveServer.sync() would otherwise zero them on tick 1
        # regardless of their TOML `initial =` (see
        # examples/server_closet_controlled.toml's commissioning-gotcha
        # comment).
        write = client.write_registers(address=0, values=[750], device_id=1)
        assert not write.isError()
        threshold_write = client.write_registers(address=3, values=[950], device_id=1)
        assert not threshold_write.isError()

        sim.run(5_000)

        temp = client.read_input_registers(address=0, count=1, device_id=1)
        assert not temp.isError()
        assert 700 <= temp.registers[0] <= 800  # 70.0-80.0 F, holding near the 75 F setpoint

        alarm = client.read_coils(address=0, count=1, device_id=1)
        assert not alarm.isError()
        assert alarm.bits[0] is False

        setpoint_readback = client.read_holding_registers(address=1, count=1, device_id=1)
        assert setpoint_readback.registers[0] == 750
    finally:
        client.close()
        sim.modbus_slave.stop()


def test_an_unauthenticated_write_changes_control_behavior_immediately() -> None:
    """Preview of Phase 3, not Phase 3 itself: the slave server has no
    concept of authentication, so this is already possible with zero new
    code -- writing the same register a legitimate HMI would use."""
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
        client.write_registers(address=0, values=[750], device_id=1)
        sim.run(1)

        spoof = client.write_registers(address=0, values=[9000], device_id=1)  # 900.0 F
        assert not spoof.isError()
        sim.run(1)

        assert sim.plc.read("setpoint_tenths") == 9000
    finally:
        client.close()
        sim.modbus_slave.stop()
