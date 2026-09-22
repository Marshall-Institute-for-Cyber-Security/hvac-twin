"""Phase 5 defense #2: physically-implausible rate-of-change detection
over historian data.

Scope, stated plainly: this only ever sees what's already in DigiTwin's
own Historian -- the twin's real internal plc.tags, sampled once per
tick. That means it can catch setpoint_spoof, alarm_mask, and
compromised_ews (each writes a real, huge, instantaneous jump into a
real tag) -- but it can never catch mitm_proxy (which never touches the
twin's actual state, only what a remote client sees on the wire) or
dos_flood (which never touches any tag at all). Different attacks need
different defenses; this one's job is the "quiet setpoint drift" and
"instant absurd value" cases, not all five.

No new DigiTwin primitives -- this is a pure function over
Historian.series(), the same query API /historian/{tag} already serves.
"""

from __future__ import annotations

from dataclasses import dataclass

from digitwin.historian import Historian


@dataclass(frozen=True)
class RateAnomaly:
    tag: str
    from_timestamp: float
    to_timestamp: float
    from_value: float
    to_value: float
    rate: float
    limit: float


def find_rate_anomalies(
    historian: Historian, tag: str, *, max_rate_per_s: float
) -> list[RateAnomaly]:
    """Scan `tag`'s recorded series for any consecutive pair of samples
    whose rate of change exceeds `max_rate_per_s`. `max_rate_per_s` is a
    caller-supplied, tag-specific judgment call -- what's a physically or
    operationally plausible rate for one tag (a slow-moving temperature)
    is nonsense for another (a setpoint an operator sets once and rarely
    touches), so this function has no built-in notion of "normal" at all."""
    anomalies: list[RateAnomaly] = []
    previous: tuple[float, float] | None = None
    for timestamp, value in historian.series(tag):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if previous is not None:
            prev_timestamp, prev_value = previous
            dt = timestamp - prev_timestamp
            if dt > 0:
                rate = abs(value - prev_value) / dt
                if rate > max_rate_per_s:
                    anomalies.append(
                        RateAnomaly(
                            tag,
                            prev_timestamp,
                            timestamp,
                            prev_value,
                            float(value),
                            rate,
                            max_rate_per_s,
                        )
                    )
        previous = (timestamp, float(value))
    return anomalies
