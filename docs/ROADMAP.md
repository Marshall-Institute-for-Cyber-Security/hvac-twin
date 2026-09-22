# HVAC Digital Twin — Roadmap

## Starting point: DigiTwin already exists

`C:\Users\quesenberr22\Documents\DigiTwin` is not a prototype — it's a mature,
tested (~205 tests, mypy --strict, zero runtime deps) soft-PLC + physics
framework that already implements two of the three layers in the original
architecture sketch:

| Original plan layer | DigiTwin today |
|---|---|
| Physics engine | `plant/` — `PlantModel` protocol, `CompositePlant`, Euler-integrated components (`Tank`, `Valve`, `Motor`, `Pump`, `ThermalMass`, `PIDLoop`, `Integrator`, `TransportDelay`, `PipeSegment`, `AnalogSensor`, `DiscreteSensor`) |
| Control layer / attack surface | `plc.py` (abstract soft-PLC, 3-phase scan, firmware realism: first-scan bit, retentive tags, cold/warm/power-cycle, watchdog), `hardware.py` (`HardwareProfile`, address-syntax strategy), `models/` (`PLC_Generic`, `PLC_Schneider_TM221CE16T`), `adapters/modbus.py` (Modbus TCP **master** transport + **slave** server, tested against real `pymodbus` and validated against a physical M221 + real HMI) |
| Authoring | `config.py` — a twin is a TOML project file, not hand-wired Python (`docs/BUILDING_A_TWIN.md`) |
| Observability | `historian.py`, `events.py`, `snapshot.py` (time-travel), `replay.py` (recorded-I/O capture/diff) |
| HMI / dashboard | **not built** — DigiTwin's own roadmap defers this explicitly |
| Attack scenarios | **not built** — DigiTwin's own roadmap explicitly puts "dataset generation, attack-path analysis" **out of scope for that repo**, and only commits to a generic fault-injection *primitive* (P4: stuck/offset/drift/noise/frozen/dropout — not yet landed) |

**Consequence for this project:** don't rebuild the physics/control layers.
Consume DigiTwin as a dependency and build the HVAC-specific physics
components, the attack framework, and the HMI *here*, in this repo — which is
exactly the boundary DigiTwin's own `ROADMAP.md` asks downstream work to
respect ("Downstream research... builds on this framework and is explicitly
out of scope here").

This also means the effort lines up with DigiTwin's own **P3** ("second twin
as proof of generality... a plant that is **not** a level process — thermal or
motor/conveyor"). A multi-room thermal twin is P3's target case. Building it
here first, then upstreaming the generic pieces, is more useful than
duplicating a parallel thermal engine.

---

## Phase 0 — Wiring & skeleton *(~1-2 days)*

**Goal:** this repo builds, imports DigiTwin, and runs one of DigiTwin's own
example twins end to end, before any HVAC-specific code exists.

- `pyproject.toml` for this repo; add DigiTwin as a dependency — editable
  install (`uv add --editable ../DigiTwin` or `pip install -e`) is simplest
  while both repos move together; a git submodule only if they need to
  version independently later.
- Install the `modbus` extra (`digitwin[modbus]`) and confirm `pymodbus` works
  in this environment.
- Smoke test: load `examples/heated_tank.toml` from DigiTwin through this
  repo's venv, run it, confirm it settles — proves the dependency boundary
  works before building on top of it.
- Decide the package layout: `hvac_twin/plant/`, `hvac_twin/programs/`,
  `hvac_twin/models/` (mirrors DigiTwin's own layout, so anything promoted
  upstream later is a near-verbatim move).
- Mirror DigiTwin's engineering baseline (ruff, mypy --strict, pytest) so
  quality bar and contribution style match — makes eventual upstreaming
  frictionless.

**Done when:** `uv run pytest` passes with zero HVAC code, just the dependency
wired up.

---

## Phase 1 — Multi-room RC thermal physics *(complete)*

**Goal:** a validated, N-room thermal network with no controller — physics
only, matching the ASHRAE-simplified/ISO 13790 approach from the original
brief.

**Gap to close:** DigiTwin's `ThermalMass` (`plant/process.py`) is a single
lumped node with one heater input, clamped to `[0,1]` — it can't carry a
signed, arbitrary-magnitude Watts value the way heat arriving from a warmer
neighbor would need to, so it can't represent inter-room coupling at all.
**Landed:** three new, DigiTwin-idiomatic primitives, composed rather than a
monolithic multi-node subsystem — no changes to DigiTwin itself:

- `HeatFlowLink` — heat exchange between any two temperature signals through
  a resistance (a `PipeSegment` analog, but symmetric — no valve, since heat
  flows whichever way is hotter, not along a commanded direction).
- `ThermalNode` — a lumped mass driven by one net Watts input. No baked-in
  "ambient" or "loss" concept — a room's connection to outdoors is just
  another `HeatFlowLink`, not a special case.
- `WeightedSum` — combines several signed Watts contributors (multiple links,
  plus any fixed equipment load) into the one flux signal a `ThermalNode`
  reads.

An integration test wires all three together (two nodes, one link, two
weighted sums) and confirms they settle at the same capacity-weighted
equilibrium a hand-rolled version of the same physics predicts — proof the
composition, not just each piece in isolation, behaves correctly.

**Scope note — occupancy and solar gain, cut:** the original brief listed
occupancy and solar heat gain alongside outdoor temperature as standard
building-simulation inputs. Cut from this project, not deferred: neither has
a validation anchor the way wall conduction does (there's no "correct" number
for how much heat imaginary occupants add to a fictional room — it would be
an invented schedule dressed up as physics), and neither is something any
attack in Phase 3 targets or any defense in Phase 5 monitors. They'd be
realism borrowed from a building-*energy* simulation goal this project
doesn't have. What a room's temperature actually needs to respond to is
outdoor temperature (real, checkable, and the thing the control loop has to
counteract — the actual point of having a control loop) and, where the
scenario calls for it, a fixed equipment load (the server closet's IT heat,
not a schedule).

**Scope**

- `HeatFlowLink` / `ThermalNode` / `WeightedSum` (above).
- Outdoor boundary: a fixed-temperature signal (defer any live weather-API
  or diurnal-schedule integration — a constant is enough to be the thing
  rooms lose heat to), connected to each room via `HeatFlowLink` like any
  other wall.
- Validate one isolated room's step/settle response against a hand-calculated
  ASHRAE-simplified or ISO 13790 reference trajectory (same rigor as
  DigiTwin's existing analytic-trajectory tests) before trusting the network.
- `examples/office_wing.toml`: N rooms, connecting walls, one outdoor boundary
  node, `noop` program (no controller yet) — proves the physics settles to
  expected steady-state temps with zero control code, mirroring how
  `heated_tank.toml` validated P2.

**Done when:** a multi-room network runs from a project file with no
controller, settles to physically sane steady states, and every new component
has an analytic-trajectory test.

### Flagship room: the server closet

One node in the network should be a **server/IT closet**, not an office —
it's the scenario with real stakes (equipment damage, not just discomfort)
and it exercises a piece of physics none of the office rooms need:

- **Self-heating load**: the server closet's `ThermalNode` gets a roughly
  constant IT heat load as a fixed `bias` term in its `WeightedSum`, not a
  controller-driven signal — the equipment keeps dumping heat whether or not
  cooling is working.
- **Irreversible damage accumulator**: a small new `Excess` primitive
  (`out = max(0, in - threshold)`) feeding an existing `Integrator` clamped
  `0..100`, **with no reset**. This gives a "damage %" signal that only rises
  while the room is over-temp and — unlike the temperature itself — never
  comes back down once the attack is fixed. That irreversibility is the
  point: it's the clearest possible illustration that some ICS attack effects
  are undoable (a spoofed setpoint — just write it back) and some aren't
  (thermal damage already done). No new component category needed beyond
  `Excess`; `Integrator` already exists.
- **Ground truth vs. sensed value**: this room is where the "don't trust the
  display" lesson lands hardest. Every temp node should carry *two* bus
  signals — the physics engine's true value, and the value after it's passed
  through whatever the sensor/PLC/HMI chain reports (which an attack can
  diverge from truth). Design the wiring so both are always available to
  observability (historian/HMI), even though only the sensed value is what
  the control program and a real operator would see.
- Validate this node's time-to-threshold against a hand calc (constant
  overheat rate × time = accumulated excess) the same way as any other
  component.

---

## Phase 2 — HVAC control layer *(the attack surface)* — complete

**Goal:** each room/zone has real setpoint control, and the twin is reachable
over Modbus TCP — DigiTwin's Modbus slave server already exists and is
**unauthenticated by design** (it mirrors a real device's Modbus map, which
has no auth concept), so this phase gets attack scenario #1 "for free."

**Landed:** the flagship server closet, not the office wing, became the
priority twin here — it's the one Phase 3's attacks actually target.
`hvac_twin/programs/crac_bang_bang.py::CracBangBangProgram` is a seal-in
latch (same style as DigiTwin's own `StartStopTankProgram`): CRAC on past
setpoint+deadband, off past setpoint-deadband, holds inside the deadband; a
high-temp alarm is an independent decision from whether cooling is running.
Controller identity: `PLC_Generic`, for now — a real vendor profile (which
would double as DigiTwin's own P3 requirement) is deferred, not abandoned.
No new plant component was needed for the CRAC unit: DigiTwin's own `Motor`
(bool command → ramped 0..1 speed) + `WeightedSum` (speed × max-wattage as a
weighted term) covers it completely. All temperatures the PLC sees are
tenths-of-a-degree integers via `AnalogSensor` — the PLC never touches the
plant's true float temperature. That gap is the concrete form of
"ground truth vs. sensed" this project has been building toward since
Phase 1: `examples/server_closet_controlled.toml` holds a stable cycle
(~73–77°F around a 75°F setpoint) and never approaches its 95°F alarm, while
`test_crac_bang_bang.py`'s last test is this project's first working
attack — writing the `setpoint_tenths` tag with no authentication changes
control behavior immediately, using a mechanism that already exists with
zero extra code.

**Also landed:** `[modbus.slave_server]` on `server_closet_controlled.toml`,
verified over a **real socket** (mirroring DigiTwin's own real-pymodbus test
pattern). The setpoint uses two holding-register addresses on purpose —
publishing and accepting the same tag at the same address is self-defeating,
since publish always overwrites the wire with the tag's current value
before accept reads it back, so a remote write never survives. `pymodbus`
had to actually be installed (`uv sync --extra modbus`); it was declared in
`pyproject.toml` since Phase 0 but never pulled in.

**Also landed:** multi-zone setpoint control for the office wing (the
original target here, deferred while the server closet became the
priority flagship scenario) — `examples/office_wing_controlled.toml` +
`hvac_twin/programs/office_wing_bang_bang.py::OfficeWingBangBangProgram`,
a per-zone bang-bang latch (inverted from the closet's — this is heating,
since outdoor is the cold side) run for all three rooms within one PLC
scan. Kept as a separate `_controlled` project file, same split as the
closet, so `office_wing.toml` still validates Phase 1 physics with zero
controller code. Not exposed over Modbus — that reachability property was
already proven via the closet.

**Done when:** an external Modbus client (a plain `pymodbus` script, standing
in for an HMI) can read the sensed temp/alarm and write the setpoint, and the
twin holds that setpoint under normal conditions. **Met** —
`test_server_closet_modbus.py` proves it over a real socket, and its second
test previews Phase 3 directly: the same unauthenticated write changes
control behavior immediately, with zero new code.

### Phase 2.5 (stretch, optional) — BACnet/IP adapter

BACnet/IP is "more HVAC-authentic" per the original brief, but Modbus alone
already supports every ATT&CK-for-ICS technique listed (spoofing, replay,
MITM, DoS, EWS compromise) — BACnet adds protocol-specific realism, not new
attack classes. Only build `adapters/bacnet.py` (mirroring `modbus.py`'s
client/slave split, via `bacpypes3`) if BACnet-specific object/service
semantics (COV subscriptions, `Who-Is`/`I-Am` discovery, priority arrays) are
a stated learning objective. Treat as a parallel adapter, not a replacement —
keep Modbus as the default, lower-friction path.

---

## Phase 3 — Attack injection framework *(instructor tooling)*

**Goal:** turn the reachable twin into the cyber-range exercise. This is new
code in *this* repo — DigiTwin explicitly excludes it from its own scope.

Map each scenario from the brief to what's actually needed, most of which is
**network-level tooling against the live twin**, not new DigiTwin internals:

| Attack | Implementation | New code needed | Status |
|---|---|---|---|
| Setpoint spoofing | Plain `pymodbus` client writing holding registers | None — already possible today, zero auth on the slave server | **Landed** — `attacks/setpoint_spoof.py` |
| Sensor replay / FDI | Landed as alarm-threshold spoofing rather than a captured-trace replay — `CracBangBangProgram`'s `alarm_threshold_tenths` is itself an accept-mapped tag, so deceiving it needs no `replay.py` capture step | Small: a threshold-spoof script | **Landed** — `attacks/alarm_mask.py` |
| MITM manipulation | A Modbus TCP proxy that rewrites read-response bytes in flight (ARP spoofing itself not implemented — the proxy is reached by pointing a client at its port, the same mechanism the other scripts already rely on) | New: proxy script (this repo, not DigiTwin) | **Landed** — `attacks/mitm_proxy.py` |
| DoS on HMI | Landed as a raw-socket request flood against the slave server's TCP port; impact shown via a legitimate client's degraded read latency (and, verified manually, outright connection timeouts) rather than the executive's `scan_time_ms`/jitter tags — those track scan *compute* time, not the separate Modbus-server thread the flood actually contends with | New: flood script + a dashboard panel to show the effect | **Landed** — `attacks/dos_flood.py` |
| Compromised EWS | Landed as a scripted session against the office wing (not the closet) rather than a separate container: read each zone's setpoint first (legitimate-looking), then write all three at once -- one actor touching every zone in the same breath is what makes it an attack, not the mechanism | New: a small standalone client container | **Landed** — `attacks/compromised_ews.py` |

- Build a lightweight "attack console" service (FastAPI) instructors call to
  start/stop each scenario against a running twin instance — this is the
  piece that makes it a live exercise instead of a set of standalone
  scripts. **Landed** — `hvac_twin/console.py`, covering all five scenarios.
- If DigiTwin's P4 fault primitives (`stuck`/`offset`/`drift`/`noise`/
  `frozen`/`dropout`) have landed upstream by this point, use them for
  sensor-level faults that don't need a real network attack (e.g. "sensor
  drift" without staging a MITM). If not landed yet, implement just the 1-2
  primitives this project needs directly against the I/O bus here, and
  consider upstreaming later rather than blocking on it.

**Done when:** an instructor can trigger each of the five scenarios against a
running twin through one console, and each is independently observable in the
historian/event log. **Met** — all five scenarios are triggerable through
`hvac_twin.console`. Phase 3 is complete.

### What these attacks actually impact

Worth designing the console around *impact category*, not just mechanism —
this is what makes the exercise more than "write a bad number to a register":

| Impact category | Mechanism | How it shows up |
|---|---|---|
| Comfort/safety | Setpoint spoofing, disabled freeze-stat/high-limit alarms | Room temp drifts out of band; alarm badge |
| Equipment damage | Short-cycling (rapid stage on/off flood), disabled safety interlocks, forced simultaneous heat+cool on a shared loop | Equipment-state flicker; damage accumulator rises |
| Energy waste | Quiet setpoint drift, "always-on" run command spoofing | Slow, easy-to-miss trend — the anomaly-detection teaching case |
| Loss of view | DoS flood on the Modbus slave | HMI goes stale/blank *while the physical process keeps running unattended* |
| Loss of control | Command injection blocking fan/pump/valve actuation | Commanded state says "cooling," physical temp doesn't respond |
| Deception | Sensor replay/FDI — feed stale or spoofed "normal" values | Ground-truth temp diverges from the sensed/displayed value |
| Lateral/cascading | Compromised EWS or shared-bus pivot writes setpoints across multiple zones at once | Several non-adjacent rooms alarm simultaneously — signals attack, not a physical fault |

### Flagship scenario: cooking the server closet

Lead the console demo with the server closet from Phase 1 — it has the
clearest stakes and reuses every mechanism above, just targeted at one
controller:

- **Setpoint spoof** the CRAC/CRAH cooling setpoint way up — direct "turn the
  heat up," zero new tooling beyond a Modbus write.
- **Command-block** the CRAC fan/compressor start — cooling *looks* commanded
  on, but nothing's moving; the commanded-vs-actual divergence case.
- **Mask the high-temp alarm** / spoof the sensor low while ground truth
  climbs — the deception case, now with damage-model stakes instead of just
  discomfort.
- **Targeted DoS** on just this controller's Modbus link — the rest of the
  building's HMI looks fine; this one room silently cooks. A good contrast to
  a building-wide DoS.

---

## Phase 4 — HMI / dashboard

**Goal:** the student-facing piece DigiTwin's roadmap defers entirely — build
it here.

**Deployment model, clarified:** the actual product is two student groups on
two laptops on the same network — one group runs the attack console
(`attack.html` + `hvac_twin.console`) against the other group's plant
machine (`hvac_twin.hmi`, which owns the twin, its Modbus slave, and the
HTTP/WS API), and the second group watches/reasons about the effect on their
own laptop (`index.html`). This isn't a separate "instructor mode" to build
later — every piece since Phase 2 already talks over real TCP sockets with
host/port as runtime parameters (never in-process shortcuts), specifically
so this topology needs no rework: point the plant's `--host`/`--twin-host`
at `0.0.0.0` instead of `127.0.0.1`, point both frontends' connection bars at
the plant's LAN IP, done. Self-use (one person, one laptop, everything on
`127.0.0.1`) is the same code, just localhost — not a different build.
The "instructor/red-team view" language below means "the attacking student
group's screen," not a privileged instructor role.

- FastAPI backend: WebSocket stream of historian + event-log data (the
  historian's on-change/periodic query API already exists; this is a thin
  serialization layer), REST endpoints for current tag values and alarm
  state. **Landed** — `hvac_twin/hmi.py`: `/tags`, `/bus/{signal}` (ground
  truth), `/historian/{tag}`, `/events`, and a `/ws` stream. Read-only;
  nothing here touches DigiTwin's core, it only reads objects DigiTwin
  already maintains.
- React frontend: real-time trend charts (Recharts), an alarm panel driven by
  `events.py`, and **two views** — student/defender (read-only monitoring +
  whatever mitigations Phase 5 exposes) and instructor/red-team (the Phase 3
  attack console). **Both screens landed** — `frontend/index.html`: an
  operator console for the server closet (trend chart, tag panel, event log,
  and the operator/instructor ground-truth-vs-sensed toggle from the
  floorplan section below, built here since it didn't need the floorplan
  itself to be useful); `frontend/attack.html`: form-driven cards for all
  five Phase 3 scenarios against `hvac_twin.console`. Both are
  runtime-configurable to whatever backend they're pointed at (see the
  deployment-model note above), not build-time constants. Deliberately not
  a generic AI-dashboard look — see `docs/TODO.md` Phase 4 for the specific
  design choices. `frontend/office.html` landed too — a third screen for
  the office wing's three zones, each a real live tile (sensed/ground-truth
  toggle, setpoint/deadband/freeze-threshold/relay), against a second
  `hvac_twin.hmi` process pointed at `office_wing_controlled.toml`. Still
  missing: true free-form floorplan/tile positioning from a project-config
  schema (polish, not a blocker — the office screen's fixed 3-up grid
  covers the "room tiles with live data" part of that idea already).
- Nothing here touches DigiTwin's core — it only reads the historian/event
  log and, for the attack console, calls Phase 3's API.

**Done when:** a student can watch live trends and alarms in a browser, and
an instructor can trigger an attack from the same session and see its effect
propagate into the dashboard in real time. **Met for the closet flagship
scenario**, verified with the full loop running at once (plant + attack
console + both frontends): firing `setpoint-spoof` from `attack.html` moved
`index.html`'s live SETPOINT readout in real time, over real network calls
throughout. The floorplan view and an office-wing screen remain as polish.

### Blueprint / floorplan view

Rather than (or in addition to) plain trend charts, render the building as a
floorplan with each room as a live tile — this is how real BAS HMIs look
(Niagara, Metasys graphics pages), so it's realistic *and* it shows spatial
effects a trend chart can't: cascading through the thermal network, and
non-adjacent rooms alarming together as a lateral-movement signal.

- **Data model addition needed in the project config**: each room needs a
  position/dimensions for layout, and its `HeatFlowLink` neighbors need to be
  derivable so the frontend can draw walls and heat-flow arrows between
  tiles — the thermal network today only needs signal names, not coordinates,
  so this is new schema, not something already implicit in Phase 1.
- **Per-tile state**: live temp, setpoint, equipment state (heating/cooling/
  fan running), alarm/fault badge.
- **Two temps per tile, not one** — ground truth (physics, always correct,
  instructor-visible) and sensed/displayed (what the student sees, what an
  attack can diverge from truth). Toggling between "operator view" (sensed
  only) and "instructor view" (both, with a mismatch highlight) is the
  concrete implementation of the deception lesson from Phase 3. **This
  toggle already exists** in the first (non-floorplan) screen —
  `frontend/src/components/GroundTruthPanel.tsx` — as a single-room
  version; the floorplan generalizes it to N tiles, it doesn't invent it.
- **Server closet tile gets a second gauge**: temp (recoverable) alongside
  damage % (monotonic, never recovers) — watching temp spike-then-recover
  while damage keeps climbing is the sharper version of the lesson than a
  single number can give.

---

## Phase 5 — Hardening / defense layer *(the student exercise)*

**Goal:** give students something to build as the "fix" side, per the
original brief.

- Auth/allowlist proxy in front of the Modbus slave server (function-code +
  source-IP allowlisting) that students add and toggle on/off. **Landed** —
  `hvac_twin/defenses/auth_proxy.py`, verified to defeat a real Phase 3
  attack (setpoint_spoof) while leaving a legitimate read untouched. **UI
  wiring landed too**: `hvac_twin.hmi` owns starting/stopping it (it already
  owns the twin's Modbus slave the proxy sits in front of), exposed as
  `GET/POST /defenses/auth-proxy(/start|/stop)`; the operator console's new
  `DefensePanel` gives the blue-team student an ENABLE/DISABLE toggle and
  shows the assigned listen port to hand the red team once it's on.
- Anomaly detection: physically-implausible rate-of-change / bounds checks
  over historian data — this reuses the historian query API directly, no
  new DigiTwin primitives required (landed as a direct `Historian.series()`
  scan; `replay.py`'s `diff_outputs`, mentioned when this phase was first
  planned, wasn't actually investigated — a plain series scan turned out
  to be enough, not something chosen over it). **Landed** —
  `hvac_twin/defenses/anomaly_detection.py`, wired into `hvac_twin.hmi` as
  `GET /anomalies/{tag}`. Catches three of five attacks (setpoint_spoof,
  alarm_mask, compromised_ews — each writes a real jump into a real tag);
  structurally cannot catch mitm_proxy or dos_flood, neither of which
  touches the twin's actual tag state. That's a permanent scope boundary
  of a historian-based detector, not a gap to close later. **UI wiring
  landed too**: `DefensePanel` polls the endpoint for the closet's setpoint
  tag and shows CLEAR vs. ANOMALY DETECTED live.
- Network segmentation exercise: separate Docker networks per zone/building
  (see Phase 6), demonstrating blocked vs. unblocked attack paths through the
  Phase 3 console. Deferred to Phase 6 — needs that phase's Docker Compose
  infrastructure to mean anything.

**Done when:** each mitigation is toggleable independently and visibly
changes whether a Phase 3 attack succeeds. **Met** for both landed defenses
— toggleable from the operator console now, not just CLI/curl, and each
proven against a real attack over real sockets. **Phase 5 is complete**
except for network segmentation, which correctly waits on Phase 6.

---

## Phase 6 — Multi-building scale-out / deployment

**Goal:** a clean, portable Docker Compose deployment — runs the same on
any Docker host, not tied to a particular machine.

- Docker Compose: `plant` and `office-plant` (each the twin + Modbus slave +
  HMI API in one process — `hvac_twin.hmi` — pointed at a different project
  file), `attack-console` (`hvac_twin.console`), `frontend` (all three HTML
  entries, static, via nginx). **Landed** — `Dockerfile`,
  `frontend/Dockerfile`, `compose.yaml`. DigiTwin is a public repo, so the
  backend image's `uv sync` resolves it straight from GitHub
  (`[tool.uv.sources]`), same as any other dependency — no sibling
  checkout or special build context needed.
- One container per PLC node: landed for both twins this repo actually
  models (the server closet, the office wing — see Phase 4 for the
  office-wing screen that made a second HMI service worth adding). A third
  twin would get its own service the same way, not a redesign.
- Confirm the whole stack comes up clean under `docker compose up` on a
  fresh host before calling this done. **Verified on this dev machine**:
  full `docker compose up --build`, all four services healthy, and a real
  `setpoint-spoof` fired from the `attack-console` container landed on the
  `plant` container over Compose's internal network (targeting it by
  service name, `plant`, since `attack-console`'s own default
  `127.0.0.1` means itself once every service is its own container —
  documented in the README). `scripts/verify_compose_stack.sh` makes this
  exact check reproducible on any host.

---

## Phase 7 (optional) — Upstream contribution

If the multi-room thermal network and any real HVAC controller profile from
Phases 1-2 prove generically useful (not HVAC-attack-specific), package them
as DigiTwin's own P3 deliverable and contribute upstream — per DigiTwin's
roadmap self-check, this must land **without a schema change** and must not
touch `plc.py`/`executive.py`/`io.py`/`historian.py`/`events.py`. Keeping this
repo focused on attack/HMI/cyber-range concerns after that split matches the
boundary DigiTwin's own docs already draw.

---

## Sequencing summary

```
Phase 0  skeleton, DigiTwin wired in                      ── days
Phase 1  multi-room thermal physics, validated, no control ── physics-only checkpoint
Phase 2  control + Modbus attack surface live             ── first attackable twin
Phase 3  attack console (5 scenarios)                     ── cyber-range checkpoint
Phase 4  HMI / dashboard                                  ── student-facing checkpoint
Phase 5  hardening layer                                  ── defense-exercise checkpoint
Phase 6  Docker Compose multi-building                    ── deployable to lab
Phase 7  optional upstream contribution
```

Each phase's "done when" is a real checkpoint — Phase 1 must run and settle
with *zero* control or network code, Phase 2 must be attackable with a plain
Modbus script before any custom attack tooling exists, and Phase 3's five
scenarios must work before the HMI wraps a UI around them.
