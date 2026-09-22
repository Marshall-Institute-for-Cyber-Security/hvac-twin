"""hvac_twin.attacks.alarm_mask, exercised against a real Modbus socket,
chained with setpoint_spoof.py to reproduce the flagship "cooking the
server closet" narrative from docs/ROADMAP.md Phase 3: commission the
closet normally, spoof the setpoint so cooling stops and the closet
genuinely overheats, confirm the alarm is genuinely (honestly) tripped,
then mask it by spoofing the threshold it's compared against -- and
confirm ground truth (closet_temp / closet_damage) is completely
unaffected by the mask, which is the whole point of the deception
category: the attack changes what the operator sees, not what's
physically happening."""

from __future__ import annotations

import socket
import time
from pathlib import Path
from typing import Any

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin.attacks import alarm_mask, setpoint_spoof

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


def test_alarm_mask_hides_a_real_overheat_from_the_wire() -> None:
    pytest.importorskip("pymodbus")
    from pymodbus.client import ModbusTcpClient

    sim = load_project(_PROJECT_PATH)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()

    host, port = "127.0.0.1", sim.modbus_slave.port
    try:
        # Commission a healthy setpoint and the real 95F alarm threshold,
        # same as any fresh controller.
        client: Any = ModbusTcpClient(host, port=port, timeout=1.0)
        try:
            _connect(client)
            client.write_registers(address=0, values=[750], device_id=1)
            client.write_registers(address=3, values=[950], device_id=1)
        finally:
            client.close()
        # A couple of ticks, not one: sync() (which pulls the just-written
        # accept values into their tags) runs after the scan each tick, so
        # the commissioned threshold isn't visible to the ladder until the
        # *second* scan.
        sim.run(5)

        assert sim.plc.read("high_temp_alarm") is False  # healthy baseline, honestly reported

        # Scenario #1: spoof the setpoint so cooling never runs, and let
        # ground truth climb well past the 95F alarm threshold.
        setpoint_spoof.main(["--host", host, "--port", str(port), "--setpoint", "900"])
        sim.run(6_000)

        assert float(sim.bus.get("closet_temp")) > 95.0
        assert float(sim.bus.get("closet_damage")) > 0.0
        assert sim.plc.read("high_temp_alarm") is True  # genuinely alarming right now

        temp_before_mask = float(sim.bus.get("closet_temp"))
        damage_before_mask = float(sim.bus.get("closet_damage"))

        # Scenario #2: mask it.
        alarm_mask.main(["--host", host, "--port", str(port)])
        sim.run(100)

        assert sim.plc.read("high_temp_alarm") is False  # masked on the wire...
        # ...while ground truth is not just unchanged, it kept getting worse.
        assert float(sim.bus.get("closet_temp")) >= temp_before_mask
        assert float(sim.bus.get("closet_damage")) >= damage_before_mask
    finally:
        sim.modbus_slave.stop()
