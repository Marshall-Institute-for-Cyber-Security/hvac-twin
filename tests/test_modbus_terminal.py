"""hvac_twin.attacks.modbus_terminal, exercised against a real Modbus
socket -- same live-socket pattern as test_setpoint_spoof.py, but driving
the free-form terminal a student builds their own request through instead
of a fixed scenario."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin.attacks import modbus_terminal

_PROJECT_PATH = Path(__file__).resolve().parents[1] / "examples" / "server_closet_controlled.toml"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_read_operations_return_the_real_published_values() -> None:
    pytest.importorskip("pymodbus")

    sim = load_project(_PROJECT_PATH)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()
    try:
        temp = modbus_terminal.execute(
            "127.0.0.1", sim.modbus_slave.port, "read_input_registers", 0
        )
        assert temp["ok"] is True
        assert temp["values"] == [sim.plc.read("closet_temp_raw")]

        alarm = modbus_terminal.execute("127.0.0.1", sim.modbus_slave.port, "read_coils", 0)
        assert alarm["ok"] is True
        assert alarm["values"] == [sim.plc.read("high_temp_alarm")]
    finally:
        sim.modbus_slave.stop()


def test_write_registers_changes_control_behavior_over_the_wire() -> None:
    pytest.importorskip("pymodbus")

    sim = load_project(_PROJECT_PATH)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()
    try:
        result = modbus_terminal.execute(
            "127.0.0.1",
            sim.modbus_slave.port,
            "write_registers",
            0,
            values=[900],
        )
        assert result == {"ok": True, "values": None}
        sim.run(1)
        assert sim.plc.read("setpoint_tenths") == 900
    finally:
        sim.modbus_slave.stop()


def test_write_without_values_raises_runtime_error() -> None:
    pytest.importorskip("pymodbus")

    sim = load_project(_PROJECT_PATH)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()
    try:
        with pytest.raises(RuntimeError, match="needs"):
            modbus_terminal.execute(
                "127.0.0.1", sim.modbus_slave.port, "write_register", 0, values=None
            )
    finally:
        sim.modbus_slave.stop()
