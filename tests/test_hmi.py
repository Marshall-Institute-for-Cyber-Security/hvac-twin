"""hvac_twin.hmi, exercised against a real Executive advanced synchronously
via sim.run() (no background thread needed for these tests -- the app only
ever reads sim, so ticking it directly between assertions is enough):
confirms /tags and /bus expose the sensed-vs-ground-truth split the rest of
this project has been building since Phase 1, /historian and /events serve
real recorded data, both 404 cleanly on a project with no [observability],
and the WebSocket stream reflects live state."""

from __future__ import annotations

import socket
import time
from pathlib import Path
from typing import Any

import pytest
from digitwin.config import load_project
from digitwin.events import EventCategory, EventSeverity

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin import hmi

_CLOSET_PROJECT = Path(__file__).resolve().parents[1] / "examples" / "server_closet_controlled.toml"
# Uncontrolled/no-observability variant on purpose: office_wing_controlled.toml
# now configures [observability] (the office HMI's own anomaly-detection
# defense needs it), so the "404s cleanly with no observability configured"
# case below needs a project that still has none.
_NO_OBSERVABILITY_PROJECT = Path(__file__).resolve().parents[1] / "examples" / "office_wing.toml"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_tags_and_bus_expose_ground_truth_vs_sensed() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    sim = load_project(_CLOSET_PROJECT)
    sim.run(5)
    client = TestClient(hmi.create_app(sim))

    tags = client.get("/tags").json()
    # the PLC tag -- closet_temp_sensed is the bus signal it's wired from
    assert "closet_temp_raw" in tags

    ground_truth = client.get("/bus/closet_temp").json()
    assert ground_truth["name"] == "closet_temp"
    assert isinstance(ground_truth["value"], float)

    assert client.get("/tags/no_such_tag").status_code == 404
    assert client.get("/bus/no_such_signal").status_code == 404


def test_historian_and_events_serve_real_data() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    sim = load_project(_CLOSET_PROJECT)
    assert sim.historian is not None
    assert sim.events is not None
    sim.run(50)
    sim.events.log(
        sim.elapsed, EventCategory.ALARM, "test alarm", severity=EventSeverity.WARNING,
        source="test", high_temp=True,
    )

    client = TestClient(hmi.create_app(sim))

    series = client.get("/historian/closet_temp_raw").json()
    assert len(series) > 0
    assert series[0]["timestamp"] <= series[-1]["timestamp"]

    events = client.get("/events").json()
    assert any(e["message"] == "test alarm" and e["data"]["high_temp"] is True for e in events)

    assert client.get("/events", params={"category": "not-a-real-category"}).status_code == 400


def test_historian_and_events_404_without_observability() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    sim = load_project(_NO_OBSERVABILITY_PROJECT)
    assert sim.historian is None
    assert sim.events is None
    client = TestClient(hmi.create_app(sim))

    assert client.get("/historian/room_1_temp_raw").status_code == 404
    assert client.get("/events").status_code == 404


def test_websocket_stream_reflects_live_state() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    sim = load_project(_CLOSET_PROJECT)
    sim.run(10)
    client = TestClient(hmi.create_app(sim))

    with client.websocket_connect("/ws") as websocket:
        message: Any = websocket.receive_json()

    assert message["scan_count"] == sim.scan_count
    assert message["tags"]["closet_temp_raw"] == sim.plc.read("closet_temp_raw")


def test_operator_setpoint_write_via_hmi() -> None:
    """A legitimate operator write goes over the exact same Modbus channel
    setpoint_spoof.py uses to attack a twin -- /control/setpoint just
    issues it from the trusted HMI process instead of a red-team script."""
    pytest.importorskip("fastapi")
    pytest.importorskip("pymodbus")
    from fastapi.testclient import TestClient

    sim = load_project(_CLOSET_PROJECT)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()

    client = TestClient(hmi.create_app(sim))
    try:
        response = client.post(
            "/control/setpoint", json={"tag": "setpoint_tenths", "value_tenths": 680}
        )
        assert response.status_code == 200
        assert response.json()["value_tenths"] == 680

        sim.modbus_slave.sync()
        assert sim.plc.tags["setpoint_tenths"].value == 680

        # accept-writable but not a setpoint -- refused, not silently allowed
        assert (
            client.post(
                "/control/setpoint", json={"tag": "alarm_threshold_tenths", "value_tenths": 1}
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/control/setpoint", json={"tag": "no_such_tag", "value_tenths": 1}
            ).status_code
            == 404
        )
    finally:
        sim.modbus_slave.stop()


def test_anomaly_detection_toggle_via_hmi() -> None:
    """Anomaly detection defaults on but is toggleable, same shape as the
    auth proxy: disabling it makes /anomalies/{tag} report clean even over
    a jump that would otherwise trip the rate limit."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    sim = load_project(_CLOSET_PROJECT)
    assert sim.historian is not None
    sim.run(2)
    sim.historian.record(sim.elapsed + 1.0, {"closet_temp_raw": 0})
    sim.historian.record(sim.elapsed + 2.0, {"closet_temp_raw": 5000})

    client = TestClient(hmi.create_app(sim))

    assert client.get("/defenses/anomaly-detection").json() == {"enabled": True}
    anomalies = client.get(
        "/anomalies/closet_temp_raw", params={"max_rate_per_s": 50}
    ).json()
    assert len(anomalies) > 0

    stopped = client.post("/defenses/anomaly-detection/stop").json()
    assert stopped == {"enabled": False}
    assert (
        client.get("/anomalies/closet_temp_raw", params={"max_rate_per_s": 50}).json() == []
    )

    started = client.post("/defenses/anomaly-detection/start").json()
    assert started == {"enabled": True}


def test_auth_proxy_toggle_via_hmi_blocks_writes_but_not_reads() -> None:
    """The Phase 5 defense, wired into the HMI backend so a student can flip
    it on from the operator console rather than only via a Python script:
    starting it here points a real AuthProxy at this twin's own Modbus
    slave, and a client through the proxy sees exactly the enforcement
    test_auth_proxy.py already proves the class provides on its own."""
    pytest.importorskip("fastapi")
    pytest.importorskip("pymodbus")
    from fastapi.testclient import TestClient
    from pymodbus.client import ModbusTcpClient

    sim = load_project(_CLOSET_PROJECT)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()

    client = TestClient(hmi.create_app(sim))
    try:
        status = client.post(
            "/defenses/auth-proxy/start",
            json={"listen_host": "127.0.0.1", "allow_functions": [3, 4]},
        ).json()
        assert status["running"] is True
        listen_port = status["listen_port"]

        assert client.post("/defenses/auth-proxy/start", json={}).status_code == 409

        proxied: Any = ModbusTcpClient("127.0.0.1", port=listen_port, timeout=2.0)
        deadline = time.monotonic() + 3.0
        while not proxied.connect():
            if time.monotonic() > deadline:
                pytest.fail("auth proxy never accepted a connection")
            time.sleep(0.05)
        try:
            read_result = proxied.read_input_registers(address=0, count=1, device_id=1)
            assert not read_result.isError()
            write_result = proxied.write_registers(address=0, values=[9000], device_id=1)
            assert write_result.isError()
        finally:
            proxied.close()

        stop_status = client.post("/defenses/auth-proxy/stop").json()
        assert stop_status["running"] is False
        assert client.post("/defenses/auth-proxy/stop").status_code == 409
    finally:
        sim.modbus_slave.stop()
