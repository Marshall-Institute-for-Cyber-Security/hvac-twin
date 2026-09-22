"""Runs an hvac_twin project file as a live process: real-time paced, with
its Modbus slave server (if configured) listening on a real socket. This
is what makes a twin an actual target for Phase 3 attack scripts, rather
than something only reachable in-process the way the test suite drives
it -- DigiTwin's own `digitwin run` CLI scans a project file and exits; it
never opens the Modbus slave or paces in real time.

    uv run python -m hvac_twin.live_runner examples/server_closet_controlled.toml
    uv run python -m hvac_twin.live_runner examples/server_closet_controlled.toml --seconds 300

Runs until interrupted (Ctrl-C) if --seconds is omitted. --host/--port
override the project file's own [modbus.slave_server] settings, mainly so
tests (and anyone running more than one twin at once) can pick a free
port instead of colliding on the file's default.

Auto-commissions every accept-mapped tag before the first tick (see
_commission_accept_tags) unless --cold-start says not to. Without this,
ModbusSlaveServer.sync() -- which runs every tick regardless of whether a
client ever connects -- discards each accept-mapped tag's TOML `initial =`
on tick 1, reading back 0 (the register store's default) instead; see
examples/server_closet_controlled.toml's [modbus.slave_server] comment
for the concrete symptom this caused before this existed. --cold-start
is there for the rare case that "uncommissioned, defaults included" is
itself the point (e.g. demonstrating the gotcha, or a scenario that wants
a genuinely fresh controller).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from digitwin import ExecutiveMode
from digitwin.config import load_project
from digitwin.executive import Executive

import hvac_twin  # noqa: F401  (side effect: registers components with DigiTwin)


def _commission_accept_tags(sim: Executive) -> None:
    """Seed every accept-mapped tag's register with that tag's own current
    PLC value -- its TOML `initial =`, since this runs before anything has
    ticked -- so the first automatic sync() reflects it back unchanged
    instead of overwriting it with the register store's zero default.

    Reaches into ModbusSlaveServer's private `_store`: the same kind of
    documented wart as hvac_twin/registry.py's reach into DigiTwin's
    plant/program registries, for the same reason -- there's no public
    "pre-seed the accept side" API yet. `_store` is explicitly designed to
    work without a live server or pymodbus (see its own docstring in
    DigiTwin), so this needs neither `.start()` nor the network.
    """
    modbus_slave = sim.modbus_slave
    if modbus_slave is None:
        return
    for tag_name, reg in modbus_slave.accept.items():
        value = sim.plc.tags[tag_name].value
        modbus_slave._store.write(reg.kind, reg.address, reg.encode(value))



def start_twin(
        project: Path,
        *,
        host: str | None = None,
        port: int | None = None,
        auto_commission: bool = True,
) -> Executive:
    """Load `project`, set it to real-time pacing, and start its Modbus
    slave on a real socket -- everthing run_live() and the HMI backend
    both need before they can drive ticks themselves. Does not tick or
    block ; call sim.tick()/sim.run_for()/sim.run() (or hand the running
    sim to a background thread, as hvac_twin.hmi does) to actually
    advance it."""
    sim = load_project(project)
    sim.mode = ExecutiveMode.REAL_TIME

    if sim.modbus_slave is not None:
        if host is not None:
            sim.modbus_slave.host = host
        if port is not None:
            sim.modbus_slave.port = port
        if auto_commission:
            _commission_accept_tags(sim)
        sim.modbus_slave.sync()
        sim.modbus_slave.start()
        print(f"Modbus slave listening on {sim.modbus_slave.host}:{sim.modbus_slave.port}")

    return sim


def run_live(
    project: Path,
    *,
    host: str | None = None,
    port: int | None = None,
    seconds: float | None = None,
    auto_commission: bool = True,
) -> Executive:
    """Load `project`, start it (see start_twin), and run it real-time-paced
    for `seconds` of simulated time (indefinitely, until Ctrl-C, if `seconds`
    is None). Returns the Executive once stopped.
    """
    sim = start_twin(project, host=host, port=port, auto_commission=auto_commission)
    try:
        if seconds is not None:
            sim.run_for(seconds)
        else:
            while True:
                sim.tick()
    except KeyboardInterrupt:
        pass
    finally:
        if sim.modbus_slave is not None:
            sim.modbus_slave.stop()

    return sim


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="path to a .toml project file")
    parser.add_argument("--host", default=None, help="override [modbus.slave_server] host")
    parser.add_argument(
        "--port", type=int, default=None, help="override [modbus.slave_server] port"
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="simulated seconds to run (default: run until Ctrl-C)",
    )
    parser.add_argument(
        "--cold-start",
        action="store_true",
        help="skip auto-commissioning; accept-mapped tags start at their register defaults (0)",
    )
    args = parser.parse_args(argv)

    if args.seconds is None:
        print(f"{args.project.name}: starting (Ctrl-C to stop)")
    else:
        print(f"{args.project.name}: running for {args.seconds:.0f}s simulated")

    sim = run_live(
        args.project,
        host=args.host,
        port=args.port,
        seconds=args.seconds,
        auto_commission=not args.cold_start,
    )
    print(f"stopped after {sim.scan_count} scans, t={sim.elapsed:.1f}s simulated")


if __name__ == "__main__":
    main()
