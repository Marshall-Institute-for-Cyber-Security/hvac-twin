"""hvac_twin.attacks.compromised_ews, exercised against a real Modbus
socket: confirms a single scripted session that reads then writes every
zone's setpoint causes room_1 and room_3 -- the office wing's two
non-adjacent end rooms -- to freeze-alarm at the same time, the
"lateral/cascading" signal from docs/ROADMAP.md Phase 3 that distinguishes
an attack from an isolated physical fault (which would hit one room, not
two disconnected ones simultaneously)."""

from __future__ import annotations

import socket
import time
from pathlib import Path
from typing import Any

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin.attacks import compromised_ews

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


def test_compromised_ews_pivots_every_zone_and_freezes_non_adjacent_rooms() -> None:
    pytest.importorskip("pymodbus")
    from pymodbus.client import ModbusTcpClient

    sim = load_project(_PROJECT_PATH)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()

    host, port = "127.0.0.1", sim.modbus_slave.port
    try:
        # Commission a healthy 72F setpoint for every zone, same as any
        # fresh controller.
        client: Any = ModbusTcpClient(host, port=port, timeout=1.0)
        try:
            _connect(client)
            for address in (0, 1, 2):
                client.write_registers(address=address, values=[720], device_id=1)
        finally:
            client.close()
        sim.run(5)

        for room in ("room_1", "room_2", "room_3"):
            assert sim.plc.tags[f"{room}_freeze_alarm"].value is False

        detail = compromised_ews.pivot_zone_setpoints(host, port, 0.0)
        assert "3 zone(s)" in detail

        sim.run(100_000)  # ~80,000s to cross 50F, verified numerically before writing

        # room_1 and room_3 share no wall -- room_2 sits between them -- so
        # all three alarming at once (not just one, as a single failed
        # heater would cause) is the signature this scenario exists to
        # demonstrate.
        for room in ("room_1", "room_2", "room_3"):
            assert sim.plc.tags[f"{room}_freeze_alarm"].value is True
    finally:
        sim.modbus_slave.stop()
