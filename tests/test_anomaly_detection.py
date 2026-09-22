"""hvac_twin.defenses.anomaly_detection, exercised against a real
historian recording a live twin: confirms it stays silent through normal
commissioned operation (no false positives against this twin's own
tuning) and flags setpoint_spoof's instantaneous jump the moment it
happens -- the exact attack test_setpoint_spoof.py proves lands
unconditionally against an undefended twin."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin.attacks import setpoint_spoof
from hvac_twin.defenses.anomaly_detection import find_rate_anomalies
from hvac_twin.live_runner import _commission_accept_tags

_PROJECT_PATH = Path(__file__).resolve().parents[1] / "examples" / "server_closet_controlled.toml"
# tenths-of-a-degree per second -- generous vs. any real operator adjustment
_MAX_SETPOINT_RATE = 50.0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_no_false_positives_under_normal_commissioned_operation() -> None:
    """Commissions via _commission_accept_tags -- the same mechanism
    hvac_twin.hmi/live_runner use by default -- rather than a live client
    write. A live write still leaves one real tick where the tag reads
    its zeroed pre-write default before the write lands (historian.record()
    runs before modbus_slave.sync() within each tick), which shows up as a
    spurious 0 -> 750 "anomaly" that's an artifact of commissioning timing,
    not a real one. _commission_accept_tags seeds the register store
    directly (no live write needed) so the tag never transiently reads 0
    at all -- verified by first reproducing the spurious-anomaly failure
    with a live-write commission, then confirming it disappears here."""
    pytest.importorskip("pymodbus")

    sim = load_project(_PROJECT_PATH)
    assert sim.historian is not None
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    _commission_accept_tags(sim)
    sim.modbus_slave.sync()
    sim.modbus_slave.start()

    try:
        sim.run(500)
        anomalies = find_rate_anomalies(
            sim.historian, "setpoint_tenths", max_rate_per_s=_MAX_SETPOINT_RATE
        )
        assert anomalies == []
    finally:
        sim.modbus_slave.stop()


def test_setpoint_spoof_produces_a_detectable_rate_anomaly() -> None:
    pytest.importorskip("pymodbus")

    sim = load_project(_PROJECT_PATH)
    assert sim.historian is not None
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    _commission_accept_tags(sim)
    sim.modbus_slave.sync()
    sim.modbus_slave.start()

    try:
        sim.run(5)
        setpoint_spoof.main(
            ["--host", "127.0.0.1", "--port", str(sim.modbus_slave.port), "--setpoint", "900"]
        )
        sim.run(5)

        anomalies = find_rate_anomalies(
            sim.historian, "setpoint_tenths", max_rate_per_s=_MAX_SETPOINT_RATE
        )
        assert len(anomalies) == 1
        assert anomalies[0].from_value == 750.0
        assert anomalies[0].to_value == 9000.0
    finally:
        sim.modbus_slave.stop()
