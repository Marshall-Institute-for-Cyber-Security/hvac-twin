"""Extensible catalog of defense metadata for the student-facing Defenses
page: what mitigations exist, what they actually do and don't catch, and
whether a student can control them live from a room's own HMI. Adding a
new defense means adding one DefenseDescriptor here -- the catalog
endpoint and the frontend page that renders it need no other change."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DefenseDescriptor:
    id: str
    title: str
    summary: str
    how_it_works: str
    mitigates: tuple[str, ...] = field(default_factory=tuple)
    live_control: bool = False


CATALOG: tuple[DefenseDescriptor, ...] = (
    DefenseDescriptor(
        id="auth-proxy",
        title="Auth / Allowlist Proxy",
        summary=(
            "Filters Modbus connections by source IP and function code "
            "before they reach the real device."
        ),
        how_it_works=(
            "Point every client at the proxy instead of the twin's real "
            "port. A disallowed IP is refused outright; a disallowed "
            "function code gets a Modbus error, not a forward."
        ),
        mitigates=("setpoint-spoof", "alarm-mask", "compromised-ews"),
        live_control=True,
    ),
    DefenseDescriptor(
        id="anomaly-detection",
        title="Anomaly Detection",
        summary="Flags implausible rate-of-change jumps in a tag's recorded history.",
        how_it_works=(
            "Scans the historian for two consecutive samples that change "
            "faster than a set limit. Detection only -- it can flag a jump, "
            "not block the write that caused it."
        ),
        mitigates=("setpoint-spoof", "alarm-mask", "compromised-ews"),
        live_control=True,
    ),
)
