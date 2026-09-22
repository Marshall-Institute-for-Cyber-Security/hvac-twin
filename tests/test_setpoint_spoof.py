"""hvac_twin.attacks.setpoint_spoof, exercised against a real Modbus
socket -- same live-socket pattern as test_server_closet_modbus.py, but
driving the actual attack script instead of raw pymodbus calls, to prove
the packaged tool does what that test's preview already showed was
possible."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin.attacks import setpoint_spoof

_PROJECT_PATH = Path(__file__).resolve().parents[1] / "examples" / "server_closet_controlled.toml"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_setpoint_spoof_script_changes_control_behavior_over_the_wire() -> None:
    pytest.importorskip("pymodbus")

    sim = load_project(_PROJECT_PATH)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()
    try:
        setpoint_spoof.main(
            ["--host", "127.0.0.1", "--port", str(sim.modbus_slave.port), "--setpoint", "900"]
        )
        sim.run(1)
        assert sim.plc.read("setpoint_tenths") == 9000
    finally:
        sim.modbus_slave.stop()
