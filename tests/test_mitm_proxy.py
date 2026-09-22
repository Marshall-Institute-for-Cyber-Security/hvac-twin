"""hvac_twin.attacks.mitm_proxy, exercised against a real Modbus TCP
proxy in front of a live twin -- the network-level counterpart to
setpoint_spoof.py and alarm_mask.py's accept-write attacks. A real sensor
reading and a real alarm coil can't be overwritten by any accept write at
all; a MITM proxy doesn't need to write anything; it rewrites response
bytes in flight, which is what actually lets an attacker fake a read-only
value.

Two clients: an "HMI" that only ever talks through the proxy, and a
"ground truth" client that talks directly to the twin's real port,
bypassing the proxy entirely -- confirming the attack changes what's
displayed, not what's physically happening, and that legitimate writes
(the HMI's own commissioning) pass through the proxy untouched."""

from __future__ import annotations

import socket
import time
from pathlib import Path
from typing import Any

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin.attacks import setpoint_spoof
from hvac_twin.attacks.mitm_proxy import (
    FUNC_READ_COILS,
    FUNC_READ_INPUT_REGISTERS,
    MitmProxy,
    SpoofRule,
)

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


def test_mitm_proxy_shows_a_fake_reading_while_ground_truth_diverges() -> None:
    pytest.importorskip("pymodbus")
    from pymodbus.client import ModbusTcpClient

    sim = load_project(_PROJECT_PATH)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()

    proxy = MitmProxy(
        listen_host="127.0.0.1",
        listen_port=_free_port(),
        target_host="127.0.0.1",
        target_port=sim.modbus_slave.port,
        rules=[
            SpoofRule(FUNC_READ_INPUT_REGISTERS, address=0, value=750),  # always "75.0F"
            SpoofRule(FUNC_READ_COILS, address=0, value=0),  # always "no alarm"
        ],
    )
    proxy.start()

    hmi: Any = ModbusTcpClient("127.0.0.1", port=proxy.listen_port, timeout=1.0)
    ground_truth: Any = ModbusTcpClient("127.0.0.1", port=sim.modbus_slave.port, timeout=1.0)
    try:
        _connect(hmi)
        _connect(ground_truth)

        # The HMI's own commissioning writes pass through the proxy untouched.
        commission = hmi.write_registers(address=0, values=[750], device_id=1)
        assert not commission.isError()
        hmi.write_registers(address=3, values=[950], device_id=1)
        sim.run(1)

        # Cook the closet for real, through the proxy -- writes aren't touched.
        setpoint_spoof.main(
            ["--host", "127.0.0.1", "--port", str(proxy.listen_port), "--setpoint", "900"]
        )
        sim.run(6_000)

        # Ground truth, read directly: genuinely overheating and alarming.
        truth_temp = ground_truth.read_input_registers(address=0, count=1, device_id=1)
        truth_alarm = ground_truth.read_coils(address=0, count=1, device_id=1)
        assert truth_temp.registers[0] >= 950  # >= 95.0 F
        assert truth_alarm.bits[0] is True

        # The HMI, reading through the compromised proxy: everything's fine.
        hmi_temp = hmi.read_input_registers(address=0, count=1, device_id=1)
        hmi_alarm = hmi.read_coils(address=0, count=1, device_id=1)
        assert hmi_temp.registers[0] == 750
        assert hmi_alarm.bits[0] is False
    finally:
        hmi.close()
        ground_truth.close()
        proxy.stop()
        sim.modbus_slave.stop()
