"""hvac_twin.console, exercised against a real live twin over real
sockets via FastAPI's TestClient -- confirms an instructor can trigger
each landed Phase 3 scenario through one HTTP surface instead of running
standalone scripts, and that state (a running mitm-proxy, an in-progress
dos-flood) is genuinely tracked rather than fire-and-forget."""

from __future__ import annotations

import socket
import time
from pathlib import Path
from typing import Any

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin import console

_PROJECT_PATH = Path(__file__).resolve().parents[1] / "examples" / "server_closet_controlled.toml"
_OFFICE_WING_PROJECT_PATH = (
    Path(__file__).resolve().parents[1] / "examples" / "office_wing_controlled.toml"
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _start_live_twin(project_path: Path = _PROJECT_PATH) -> Any:
    sim = load_project(project_path)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()
    return sim


@pytest.fixture(autouse=True)
def _reset_console_state() -> Any:
    console._state = {
        name: console.ScenarioStatus(name=name, state="idle") for name in console._state
    }
    console._mitm_proxy = None
    console._dos_flood_stop = None
    yield


def test_setpoint_spoof_via_console_lands_on_the_real_twin() -> None:
    pytest.importorskip("pymodbus")
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    sim = _start_live_twin()
    try:
        client = TestClient(console.app)
        response = client.post(
            "/attacks/setpoint-spoof/start",
            json={"host": "127.0.0.1", "port": sim.modbus_slave.port, "setpoint": 900.0},
        )
        assert response.status_code == 200
        assert response.json()["state"] == "done"

        sim.run(5)  # sync() pulls the accept write into the tag on the next scan
        assert sim.plc.read("setpoint_tenths") == 9000
    finally:
        sim.modbus_slave.stop()


def test_mitm_proxy_start_stop_via_console() -> None:
    pytest.importorskip("pymodbus")
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from pymodbus.client import ModbusTcpClient

    sim = _start_live_twin()
    try:
        client = TestClient(console.app)
        listen_port = _free_port()
        response = client.post(
            "/attacks/mitm-proxy/start",
            json={
                "listen_host": "127.0.0.1",
                "listen_port": listen_port,
                "target_host": "127.0.0.1",
                "target_port": sim.modbus_slave.port,
                "spoof_temp": 75.0,
            },
        )
        assert response.status_code == 200
        assert response.json()["state"] == "running"

        # Already running -- a second start is rejected, not silently doubled.
        assert (
            client.post("/attacks/mitm-proxy/start", json={"spoof_temp": 80.0}).status_code == 409
        )

        hmi: Any = ModbusTcpClient("127.0.0.1", port=listen_port, timeout=2.0)
        deadline = time.monotonic() + 3.0
        while not hmi.connect():
            if time.monotonic() > deadline:
                pytest.fail("proxy never accepted a connection")
            time.sleep(0.05)
        try:
            result = hmi.read_input_registers(address=0, count=1, device_id=1)
            assert result.registers[0] == 750  # spoofed, regardless of ground truth
        finally:
            hmi.close()

        stop_response = client.post("/attacks/mitm-proxy/stop")
        assert stop_response.status_code == 200
        assert stop_response.json()["state"] == "idle"
        assert client.get("/attacks/mitm-proxy").json()["state"] == "idle"
    finally:
        sim.modbus_slave.stop()


def test_dos_flood_start_then_stop_ends_it_early_via_console() -> None:
    pytest.importorskip("pymodbus")
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    sim = _start_live_twin()
    try:
        client = TestClient(console.app)
        response = client.post(
            "/attacks/dos-flood/start",
            json={
                "host": "127.0.0.1",
                "port": sim.modbus_slave.port,
                "connections": 5,
                "duration_s": 30.0,
            },
        )
        assert response.status_code == 200
        assert response.json()["state"] == "running"

        time.sleep(0.3)
        started_at = time.monotonic()
        stop_response = client.post("/attacks/dos-flood/stop")
        assert stop_response.status_code == 200

        deadline = time.monotonic() + 3.0
        while client.get("/attacks/dos-flood").json()["state"] != "done":
            if time.monotonic() > deadline:
                pytest.fail("dos-flood did not report done after being stopped")
            time.sleep(0.05)
        elapsed = time.monotonic() - started_at
        assert elapsed < 5.0  # ended on request, not after the full 30s duration
    finally:
        sim.modbus_slave.stop()


def test_compromised_ews_via_console_pivots_every_zone() -> None:
    pytest.importorskip("pymodbus")
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from pymodbus.client import ModbusTcpClient

    sim = _start_live_twin(_OFFICE_WING_PROJECT_PATH)
    try:
        commission: Any = ModbusTcpClient("127.0.0.1", port=sim.modbus_slave.port, timeout=1.0)
        deadline = time.monotonic() + 3.0
        while not commission.connect():
            if time.monotonic() > deadline:
                pytest.fail("real pymodbus server never accepted a connection")
            time.sleep(0.05)
        try:
            for address in (0, 1, 2):
                commission.write_registers(address=address, values=[720], device_id=1)
        finally:
            commission.close()
        sim.run(5)

        client = TestClient(console.app)
        response = client.post(
            "/attacks/compromised-ews/start",
            json={"host": "127.0.0.1", "port": sim.modbus_slave.port, "setpoint": 0.0},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "done"
        assert "3 zone(s)" in body["detail"]

        sim.run(5)
        for room in ("room_1", "room_2", "room_3"):
            assert sim.plc.tags[f"{room}_heating_on"].value is False
    finally:
        sim.modbus_slave.stop()
