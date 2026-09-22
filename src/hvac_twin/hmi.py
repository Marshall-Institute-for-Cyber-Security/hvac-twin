"""HMI backend (Phase 4): a FastAPI service serving a running twin's live
tag table, ground-truth bus signals, historian trends, and event log over
HTTP, plus a WebSocket stream of the same. Mostly read-only -- the one
exception is /control/setpoint, a legitimate operator write sent over the
same Modbus channel an attack would use (see that route's docstring).

    uv run python -m hvac_twin.hmi examples/server_closet_controlled.toml

Then, e.g.:
    curl localhost:8100/tags
    curl localhost:8100/bus/closet_temp
    curl localhost:8100/events
    curl localhost:8100/historian.closet_temp_sensed

Requires the project file to declare [observability] (historian/events
are None otherwise, per DigiTwin's own config.py) -- /events and
/historian/{tag} 404 rather than silently returning nothing in that case.

Reads happen from a different thread than the twin's own tick loop (the
same arrangement as the Modbus slave server), with no locking between
them -- acceptable for a monitoring dashboard's eventually-consistent
view, not something transactional.
"""

from __future__ import annotations

import argparse
import asyncio
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from digitwin.events import EventCategory, EventSeverity
from digitwin.executive import Executive
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin.defenses.anomaly_detection import find_rate_anomalies
from hvac_twin.defenses.auth_proxy import AuthProxy
from hvac_twin.live_runner import start_twin

_WS_INTERVAL_S = 5.0


class TagValue(BaseModel):
    name: str
    value: Any


class EventOut(BaseModel):
    timestamp: float
    scan: int | None
    category: str
    severity: str
    source: str
    message: str
    data: dict[str, Any]


class SeriesPoint(BaseModel):
    timestamp: float
    value: Any


class StatusOut(BaseModel):
    scan_count: int
    elapsed: float


class AuthProxyStatus(BaseModel):
    running: bool
    listen_host: str | None = None
    listen_port: int | None = None
    allowed_source_ips: list[str] | None = None
    allowed_function_codes: list[int] | None = None


class AnomalyDetectionStatus(BaseModel):
    enabled: bool


class SetpointRequest(BaseModel):
    tag: str
    value_tenths: int


class SetpointResult(BaseModel):
    tag: str
    value_tenths: int
    detail: str


class AuthProxyRequest(BaseModel):
    # 0.0.0.0, not 127.0.0.1: this proxy exists specifically to be the new
    # front door for whoever would otherwise attack the twin directly --
    # binding it to loopback-only would make it unreachable by exactly the
    # kind of external client it's meant to filter (e.g. a different
    # container under Docker Compose, or a second laptop in the two-laptop
    # deployment model).
    listen_host: str = "0.0.0.0"
    listen_port: int = 0  # 0 = OS picks a free port
    allow_ips: list[str] | None = None
    allow_functions: list[int] | None = None


def _event_out(event: Any) -> EventOut:
    return EventOut(
        timestamp=event.timestamp,
        scan=event.scan,
        category=event.category.value,
        severity=event.severity.value,
        source=event.source,
        message=event.message,
        data=event.data,
    )


def create_app(sim: Executive) -> FastAPI:
    """FastAPI app that reads `sim` live -- `sim` is expected to
    already be advancing on its own (bg thread in run_hmi(), or
    a test calling sim.run()/sim.tick() directly). This app never
    advances it and never writes to it."""
    app = FastAPI(title="hvac-twin HMI")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/status", response_model=StatusOut)
    def get_status() -> StatusOut:
        return StatusOut(scan_count=sim.scan_count, elapsed=sim.elapsed)

    @app.get("/tags", response_model=dict[str, Any])
    def get_tags() -> dict[str, Any]:
        return {name: tag.value for name, tag in sim.plc.tags.items()}

    @app.get("/tags/{name}", response_model=TagValue)
    def get_tag(name: str) -> TagValue:
        if name not in sim.plc.tags:
            raise HTTPException(404, f"unknown tag {name!r}")
        return TagValue(name=name, value=sim.plc.tags[name].value)

    @app.get("/bus", response_model=dict[str, Any])
    def get_bus() -> dict[str, Any]:
        snapshot: dict[str, Any] = sim.bus.snapshot()
        return snapshot

    @app.get("/bus/{signal}", response_model=TagValue)
    def get_bus_signal(signal: str) -> TagValue:
        snapshot = sim.bus.snapshot()
        if signal not in snapshot:
            raise HTTPException(404, f"unknown bus signal {signal!r}")
        return TagValue(name=signal, value=snapshot[signal])

    @app.get("/events", response_model=list[EventOut])
    def get_events(
        category: str | None = None, severity: str | None = None, limit: int = 100
    ) -> list[EventOut]:
        if sim.events is None:
            raise HTTPException(404, "this twin has no event log configured")
        try:
            cat = EventCategory(category) if category is not None else None
            sev = EventSeverity(severity) if severity is not None else None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        matches = sim.events.query(category=cat, severity=sev)
        return [_event_out(e) for e in matches[-limit:]]

    @app.get("/historian/{tag}", response_model=list[SeriesPoint])
    def get_series(
        tag: str, start: float | None = None, end: float | None = None
    ) -> list[SeriesPoint]:
        if sim.historian is None:
            raise HTTPException(404, "this twin has no historian configured")
        return [
            SeriesPoint(timestamp=t, value=v)
            for t, v in sim.historian.series(tag, start=start, end=end)
        ]

    _anomaly_detection_enabled = True

    @app.get("/anomalies/{tag}", response_model=list[dict[str, Any]])
    def get_rate_anomalies(tag: str, max_rate_per_s: float) -> list[dict[str, Any]]:
        if sim.historian is None:
            raise HTTPException(404, "this twin has no historian configured")
        if not _anomaly_detection_enabled:
            return []
        anomalies = find_rate_anomalies(sim.historian, tag, max_rate_per_s=max_rate_per_s)
        return [asdict(a) for a in anomalies]

    @app.get("/defenses/anomaly-detection", response_model=AnomalyDetectionStatus)
    def get_anomaly_detection() -> AnomalyDetectionStatus:
        return AnomalyDetectionStatus(enabled=_anomaly_detection_enabled)

    @app.post("/defenses/anomaly-detection/start", response_model=AnomalyDetectionStatus)
    def start_anomaly_detection() -> AnomalyDetectionStatus:
        nonlocal _anomaly_detection_enabled
        _anomaly_detection_enabled = True
        return AnomalyDetectionStatus(enabled=_anomaly_detection_enabled)

    @app.post("/defenses/anomaly-detection/stop", response_model=AnomalyDetectionStatus)
    def stop_anomaly_detection() -> AnomalyDetectionStatus:
        nonlocal _anomaly_detection_enabled
        _anomaly_detection_enabled = False
        return AnomalyDetectionStatus(enabled=_anomaly_detection_enabled)

    @app.post("/control/setpoint", response_model=SetpointResult)
    def set_setpoint(req: SetpointRequest) -> SetpointResult:
        """Operator write: a real Modbus write to the twin's own accept
        register, the same channel setpoint_spoof.py attacks over. Scoped to
        accept-writable tags with "setpoint" in the name so this can't also
        move an alarm threshold."""
        if sim.modbus_slave is None:
            raise HTTPException(400, "this twin has no Modbus slave to command")
        reg = sim.modbus_slave.accept.get(req.tag)
        if reg is None or reg.kind != "holding_register" or "setpoint" not in req.tag:
            raise HTTPException(404, f"{req.tag!r} is not an operator-writable setpoint")
        from pymodbus.client import ModbusTcpClient

        from hvac_twin.attacks._client import wait_for_connection

        client: Any = ModbusTcpClient("127.0.0.1", port=sim.modbus_slave.port, timeout=2.0)
        try:
            wait_for_connection(client, "127.0.0.1", sim.modbus_slave.port)
            result = client.write_registers(
                address=reg.address,
                values=reg.encode(req.value_tenths),
                device_id=sim.modbus_slave.unit_id,
            )
            if result.isError():
                raise RuntimeError(f"write failed: {result}")
        except (ConnectionError, RuntimeError) as exc:
            raise HTTPException(502, str(exc)) from exc
        finally:
            client.close()
        return SetpointResult(
            tag=req.tag,
            value_tenths=req.value_tenths,
            detail=f"wrote {req.tag} = {req.value_tenths}",
        )

    _auth_proxy: AuthProxy | None = None

    def _auth_proxy_status() -> AuthProxyStatus:
        if _auth_proxy is None:
            return AuthProxyStatus(running=False)
        return AuthProxyStatus(
            running=True,
            listen_host=_auth_proxy.listen_host,
            listen_port=_auth_proxy.listen_port,
            allowed_source_ips=(
                sorted(_auth_proxy.allowed_source_ips) if _auth_proxy.allowed_source_ips else None
            ),
            allowed_function_codes=(
                sorted(_auth_proxy.allowed_function_codes)
                if _auth_proxy.allowed_function_codes
                else None
            ),
        )

    @app.get("/defenses/auth-proxy", response_model=AuthProxyStatus)
    def get_auth_proxy() -> AuthProxyStatus:
        return _auth_proxy_status()

    @app.post("/defenses/auth-proxy/start", response_model=AuthProxyStatus)
    def start_auth_proxy(req: AuthProxyRequest) -> AuthProxyStatus:
        nonlocal _auth_proxy
        if _auth_proxy is not None:
            raise HTTPException(409, "auth proxy is already running")
        if sim.modbus_slave is None:
            raise HTTPException(400, "this twin has no Modbus slave to defend")
        if req.listen_host not in ("127.0.0.1", "localhost", "::1") and not (
            req.allow_ips or req.allow_functions
        ):
            raise HTTPException(
                400,
                "listen_host is reachable beyond loopback but allow_ips and "
                "allow_functions are both empty -- that would start a fully "
                "open, unrestricted proxy; set at least one allowlist",
            )
        proxy = AuthProxy(
            req.listen_host,
            req.listen_port,
            "127.0.0.1",  # the proxy runs alongside the twin -- always reachable via loopback
            sim.modbus_slave.port,  # regardless of what the real slave itself is bound to
            enabled=True,
            allowed_source_ips=frozenset(req.allow_ips) if req.allow_ips else None,
            allowed_function_codes=frozenset(req.allow_functions) if req.allow_functions else None,
        )
        proxy.start()
        _auth_proxy = proxy
        return _auth_proxy_status()

    @app.post("/defenses/auth-proxy/stop", response_model=AuthProxyStatus)
    def stop_auth_proxy() -> AuthProxyStatus:
        nonlocal _auth_proxy
        if _auth_proxy is None:
            raise HTTPException(409, "auth proxy is not running")
        _auth_proxy.stop()
        _auth_proxy = None
        return AuthProxyStatus(running=False)

    @app.websocket("/ws")
    async def stream(websocket: WebSocket) -> None:
        await websocket.accept()
        seen_events = len(sim.events.events) if sim.events is not None else 0
        try:
            while True:
                new_events: list [EventOut] = []
                if sim.events is not None:
                    new_events = [_event_out(e) for e in sim.events.events[seen_events:]]
                    seen_events = len(sim.events.events)
                await websocket.send_json(
                    {
                        "scan_count": sim.scan_count,
                        "elapsed": sim.elapsed,
                        "tags": {name: tag.value for name, tag in sim.plc.tags.items()},
                        "events": [e.model_dump() for e in new_events],
                    }
                )
                await asyncio.sleep(_WS_INTERVAL_S)
        except WebSocketDisconnect:
            pass

    return app


def _tick_forever(sim: Executive, stop: threading.Event) -> None:
    while not stop.is_set():
        sim.tick()



def run_hmi(
    project: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8100,
    twin_host: str | None = None,
    twin_port: int | None = None,
) -> None:
    """Load `project`, start it ticking in real time on a background
    thread, and serve its live state over HTTP + WebSocket on
    `host`:`port` until interrupted."""
    sim = start_twin(project, host=twin_host, port=twin_port)

    stop = threading.Event()
    tick_thread = threading.Thread(target=_tick_forever, args=(sim, stop), daemon=True)
    tick_thread.start()

    app = create_app(sim)
    import uvicorn

    try:
        uvicorn.run(app, host=host, port=port)
    finally:
        stop.set()
        if sim.modbus_slave is not None:
            sim.modbus_slave.stop()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="path to a .toml project file")
    parser.add_argument("--host", default="127.0.0.1", help="HMI server host")
    parser.add_argument("--port", type=int, default=8100, help="HMI server port")
    parser.add_argument("--twin-host", default=None, help="override [modbus.slave_server] host")
    parser.add_argument(
        "--twin-port", type=int, default=None, help="override [modbus.slave_server] port"
    )
    args = parser.parse_args(argv)

    run_hmi(
        args.project,
        host=args.host,
        port=args.port,
        twin_host=args.twin_host,
        twin_port=args.twin_port,
    )


if __name__ == "__main__":
    main()