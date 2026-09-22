"""hvac_twin.attacks.dos_flood, exercised against a real Modbus TCP slave
server fronting a live twin -- confirms a plain request flood measurably
degrades a legitimate client's response latency on the same port (the
"loss of view" case: an HMI goes slow/stale) while the twin's own scan
loop keeps advancing throughout, completely unaffected -- the physical
process keeps running unattended, which is the sharper half of the
lesson."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin.attacks import dos_flood

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


def _time_n_reads(client: Any, n: int) -> float:
    start = time.monotonic()
    for _ in range(n):
        result = client.read_input_registers(address=0, count=1, device_id=1)
        assert not result.isError()
    return time.monotonic() - start


def test_flood_degrades_legitimate_client_while_physics_keeps_ticking() -> None:
    pytest.importorskip("pymodbus")
    from pymodbus.client import ModbusTcpClient

    sim = load_project(_PROJECT_PATH)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()

    hmi: Any = ModbusTcpClient("127.0.0.1", port=sim.modbus_slave.port, timeout=2.0)
    try:
        _connect(hmi)
        baseline = _time_n_reads(hmi, 20)

        flood_thread = threading.Thread(
            target=dos_flood.run_flood,
            kwargs={
                "host": "127.0.0.1",
                "port": sim.modbus_slave.port,
                "connections": 30,
                "duration_s": 3.0,
            },
            daemon=True,
        )
        flood_thread.start()
        time.sleep(0.3)  # let the flood connections ramp up and start contending

        scans_before = sim.scan_count
        during = _time_n_reads(hmi, 20)
        sim.run(10)  # the scan/physics loop is on its own thread -- unaffected by the flood
        assert sim.scan_count > scans_before

        flood_thread.join(timeout=5.0)

        assert during > baseline * 1.5  # legitimate reads visibly slower while flooded
    finally:
        hmi.close()
        sim.modbus_slave.stop()
