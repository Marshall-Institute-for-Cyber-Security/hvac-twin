"""hvac_twin.live_runner, exercised end-to-end: loads a project file,
starts its Modbus slave on a free port, runs for a short bounded duration
in real-time-paced mode, and shuts down cleanly. This is the live target
Phase 3 attack scripts (e.g. hvac_twin.attacks.setpoint_spoof) run
against outside of pytest; DigiTwin's own `digitwin run` CLI doesn't open
the Modbus port or pace in real time, so this repo needs its own entry
point for that.

Also proves auto-commissioning: without it, ModbusSlaveServer.sync()
silently zeros every accept-mapped tag (setpoint_tenths included) on
tick 1 regardless of whether a client ever connects -- the bug documented
in examples/server_closet_controlled.toml's [modbus.slave_server]
comment. run_live() seeds the register store from each tag's own TOML
`initial =` before the first tick by default; --cold-start (tested here
as auto_commission=False) reproduces the old, broken behavior on
purpose."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin.live_runner import run_live

_PROJECT_PATH = Path(__file__).resolve().parents[1] / "examples" / "server_closet_controlled.toml"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_run_live_serves_modbus_for_a_bounded_duration_then_stops() -> None:
    pytest.importorskip("pymodbus")

    sim = run_live(_PROJECT_PATH, host="127.0.0.1", port=_free_port(), seconds=2.0)

    assert sim.scan_count == 2  # dt=1.0s, so 2 simulated seconds is 2 scans
    assert sim.modbus_slave is not None


def test_run_live_auto_commissions_accept_mapped_tags_by_default() -> None:
    pytest.importorskip("pymodbus")

    sim = run_live(_PROJECT_PATH, host="127.0.0.1", port=_free_port(), seconds=1.0)

    # Held its TOML `initial = 750`, not the register store's zero default.
    assert sim.plc.read("setpoint_tenths") == 750
    assert sim.plc.read("alarm_threshold_tenths") == 950


def test_cold_start_reproduces_the_uncommissioned_bug_on_purpose() -> None:
    pytest.importorskip("pymodbus")

    sim = run_live(
        _PROJECT_PATH, host="127.0.0.1", port=_free_port(), seconds=1.0, auto_commission=False
    )

    assert sim.plc.read("setpoint_tenths") == 0
    assert sim.plc.read("alarm_threshold_tenths") == 0
