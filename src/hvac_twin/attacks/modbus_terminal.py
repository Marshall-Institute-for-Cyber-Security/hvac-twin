"""Red-team console tool: a free-form Modbus TCP command executor, not a
canned attack scenario. Every other attacks/ module does one fixed thing
against one fixed address; this is the raw primitive underneath all of
them, exposed directly so a student can build their own request instead
of only running the five pre-built ones -- e.g. probing an address the
canned scenarios don't touch, or hand-crafting the exact write
setpoint_spoof.py already does but with a different value/address.

    uv run python -m hvac_twin.attacks.modbus_terminal \
        --host 127.0.0.1 --port 5020 \
        --operation read_input_registers --address 0 --quantity 1
"""

from __future__ import annotations

import argparse
from typing import Any, Literal

from hvac_twin.attacks._client import wait_for_connection

Operation = Literal[
    "read_coils",
    "read_discrete_inputs",
    "read_holding_registers",
    "read_input_registers",
    "write_coil",
    "write_coils",
    "write_register",
    "write_registers",
]

_READ_OPS: tuple[Operation, ...] = (
    "read_coils",
    "read_discrete_inputs",
    "read_holding_registers",
    "read_input_registers",
)
_WRITE_OPS: tuple[Operation, ...] = ("write_coil", "write_coils", "write_register", "write_registers")


def execute(
    host: str,
    port: int,
    operation: Operation,
    address: int,
    *,
    unit_id: int = 1,
    quantity: int = 1,
    values: list[int] | None = None,
) -> dict[str, Any]:
    """Send one Modbus TCP request built from plain, student-supplied
    parameters and return a JSON-serializable result -- raises
    ConnectionError/RuntimeError rather than exiting the process, same
    contract as every other attacks/ module, so this is safe to call from
    a long-running console."""
    from pymodbus.client import ModbusTcpClient

    client: Any = ModbusTcpClient(host, port=port, timeout=2.0)
    try:
        wait_for_connection(client, host, port)
        if operation == "read_coils":
            result = client.read_coils(address=address, count=quantity, device_id=unit_id)
        elif operation == "read_discrete_inputs":
            result = client.read_discrete_inputs(address=address, count=quantity, device_id=unit_id)
        elif operation == "read_holding_registers":
            result = client.read_holding_registers(address=address, count=quantity, device_id=unit_id)
        elif operation == "read_input_registers":
            result = client.read_input_registers(address=address, count=quantity, device_id=unit_id)
        elif operation == "write_coil":
            if not values:
                raise RuntimeError("write_coil needs one value")
            result = client.write_coil(address=address, value=bool(values[0]), device_id=unit_id)
        elif operation == "write_coils":
            if not values:
                raise RuntimeError("write_coils needs at least one value")
            result = client.write_coils(
                address=address, values=[bool(v) for v in values], device_id=unit_id
            )
        elif operation == "write_register":
            if not values:
                raise RuntimeError("write_register needs one value")
            result = client.write_register(address=address, value=int(values[0]), device_id=unit_id)
        else:
            if not values:
                raise RuntimeError("write_registers needs at least one value")
            result = client.write_registers(
                address=address, values=[int(v) for v in values], device_id=unit_id
            )

        if result.isError():
            raise RuntimeError(f"{operation} failed: {result}")

        if operation in ("read_coils", "read_discrete_inputs"):
            return {"ok": True, "values": list(result.bits[:quantity])}
        if operation in _READ_OPS:
            return {"ok": True, "values": list(result.registers)}
        return {"ok": True, "values": None}
    finally:
        client.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5020)
    parser.add_argument("--unit-id", type=int, default=1)
    parser.add_argument("--operation", required=True, choices=list(_READ_OPS + _WRITE_OPS))
    parser.add_argument("--address", type=int, required=True)
    parser.add_argument("--quantity", type=int, default=1, help="read count")
    parser.add_argument("--value", type=int, action="append", help="one write value; repeat for multiple")
    args = parser.parse_args(argv)

    try:
        result = execute(
            args.host,
            args.port,
            args.operation,
            args.address,
            unit_id=args.unit_id,
            quantity=args.quantity,
            values=args.value,
        )
    except (ConnectionError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(result)


if __name__ == "__main__":
    main()
