"""hvac_twin.defenses.auth_proxy, exercised against a real Modbus TCP
proxy in front of a live twin -- the defensive counterpart to
attacks/mitm_proxy.py: same shape (a TCP proxy in front of the twin's
real Modbus port), opposite job. Confirms the proxy is a true
passthrough when disabled (today's undefended baseline, unchanged), that
each allowlist can be toggled independently, and that the function-code
allowlist alone is enough to make setpoint_spoof.py's attack -- which
test_setpoint_spoof.py proves succeeds unconditionally against an
undefended twin -- actually fail."""

from __future__ import annotations

import socket
import time
from pathlib import Path
from typing import Any

import pytest
from digitwin.config import load_project

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)
from hvac_twin.attacks import setpoint_spoof
from hvac_twin.defenses.auth_proxy import AuthProxy

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


def _start_twin() -> Any:
    sim = load_project(_PROJECT_PATH)
    assert sim.modbus_slave is not None
    sim.modbus_slave.port = _free_port()
    sim.modbus_slave.sync()
    sim.modbus_slave.start()
    return sim


def test_disabled_proxy_is_a_transparent_passthrough() -> None:
    pytest.importorskip("pymodbus")
    from pymodbus.client import ModbusTcpClient

    sim = _start_twin()
    proxy = AuthProxy("127.0.0.1", _free_port(), "127.0.0.1", sim.modbus_slave.port, enabled=False)
    proxy.start()
    client: Any = ModbusTcpClient("127.0.0.1", port=proxy.listen_port, timeout=2.0)
    try:
        _connect(client)
        result = client.read_input_registers(address=0, count=1, device_id=1)
        assert not result.isError()
    finally:
        client.close()
        proxy.stop()
        sim.modbus_slave.stop()


def test_source_ip_allowlist_refuses_a_disallowed_client() -> None:
    pytest.importorskip("pymodbus")
    from pymodbus.client import ModbusTcpClient

    sim = _start_twin()
    proxy = AuthProxy(
        "127.0.0.1",
        _free_port(),
        "127.0.0.1",
        sim.modbus_slave.port,
        enabled=True,
        allowed_source_ips=frozenset({"10.0.0.1"}),  # not loopback -- this test's client is refused
    )
    proxy.start()
    client: Any = ModbusTcpClient("127.0.0.1", port=proxy.listen_port, timeout=1.0)
    try:
        client.connect()  # the TCP handshake may still succeed -- the proxy closes right after
        try:
            result = client.read_input_registers(address=0, count=1, device_id=1)
            assert result.isError()
        except OSError:
            pass  # also an acceptable failure mode (e.g. a raw connection reset on Windows) --
            # the point is it never succeeds, not the exact shape of the failure
    finally:
        client.close()
        proxy.stop()
        sim.modbus_slave.stop()


def test_function_code_allowlist_blocks_writes_but_not_reads() -> None:
    pytest.importorskip("pymodbus")
    from pymodbus.client import ModbusTcpClient

    sim = _start_twin()
    proxy = AuthProxy(
        "127.0.0.1",
        _free_port(),
        "127.0.0.1",
        sim.modbus_slave.port,
        enabled=True,
        allowed_function_codes=frozenset({3, 4}),  # reads only
    )
    proxy.start()
    client: Any = ModbusTcpClient("127.0.0.1", port=proxy.listen_port, timeout=2.0)
    try:
        _connect(client)
        read_result = client.read_input_registers(address=0, count=1, device_id=1)
        assert not read_result.isError()

        write_result = client.write_registers(address=0, values=[9000], device_id=1)
        assert write_result.isError()
    finally:
        client.close()
        proxy.stop()
        sim.modbus_slave.stop()


def test_function_code_allowlist_defeats_the_setpoint_spoof_attack() -> None:
    """The exact scenario test_setpoint_spoof.py proves succeeds against an
    undefended twin -- now blocked by a mitigation the student turned on.
    Commissioning happens directly against the twin's real port (the
    trusted internal path an engineer would use, same as every other
    controlled-closet test); the attack is attempted through the
    defended, external-facing proxy port instead."""
    pytest.importorskip("pymodbus")
    from pymodbus.client import ModbusTcpClient

    sim = _start_twin()
    proxy = AuthProxy(
        "127.0.0.1",
        _free_port(),
        "127.0.0.1",
        sim.modbus_slave.port,
        enabled=True,
        allowed_function_codes=frozenset({3, 4}),
    )
    proxy.start()
    try:
        commission: Any = ModbusTcpClient("127.0.0.1", port=sim.modbus_slave.port, timeout=1.0)
        try:
            _connect(commission)
            commission.write_registers(address=0, values=[750], device_id=1)
        finally:
            commission.close()
        sim.run(2)
        assert sim.plc.read("setpoint_tenths") == 750

        with pytest.raises(SystemExit):
            setpoint_spoof.main(
                ["--host", "127.0.0.1", "--port", str(proxy.listen_port), "--setpoint", "900"]
            )
        sim.run(5)
        assert sim.plc.read("setpoint_tenths") == 750  # unchanged -- the attack was blocked
    finally:
        proxy.stop()
        sim.modbus_slave.stop()
