"""Attack console: a FastAPI service an instructor uses to start/stop each
Phase 3 attack scenario against a running twin from one place, instead of
juggling standalone scripts across terminals. This is orchestration only
-- every attack's actual mechanism still lives in hvac_twin.attacks; the
console just gives each one a uniform start/stop/status surface and holds
the small amount of state (a running MITM proxy, an in-progress flood)
that a one-shot script doesn't need to track. Ground truth vs. what's
displayed is still whatever the twin's own historian/event log records --
the console doesn't touch either; it only triggers the same
unauthenticated Modbus traffic a real attacker would send.

    uv run uvicorn hvac_twin.console:app --port 8000

    curl -X POST localhost:8000/attacks/setpoint-spoof/start \
        -H 'content-type: application/json' -d '{"setpoint": 900}'
    curl -X POST localhost:8000/attacks/mitm-proxy/start \
        -H 'content-type: application/json' -d '{"spoof_temp": 75.0, "hide_alarm": true}'
    curl -X POST localhost:8000/attacks/mitm-proxy/stop
    curl localhost:8000/attacks

No auth of its own -- matches the "unauthenticated by design" theme of
everything else in this repo, since it's instructor-only tooling, not
attacker-facing. Revisit if this ever needs to be reachable by anyone
other than the instructor running it.
"""

from __future__ import annotations

import threading
from dataclasses import asdict
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from hvac_twin.attacks import alarm_mask, compromised_ews, dos_flood, modbus_terminal, setpoint_spoof
from hvac_twin.attacks.mitm_proxy import (
    FUNC_READ_COILS,
    FUNC_READ_INPUT_REGISTERS,
    MitmProxy,
    SpoofRule,
)
from hvac_twin.defenses.catalog import CATALOG

app = FastAPI(title="hvac-twin attack console")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SetpointSpoofRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5020
    setpoint: float = 900.0


class AlarmMaskRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5020
    threshold: float = 999.0


class MitmProxyRequest(BaseModel):
    listen_host: str = "127.0.0.1"
    listen_port: int = 5021
    target_host: str = "127.0.0.1"
    target_port: int = 5020
    spoof_temp: float | None = None
    hide_alarm: bool = False


class DosFloodRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5020
    connections: int = 50
    duration_s: float = 15.0


class CompromisedEwsRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5040
    setpoint: float = 0.0
    zones: list[str] = ["room_1", "room_2", "room_3"]


class ScenarioStatus(BaseModel):
    name: str
    state: Literal["idle", "running", "done", "error"]
    detail: str | None = None


class ModbusExecRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5020
    unit_id: int = 1
    operation: Literal[
        "read_coils",
        "read_discrete_inputs",
        "read_holding_registers",
        "read_input_registers",
        "write_coil",
        "write_coils",
        "write_register",
        "write_registers",
    ]
    address: int = 0
    quantity: int = 1
    values: list[int] | None = None


class ModbusExecResult(BaseModel):
    ok: bool
    values: list[Any] | None = None


_lock = threading.Lock()
_state: dict[str, ScenarioStatus] = {
    "setpoint-spoof": ScenarioStatus(name="setpoint-spoof", state="idle"),
    "alarm-mask": ScenarioStatus(name="alarm-mask", state="idle"),
    "mitm-proxy": ScenarioStatus(name="mitm-proxy", state="idle"),
    "dos-flood": ScenarioStatus(name="dos-flood", state="idle"),
    "compromised-ews": ScenarioStatus(name="compromised-ews", state="idle"),
}
_mitm_proxy: MitmProxy | None = None
_dos_flood_stop: threading.Event | None = None


@app.get("/attacks", response_model=list[ScenarioStatus])
def list_attacks() -> list[ScenarioStatus]:
    with _lock:
        return list(_state.values())


@app.get("/attacks/{name}", response_model=ScenarioStatus)
def get_attack(name: str) -> ScenarioStatus:
    with _lock:
        if name not in _state:
            raise HTTPException(404, f"unknown scenario {name!r}")
        return _state[name]


@app.get("/defenses/catalog", response_model=list[dict[str, Any]])
def get_defenses_catalog() -> list[dict[str, Any]]:
    return [asdict(d) for d in CATALOG]


@app.post("/modbus/exec", response_model=ModbusExecResult)
def exec_modbus(req: ModbusExecRequest) -> ModbusExecResult:
    try:
        result = modbus_terminal.execute(
            req.host,
            req.port,
            req.operation,
            req.address,
            unit_id=req.unit_id,
            quantity=req.quantity,
            values=req.values,
        )
    except (ConnectionError, RuntimeError) as exc:
        raise HTTPException(502, str(exc)) from exc
    return ModbusExecResult(ok=result["ok"], values=result["values"])


@app.post("/attacks/setpoint-spoof/start", response_model=ScenarioStatus)
def start_setpoint_spoof(req: SetpointSpoofRequest) -> ScenarioStatus:
    try:
        detail = setpoint_spoof.spoof_setpoint(req.host, req.port, req.setpoint)
    except (ConnectionError, RuntimeError) as exc:
        with _lock:
            _state["setpoint-spoof"] = ScenarioStatus(
                name="setpoint-spoof", state="error", detail=str(exc)
            )
        raise HTTPException(502, str(exc)) from exc
    with _lock:
        _state["setpoint-spoof"] = ScenarioStatus(
            name="setpoint-spoof", state="done", detail=detail
        )
        return _state["setpoint-spoof"]


@app.post("/attacks/alarm-mask/start", response_model=ScenarioStatus)
def start_alarm_mask(req: AlarmMaskRequest) -> ScenarioStatus:
    try:
        detail = alarm_mask.mask_alarm(req.host, req.port, req.threshold)
    except (ConnectionError, RuntimeError) as exc:
        with _lock:
            _state["alarm-mask"] = ScenarioStatus(name="alarm-mask", state="error", detail=str(exc))
        raise HTTPException(502, str(exc)) from exc
    with _lock:
        _state["alarm-mask"] = ScenarioStatus(name="alarm-mask", state="done", detail=detail)
        return _state["alarm-mask"]


@app.post("/attacks/compromised-ews/start", response_model=ScenarioStatus)
def start_compromised_ews(req: CompromisedEwsRequest) -> ScenarioStatus:
    try:
        detail = compromised_ews.pivot_zone_setpoints(
            req.host, req.port, req.setpoint, tuple(req.zones)
        )
    except (ConnectionError, RuntimeError) as exc:
        with _lock:
            _state["compromised-ews"] = ScenarioStatus(
                name="compromised-ews", state="error", detail=str(exc)
            )
        raise HTTPException(502, str(exc)) from exc
    with _lock:
        _state["compromised-ews"] = ScenarioStatus(
            name="compromised-ews", state="done", detail=detail
        )
        return _state["compromised-ews"]


@app.post("/attacks/mitm-proxy/start", response_model=ScenarioStatus)
def start_mitm_proxy(req: MitmProxyRequest) -> ScenarioStatus:
    global _mitm_proxy
    with _lock:
        if _mitm_proxy is not None:
            raise HTTPException(409, "mitm-proxy is already running")
        rules: list[SpoofRule] = []
        if req.spoof_temp is not None:
            rules.append(
                SpoofRule(FUNC_READ_INPUT_REGISTERS, address=0, value=round(req.spoof_temp * 10))
            )
        if req.hide_alarm:
            rules.append(SpoofRule(FUNC_READ_COILS, address=0, value=0))
        if not rules:
            raise HTTPException(400, "nothing to spoof: set spoof_temp and/or hide_alarm")

        proxy = MitmProxy(req.listen_host, req.listen_port, req.target_host, req.target_port, rules)
        try:
            proxy.start()
        except OSError as exc:
            _state["mitm-proxy"] = ScenarioStatus(name="mitm-proxy", state="error", detail=str(exc))
            raise HTTPException(502, str(exc)) from exc
        _mitm_proxy = proxy
        _state["mitm-proxy"] = ScenarioStatus(
            name="mitm-proxy",
            state="running",
            detail=f"listening on {proxy.listen_host}:{proxy.listen_port} "
            f"-> {req.target_host}:{req.target_port}",
        )
        return _state["mitm-proxy"]


@app.post("/attacks/mitm-proxy/stop", response_model=ScenarioStatus)
def stop_mitm_proxy() -> ScenarioStatus:
    global _mitm_proxy
    with _lock:
        if _mitm_proxy is None:
            raise HTTPException(409, "mitm-proxy is not running")
        _mitm_proxy.stop()
        _mitm_proxy = None
        _state["mitm-proxy"] = ScenarioStatus(name="mitm-proxy", state="idle")
        return _state["mitm-proxy"]


def _run_dos_flood_background(
    host: str, port: int, connections: int, duration_s: float, stop_event: threading.Event
) -> None:
    global _dos_flood_stop
    total = dos_flood.run_flood(
        host, port, connections=connections, duration_s=duration_s, stop_event=stop_event
    )
    with _lock:
        _dos_flood_stop = None
        _state["dos-flood"] = ScenarioStatus(
            name="dos-flood", state="done", detail=f"{total} request/response round-trips"
        )


@app.post("/attacks/dos-flood/start", response_model=ScenarioStatus)
def start_dos_flood(req: DosFloodRequest) -> ScenarioStatus:
    global _dos_flood_stop
    with _lock:
        if _state["dos-flood"].state == "running":
            raise HTTPException(409, "dos-flood is already running")
        # Set before the background thread starts, not inside it -- otherwise
        # a stop() called right after start() returns can race the new
        # thread's first scheduled instruction and see _dos_flood_stop still
        # None, even though the API already reported state="running".
        stop_event = threading.Event()
        _dos_flood_stop = stop_event
        _state["dos-flood"] = ScenarioStatus(name="dos-flood", state="running")
    threading.Thread(
        target=_run_dos_flood_background,
        args=(req.host, req.port, req.connections, req.duration_s, stop_event),
        daemon=True,
    ).start()
    with _lock:
        return _state["dos-flood"]


@app.post("/attacks/dos-flood/stop", response_model=ScenarioStatus)
def stop_dos_flood() -> ScenarioStatus:
    with _lock:
        stop_event = _dos_flood_stop
        if stop_event is None:
            raise HTTPException(409, "dos-flood is not running")
        stop_event.set()
        _state["dos-flood"] = ScenarioStatus(
            name="dos-flood", state="running", detail="stop requested"
        )
        return _state["dos-flood"]
