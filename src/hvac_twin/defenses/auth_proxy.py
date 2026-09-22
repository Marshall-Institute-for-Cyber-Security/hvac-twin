"""Phase 5 defense #1: an auth/allowlist proxy in front of the twin's real Modbus
TCP port.

Every attack in Phase 3 works because DigiTwin's ModbusSlaveServer has no
concept of authentication -- by design, mirroring a real device's Modbus
map. This proxy is the mitigation a student adds *in front of* that real
port: point it at the twin's actual Modbus address, then point everything
else (attackers and legitimate clients alike) at the proxy's address
instead. With `enabled=False` it's a transparent passthrough -- the
undefended baseline, unchanged from every earlier scenario. With
`enabled=True`, it applies two independently toggleable allowlists:

- source IP: a connection from an address not in `allowed_source_ips`
  is refused immediately, before a single byte of Modbus is exchanged --
  the same effect a real network ACL/firewall rule would have.
- function code: a request whose function code isn't in
  `allowed_function_codes` gets a real Modbus exception response
  (ILLEGAL FUNCTION) instead of being forwarded. The connection itself
  stays open -- a legitimate client sending one disallowed request
  shouldn't be dropped entirely, just refused that one thing.

Structurally this mirrors attacks/mitm_proxy.py (same MBAP-parsing, same
per-connection two-thread relay) -- offense and defense share a shape
here because a Modbus TCP proxy is the same primitive either way; what
differs is what it does with what it sees.

    uv run python -m hvac_twin.defenses.auth_proxy \
        --target-port 5020 --listen-port 5022 \
        --allow-ip 127.0.0.1 --allow-function 3 --allow-function 4
"""

from __future__ import annotations

import argparse
import socket
import struct
import threading
import time
from dataclasses import dataclass, field

_MBAP_LEN = 7
_EXCEPTION_BIT = 0x80
_ILLEGAL_FUNCTION = 1


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _exception_response(transaction_id: int, unit_id: int, function_code: int) -> bytes:
    pdu = struct.pack(">BB", function_code | _EXCEPTION_BIT, _ILLEGAL_FUNCTION)
    header = struct.pack(">HHHB", transaction_id, 0, len(pdu) + 1, unit_id)
    return header + pdu


def _relay_client_to_target(
        client_sock: socket.socket,
        target_sock: socket.socket,
        allowed_function_codes: frozenset[int] | None,
) -> None:
    """Forward every request unmodified, except a request whose function
    code isn't allowed gets an exception response instead of being
    forwarded -- the connection itself stays open."""
    try:
        while True:
            header = _recv_exact(client_sock, _MBAP_LEN)
            if header is None:
                break
            transaction_id, _protocol_id, length, unit_id = struct.unpack(">HHHB", header)
            if length < 2:
                break  # malformed MBAP: not even a function code follows
            pdu = _recv_exact(client_sock, length - 1)
            if pdu is None:
                break
            function_code = pdu[0]
            if allowed_function_codes is not None and function_code not in allowed_function_codes:
                try:
                    client_sock.sendall(_exception_response(transaction_id, unit_id, function_code))
                except OSError:
                    break
                continue
            try:
                target_sock.sendall(header + pdu)
            except OSError:
                break
    finally:
        # Unblock the peer relay thread's blocking recv() so the connection
        # always winds down instead of leaving _handle_connection's join()
        # waiting forever on a normal one-sided disconnect.
        try:
            target_sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def _relay_target_to_client(target_sock: socket.socket, client_sock: socket.socket) -> None:
    try:
        while True:
            header = _recv_exact(target_sock, _MBAP_LEN)
            if header is None:
                break
            _, _, length, _ = struct.unpack(">HHHB", header)
            if length < 2:
                break
            pdu = _recv_exact(target_sock, length - 1)
            if pdu is None:
                break
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
        client_sock: socket.socket,
        client_addr: tuple[str, int],
        target_host: str,
        target_port: int,
        allowed_source_ips: frozenset[str] | None,
        allowed_function_codes: frozenset[int] | None,
) -> None:
    if allowed_source_ips is not None and client_addr[0] not in allowed_source_ips:
        client_sock.close()
        return
    try:
        target_sock = socket.create_connection((target_host, target_port))
    except OSError:
        client_sock.close()
        return
    to_target = threading.Thread(
        target=_relay_client_to_target,
        args=(client_sock, target_sock, allowed_function_codes),
        daemon=True
    )
    to_client = threading.Thread(
        target=_relay_target_to_client, args=(target_sock, client_sock), daemon=True
    )
    to_target.start()
    to_client.start()
    to_target.join()
    to_client.join()
    client_sock.close()
    target_sock.close()


@dataclass
class AuthProxy:
    """`start()`/`stop()` mirror ModbusSlaveServer's own naming -- same
    idempotent-thread-lifecycle shape as attacks/mitm_proxy.py's MitmProxy."""

    listen_host: str
    listen_port: int
    target_host: str
    target_port: int
    enabled: bool = True
    allowed_source_ips: frozenset[str] | None = None
    allowed_function_codes: frozenset[int] | None = None
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
        server.settimeout(0.2)
        self.listen_port = server.getsockname()[1]
        self._server = server
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                client_sock, client_addr = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            source_ips = self.allowed_source_ips if self.enabled else None
            function_codes = self.allowed_function_codes if self.enabled else None
            threading.Thread(
                target=_handle_connection,
                args=(
                    client_sock,
                    client_addr,
                    self.target_host,
                    self.target_port,
                    source_ips,
                    function_codes,
                ),
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
    parser.add_argument("--listen-port", type=int, default=5022)
    parser.add_argument("--target-host", default="127.0.0.1")
    parser.add_argument("--target-port", type=int, default=5020)
    parser.add_argument(
        "--allow-ip", action="append", default=[], help="repeatable; omit to allow any source IP"
    )
    parser.add_argument(
        "--allow-function",
        action="append",
        type=int,
        default=[],
        help="repeatable Modbus function code; omit to allow any",
    )
    parser.add_argument(
        "--disabled",
        action="store_true",
        help="start as a transparent passthrough (undefended baseline)",
    )
    args = parser.parse_args(argv)

    proxy = AuthProxy(
        args.listen_host,
        args.listen_port,
        args.target_host,
        args.target_port,
        enabled=not args.disabled,
        allowed_source_ips=frozenset(args.allow_ip) if args.allow_ip else None,
        allowed_function_codes=frozenset(args.allow_function) if args.allow_function else None,
    )
    proxy.start()
    print(
        f"auth proxy: {args.listen_host}:{proxy.listen_port} -> "
        f"{args.target_host}:{args.target_port} "
        f"({'ENFORCING' if proxy.enabled else 'PASSTHROUGH'})"
    )
    if proxy.enabled:
        ips = sorted(proxy.allowed_source_ips) if proxy.allowed_source_ips else "any"
        codes = sorted(proxy.allowed_function_codes) if proxy.allowed_function_codes else "any"
        print(f"  allowed source IPs: {ips}")
        print(f"  allowed function codes: {codes}")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        proxy.stop()


if __name__ == "__main__":
    main()

