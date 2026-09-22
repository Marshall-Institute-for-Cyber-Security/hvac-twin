"""Shared helper for attack scripts that talk to a live twin as a plain
Modbus TCP client -- not attack logic itself, just the "wait for the real
socket to accept a connection" boilerplate that setpoint_spoof.py,
alarm_mask.py, and the attack console all needed identically."""

from __future__ import annotations

import time
from typing import Any


def wait_for_connection(client: Any, host: str, port: int, timeout_s: float = 3.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not client.connect():
        if time.monotonic() > deadline:
            raise ConnectionError(f"could not connect to {host}:{port}")
        time.sleep(0.05)
