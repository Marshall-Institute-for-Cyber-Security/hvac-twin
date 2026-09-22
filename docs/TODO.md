# HVAC Twin — Build Checklist

Working checklist. Rationale and phase plan live in `docs/ROADMAP.md`; this
file tracks what's done and what's next, in that document's phase order.

---

## Phase 0 — Wiring & skeleton

- [x] `pyproject.toml` — `hvac-twin` package, depends on `digitwin`
      (`[tool.uv.sources]` points at the sibling `../Documents/DigiTwin`
      checkout, editable, for local dev)
- [x] `.python-version` (3.12), `.gitignore` mirrored from DigiTwin
- [x] `src/hvac_twin/{plant,programs,models}/` skeleton packages
- [x] `tests/test_dependency_smoke.py` — loads and runs a DigiTwin example
      twin through this repo's venv with zero HVAC code
- [x] `uv sync` and confirm the smoke test passes in this environment
- [x] Ruff/mypy config mirrored from DigiTwin; `uv run ruff check .` and
      `uv run mypy` run clean (added a `digitwin.*` mypy override — DigiTwin
      doesn't ship a `py.typed` marker despite running mypy --strict
      internally; worth flagging upstream)
- [x] Create the GitHub repo and push —
      [github.com/Glass-Pawns/hvac-twin](https://github.com/Glass-Pawns/hvac-twin)
      (private)
- [ ] DigiTwin is staying **private** until its own remaining work lands, so
      the `[tool.uv.sources]` local-path dependency stays as-is for now — a
      git source would need `git+ssh://` against a private repo anyway, which
      only helps once there's a second machine or a CI runner in the picture.
      Revisit when either DigiTwin goes public, or a second machine needs to
      build this repo (whichever comes first).

**Done when:** `uv run pytest` passes on whatever machine(s) actually need to
build this repo — currently just this one, so the local-path dependency is
sufficient; no forcing function to change it yet.

---

## Phase 1 — Multi-room RC thermal physics

### Core components (new, this repo)

- [x] `hvac_twin/plant/thermal_links.py::HeatFlowLink` — heat exchange
      between any two temperature signals through a resistance, watts =
      conductance × ΔT, sign-aware (no valve — heat flows whichever way is
      hotter). Dataclass, `step(dt, io)`, stateless.
- [x] Unit tests: exact single-step calc, sign-reversal + `max_flow` clamp,
      and a two-node relaxation to the capacity-weighted equilibrium temp.
- [x] `hvac_twin/plant/thermal_node.py::ThermalNode` — a lumped mass driven
      by one net Watts input (`flux_signal`); no baked-in ambient/loss —
      a room's connection to outdoors is just another `HeatFlowLink`.
- [x] Unit tests: constant-flux linear ramp, no-flux-signal is a no-op.
- [x] `hvac_twin/plant/combinators.py::WeightedSum` — generic `bias +
      Σ(weight × signal)`, for combining multiple `HeatFlowLink`s (and any
      fixed equipment load) into one node's `flux_signal`.
- [x] Unit tests: weights + bias exact calc, missing signal defaults to 0.
- [x] Integration test (`test_thermal_network_integration.py`): two
      `ThermalNode`s + one `HeatFlowLink` + two `WeightedSum`s, wired the way
      a real project file will, settle at the same equilibrium the
      `HeatFlowLink`-only test checks by hand — proof the composition works,
      not just each piece alone.
- [x] `hvac_twin/plant/excess.py::Excess` — `out = max(0, in - threshold)`,
      stateless. One-line component, but it's what makes the damage
      accumulator possible without a bespoke "damage" primitive.
- [x] Unit tests: at/above/below threshold, plus an integration test pairing
      it with `digitwin.plant.Integrator` proving the accumulator rises
      while over-temp and — critically — does not fall back down once the
      temperature recovers.
- [x] `hvac_twin/registry.py` — registers all four components into
      DigiTwin's `_PLANT_COMPONENTS` (there's no public registration API
      yet, so this reaches into it directly; worth proposing an upstream
      hook once a second consumer needs the same thing). Wired to run
      automatically on `import hvac_twin` via `__init__.py`.
- [x] `test_registry.py` proves it end to end: a real `.toml` project file
      referencing `HeatFlowLink`/`WeightedSum`/`ThermalNode` by name loads
      through `digitwin.config.load_project` and settles correctly — not
      just that the lookup dict contains the right keys.

### Boundary driver

- [x] `hvac_twin/plant/constant_signal.py::ConstantSignal` — writes a fixed
      value to the bus every tick; the outdoor boundary each room's exterior
      `HeatFlowLink` connects to. (Defer any live weather-API or
      diurnal-schedule integration.) Registered alongside the other four
      components in `registry.py`.
- [x] ~~Occupancy heat-gain driver~~ / ~~solar gain driver~~ — **cut, not
      deferred.** Neither has a validation anchor the way wall conduction
      does, and neither is something any Phase 3 attack targets or Phase 5
      defense monitors — see `docs/ROADMAP.md` Phase 1 scope note. What
      drives a room's temperature is outdoor conduction (real, checkable)
      and, where the scenario needs it, a fixed equipment load — not an
      invented occupancy/solar schedule.

### Ground truth vs. sensed signal convention

- [x] Two-signal-per-room convention (ground truth + sensed) — landed in
      practice via Phase 2's `AnalogSensor` on the server closet and office
      wing: the PLC/Modbus side only ever sees the tenths-of-a-degree
      sensed reading, never the plant's true float temperature. Phase 3's
      `mitm_proxy.py` and `alarm_mask.py` are the payoff — both rely on
      ground truth and sensed being genuinely separate signals to make the
      "don't trust the display" divergence real.

### Validation twins

- [x] Hand-calc validation: one isolated room against the ASHRAE-simplified
      first-order lumped-capacitance decay (`test_office_wing_validation.py`)
      — checked against the closed-form exponential at one time constant in
      (curve shape, `rel_tol=1e-2`) and fully settled (`abs_tol=1e-3`).
- [x] `examples/office_wing.toml` — three rooms in a row (`room_1` —
      `room_2` — `room_3`), the two end rooms with an exterior wall to
      outdoor, `noop` program. Loaded through the real `load_project`
      pipeline in `test_office_wing.py`, confirming all three settle exactly
      at the outdoor boundary — the only physically sane outcome with no
      heat source anywhere, regardless of the interior wiring.
- [x] All values in Fahrenheit (converted from the original Celsius design
      numbers: absolute temps via `×9/5+32`, conductance/heat_capacity — "per
      degree" rates, not temperatures — divided by 1.8 instead; verified
      numerically that tau and convergence are unchanged either way).
- [x] `examples/server_closet.toml` — no new component code needed:
      `WeightedSum`'s `bias` covers the constant IT load (a power, not a
      per-degree rate, so not divided by 1.8 like the other conversions),
      and DigiTwin's own `Integrator` was already registered — only
      `HeatFlowLink` / `ThermalNode` / `Excess` are ours. No controller;
      the closet overheats entirely on its own.
- [x] Hand-calc validation (`test_server_closet_validation.py`): time to
      cross the 95°F safety threshold, checked against the closed-form
      decay to the IT-load-shifted equilibrium (121°F) — matches to within
      `rel_tol=1e-2`.
- [x] `test_server_closet.py` loads the real file and confirms the flagship
      point directly: with no active cooling, the room passes 95°F and the
      damage accumulator **saturates at its 100-point cap** well before the
      room even finishes climbing toward its 121°F equilibrium.

**Done when:** the office wing and the server closet both run from project
files with **no controller code**, settle (or, for the closet with no
cooling, predictably overheat) correctly, and every new component
(`HeatFlowLink`, `Excess`) has a passing analytic-trajectory test.

**Phase 1 is complete.**

---

## Phase 2 — HVAC control layer

- [x] Controller identity: `PLC_Generic`, for now — real vendor profile
      deferred (would also double as DigiTwin's own P3 requirement, but not
      blocking this repo's progress).
- [x] `hvac_twin/programs/crac_bang_bang.py::CracBangBangProgram` — a
      seal-in latch (same style as DigiTwin's `StartStopTankProgram`): CRAC
      relay on past setpoint+deadband, off past setpoint-deadband, holds
      inside the deadband. High-temp alarm is an independent decision from
      whether cooling is running. All temps are tenths-of-a-degree integers
      — the PLC never sees the plant's true float temperature, only the
      `AnalogSensor`-scaled reading. That gap is deliberately the concrete
      form of "ground truth vs. sensed" this project has been building
      toward since Phase 1.
- [x] Registered as `"crac_bang_bang"` in `digitwin.programs._REGISTRY` via
      `registry.py` (same documented reach-in pattern as the plant
      components; the module docstring now covers both).
- [x] No new plant component needed for the CRAC unit itself: DigiTwin's own
      `Motor` (bool command → ramped 0..1 speed with realistic spin-up/coast
      lag) + `WeightedSum` (speed × max-wattage as a weighted term) covers
      it completely.
- [x] `examples/server_closet_controlled.toml` — the same closet as
      `server_closet.toml`, now with the CRAC + control program wired in.
      Verified numerically before writing: holds a stable cycle between
      ~73–77°F around the 75°F setpoint, never approaching the 95°F alarm
      threshold.
- [x] `test_crac_bang_bang.py` — the control program in isolation (latch,
      hysteresis/no-chatter, alarm independence). The last test there is
      this project's first working attack: writing `setpoint_tenths` with
      no authentication changes control behavior immediately — exactly
      what Phase 3 will build tooling around, using a mechanism that
      already exists today with zero extra code.
- [x] `test_server_closet_controlled.py` — loads the real file and confirms
      the damage accumulator stays at exactly zero for the whole run,
      directly contrasting Phase 1's uncontrolled twin.
- [x] `[modbus.slave_server]` added to `server_closet_controlled.toml` —
      publishes `closet_temp_raw` (input register), `high_temp_alarm` /
      `cooling_relay` (coils), and a read-only setpoint mirror (holding
      register 1); accepts writes to the setpoint on a **separate** holding
      register (address 0). Two addresses, not one, because publishing and
      accepting the same tag at the same address is self-defeating —
      publish always overwrites the wire with the tag's current value
      before accept reads it back, so a remote write never survives; see
      the TOML's own comment and `ModbusSlaveServer`'s docstring.
- [x] Had to actually `uv sync --extra modbus` — the extra was declared in
      `pyproject.toml` since Phase 0 but never installed.
- [x] `test_server_closet_modbus.py` — two tests over a **real** socket
      (mirrors DigiTwin's own real-pymodbus test pattern): a plain client
      commissions the setpoint and reads back temp/alarm/setpoint, and a
      second test previews Phase 3 directly — the same unauthenticated
      write changes control behavior immediately, using a mechanism that
      already exists with zero new code.
- [x] Multi-zone setpoint control for `office_wing.toml`'s three rooms (the
      original roadmap target) — landed as a separate
      `examples/office_wing_controlled.toml`, mirroring the closet's
      `_controlled` split so `office_wing.toml` stays untouched as the
      Phase 1 physics-only checkpoint. Each room gets its own heater
      (`Motor` + `WeightedSum`, same mechanism as the CRAC) and its own
      `AnalogSensor`-scaled sensed temp. `hvac_twin/programs/
      office_wing_bang_bang.py::OfficeWingBangBangProgram` runs the same
      seal-in latch as the closet's `CracBangBangProgram`, but **inverted**
      — this is a heating loop (outdoor is the cold side at 41°F), not
      cooling, and one PLC scan drives all three zones independently, the
      way a real multi-zone RTU controller works. A `freeze_alarm` per
      zone is the heating-side equivalent of the closet's
      `high_temp_alarm`. Parameters (3000 W heater/room, 72°F setpoint,
      ±2°F deadband) were verified numerically before writing, same as the
      closet's tuning: each room settles into a stable cycle
      (~70–74°F end rooms, ~71–72°F middle room) well clear of the 50°F
      freeze threshold. `test_office_wing_bang_bang.py` covers the latch/
      hysteresis/alarm-independence/zone-independence/attack-surface
      behavior in isolation (mirrors `test_crac_bang_bang.py`);
      `test_office_wing_controlled.py` loads the real project file and
      confirms all three rooms hold their band with no freeze alarm. Not
      exposed over Modbus — that was already proven reachable via the
      closet, so this stayed scoped to the control loop itself.

**Done when:** the controlled closet twin is reachable by a plain Modbus
client — reading sensed temp/alarm and writing the setpoint — with no
custom tooling beyond `pymodbus`. **Met.**

**Phase 2 is complete**, including the multi-zone office-wing control loop
that had been deferred.

## Phase 3 — Attack injection framework

- [x] `hvac_twin/live_runner.py::run_live` — runs a project file as a real
      process: real-time paced (`ExecutiveMode.REAL_TIME`), Modbus slave
      (if configured) started on a real socket. This was the missing
      piece before any attack script could target "a running twin
      instance" outside of pytest — DigiTwin's own `digitwin run` CLI
      scans and exits, never opening the Modbus port or pacing in real
      time. `--host`/`--port` override the project file's own
      `[modbus.slave_server]` settings. Exposed as the `hvac-twin-live`
      console script.
- [x] `hvac_twin/attacks/setpoint_spoof.py` — attack scenario #1
      (flagship): connects over plain, unauthenticated Modbus TCP and
      writes an inflated cooling setpoint to the server closet's accept
      register. Zero new DigiTwin plumbing — this is the same write
      `test_server_closet_modbus.py`'s preview test already proved works,
      now packaged as a real standalone script (`python -m
      hvac_twin.attacks.setpoint_spoof`) runnable against a live twin
      instead of driven from a test. Verified for real, not just under
      pytest: ran `live_runner` and the attack script as two separate
      processes and confirmed the write lands with no authentication.
- [x] `test_live_runner.py` / `test_setpoint_spoof.py` — end-to-end over
      real sockets on free ports, same pattern as
      `test_server_closet_modbus.py`.
- [x] Bug found and fixed while building scenario #2: any accept-mapped
      tag (`setpoint_tenths`, and now `alarm_threshold_tenths`) gets
      overwritten by `ModbusSlaveServer.sync()` on tick 1 regardless of
      whether a client ever connects — it reads back 0 (the register
      store's default) instead of the tag's TOML `initial =`, silently.
      `server_closet_controlled.toml` never actually held ~75°F when run
      via bare `load_project(...).run(...)` — it ran the CRAC full-blast
      from tick 1 and crashed toward the 41°F outdoor temperature.
      `test_server_closet_controlled.py`'s old `< 90.0` bound didn't catch
      it (both outcomes satisfy it). Fixed by commissioning both accept
      tags over a real loopback Modbus write before running, mirroring
      the pattern `test_server_closet_modbus.py` already used for the
      setpoint; tightened the assertion to `70–80°F` so a regression like
      this can't hide behind a loose bound again. Documented as a
      commissioning-gotcha comment in the project file itself.
- [x] `hvac_twin/attacks/alarm_mask.py` — attack scenario #2 (the
      deception case): masks the high-temp alarm by spoofing the
      *threshold* `CracBangBangProgram` compares against, not the alarm
      bit itself. A direct "force the `high_temp_alarm` coil" version was
      built first and rejected — accept-mapping the alarm bit directly
      hits the same sync()-defaults-to-zero bug above, except *for the
      alarm*, meaning it would read permanently masked from tick 1
      regardless of any attacker, not just once attacked. Spoofing
      `alarm_threshold_tenths` instead keeps `high_temp_alarm` honestly
      computed at all times — the deception is in what the ladder is
      tricked into believing is normal, not in a faked output — and its
      own uncommissioned-default direction is fail-*loud* (threshold 0
      trips the alarm immediately) rather than fail-silent. See the
      `[modbus.slave_server]` comment in
      `examples/server_closet_controlled.toml` for the full reasoning.
      `test_alarm_mask.py` chains scenario #1 + #2 into the flagship
      "cook the closet, then hide it" narrative and confirms ground truth
      keeps getting worse while the wire shows nothing. Verified for real
      as three separate processes (`live_runner` + both attack scripts).
- [x] Closed the auto-commissioning gap structurally, not just per-test:
      `live_runner.run_live()` now seeds every accept-mapped tag's
      register from that tag's own TOML `initial =` before the first tick
      (`_commission_accept_tags`, reaching into `ModbusSlaveServer`'s
      private `_store` — same documented-wart category as
      `registry.py`'s reach into DigiTwin's plant/program registries).
      `hvac-twin-live` now commissions by default; `--cold-start` opts
      back into the raw, uncommissioned behavior for anyone who wants it
      on purpose (e.g. teaching the gotcha itself). Verified for real:
      ran the live twin with zero manual commissioning and confirmed
      `setpoint_tenths` reads back 750 and the alarm reads False, not the
      old silent-zero failure. `test_live_runner.py` covers both the
      default-commissioned path and the `--cold-start` path explicitly,
      so the old bug stays reproducible on purpose instead of just fixed
      in the two spots that happened to need it.
- [x] `hvac_twin/attacks/mitm_proxy.py` — attack scenario #3: a real
      Modbus TCP proxy that forwards every request/response between a
      client and the twin unmodified, except it rewrites the bytes of
      specific *read* responses in flight. Needed because scenarios #1/#2
      only work by writing into address space the ladder or an operator
      is expected to write — a real sensor reading (input register) or
      status coil can't be overwritten that way at all, since Modbus has
      no write function code for read-only address space, and
      `ModbusSlaveServer` treats a published register as read-only in
      practice regardless. Two clients in the test — an "HMI" that only
      ever talks through the proxy, and a "ground truth" client on the
      twin's real port, bypassing the proxy — confirm the attack changes
      what's displayed, not what's physically happening, and that
      legitimate writes (the HMI's own commissioning) pass through the
      proxy untouched. `test_mitm_proxy.py` runs it over real sockets
      against a live `server_closet_controlled.toml`, chaining
      `setpoint_spoof` through the proxy to cook the closet for real
      while the proxied reads still show 75°F / no alarm — the sharpest
      version yet of "don't trust the display."
- [x] `hvac_twin/attacks/dos_flood.py` — attack scenario #4: opens many
      concurrent raw-socket connections against the slave server's TCP
      port and hammers read-input-register requests in a tight loop per
      connection — no pymodbus needed, deliberately built to look like
      naive protocol-level flooding rather than a well-behaved client.
      DigiTwin's `ModbusSlaveServer` runs a single asyncio event loop on
      its own background thread, independent of the twin's scan-loop
      thread, so the effect is "loss of view" (a legitimate client
      sharing that event loop gets starved of scheduling time), not
      "loss of control." `test_dos_flood.py` proves a legitimate client's
      read latency degrades measurably during the flood while
      `sim.scan_count` keeps climbing throughout, over real sockets.
      Verified manually against a live twin too: with 40 flood
      connections, a legitimate client couldn't even open a *new*
      connection within its 2s timeout, while the twin's log showed all
      10 scheduled scans completing on schedule regardless — the
      physical process runs unattended while the HMI goes dark, the
      sharpest version of this impact category yet.
- [x] `hvac_twin/console.py` — the FastAPI attack console: a uniform
      start/stop/status HTTP surface over the four landed scenarios,
      instead of an instructor juggling standalone scripts across
      terminals. Orchestration only — every scenario's actual mechanism
      is unchanged; the console just holds the small amount of state (a
      running MITM proxy, an in-progress flood) a one-shot script doesn't
      need to track. No auth of its own, matching this repo's
      "unauthenticated by design" theme (it's instructor tooling, not
      attacker-facing) — a hardening pass is a candidate for Phase 5.
      Refactored `setpoint_spoof.py`/`alarm_mask.py` to split their logic
      out of their CLI wrappers (`spoof_setpoint()`/`mask_alarm()`) and
      raise normal exceptions instead of `SystemExit`, which a
      long-running server must never let leak out of a request handler;
      `dos_flood.run_flood()` gained an optional `stop_event` so the
      console can end a flood early. New shared
      `hvac_twin/attacks/_client.py::wait_for_connection` replaces a
      helper that used to be duplicated in two scripts.
      `tests/test_console.py` drives all of this over real sockets via
      FastAPI's `TestClient`; also verified manually end-to-end with
      `uvicorn` against a live twin. New `console` optional-dependency
      group (`fastapi`, `uvicorn`); `httpx` added to dev deps for
      `TestClient` (throws a harmless `StarletteDeprecationWarning`
      about a future `httpx2` — nothing installable under that name yet,
      not chased further).
- [x] `hvac_twin/attacks/compromised_ews.py` — attack scenario #5: exposes
      `examples/office_wing_controlled.toml` over Modbus TCP for the
      first time (each zone's setpoint gets the same two-address
      accept/publish split as the closet's), then runs a single scripted
      session that reads each zone's current setpoint first
      (legitimate-looking commissioning traffic) and writes all three in
      quick succession. Nothing about the traffic looks anomalous zone
      by zone — what makes it an attack is one actor touching every zone
      in the same breath. Delivers the "lateral/cascading" impact
      category none of the other four scenarios do: room_1 and room_3
      are the wing's two end rooms and share no wall (room_2 sits
      between them), so multiple non-adjacent rooms freeze-alarming at
      once is a signal an attack caused it, not a single failed heater.
      `test_compromised_ews.py` proves this over a real socket (verified
      numerically first: turning off all three heaters takes ~80,000
      simulated seconds to cross the 50°F freeze threshold — a much
      slower burn than the closet's overheat, since it's heading toward
      a 41°F outdoor equilibrium instead of a self-heating one). Also
      updated `test_office_wing_controlled.py` to commission each zone's
      setpoint over a real Modbus write before running, now that the
      project file has a slave server — same requirement, same
      skip-it-and-nothing-heats gotcha as the closet. Wired into
      `hvac_twin.console` as a fifth scenario.

**Done when:** an instructor can trigger each of the five scenarios
against a running twin through one console, and each is independently
observable in the historian/event log. **Met** — all five scenarios are
landed and triggerable through `hvac_twin.console`. Phase 3 is complete.

## Phase 4 — HMI / dashboard

- [x] `hvac_twin/hmi.py` — the FastAPI backend: read-only HTTP + WebSocket
      access to a running twin's live PLC tags, ground-truth bus signals,
      historian trends, and event log — the "thin serialization layer"
      the roadmap called for. `/tags` and `/bus/{signal}` give the
      sensed-vs-ground-truth split this project has built since Phase 1
      (e.g. `/tags`'s `closet_temp_raw` vs. `/bus/closet_temp`);
      `/historian/{tag}` and `/events` serve DigiTwin's own historian/
      event log, 404ing cleanly on a project with no `[observability]`
      configured. Writes stay Phase 3's job — this app never advances or
      mutates the twin it reads.
      Refactored `live_runner.py` to split setup (`start_twin`: load,
      real-time pacing, Modbus slave start/commission) from the tick loop
      itself (`run_live`) — the HMI needs a handle on the `Executive`
      while it's still running (ticked on a background thread), not just
      after it stops, so `run_hmi()` reuses `start_twin()` instead of
      duplicating its setup. Enabled `[observability]` (historian +
      events) on `server_closet_controlled.toml`, the first project file
      to declare it — `office_wing_controlled.toml` still doesn't, which
      `test_hmi.py` uses directly to prove the clean-404 case.
      `test_hmi.py` drives all of this against a real `Executive`
      advanced via `sim.run()` — no background thread needed in tests
      since the app only ever reads `sim`. Also verified manually
      end-to-end against a live twin: ground truth (71.62°F) and the
      sensed reading (716 → 71.6°F) track each other with no attack
      active, and the WebSocket stream reflects live, advancing state.
- [x] React frontend — first screen landed: `frontend/` (Vite + React +
      TypeScript) is an operator console for the server closet, reading
      `hvac_twin.hmi`'s REST/WebSocket API. `GroundTruthPanel` implements
      the roadmap's operator/instructor toggle: operator view shows only
      the sensed reading (what a real HMI would show), instructor view
      shows both ground truth and sensed with a `MISMATCH` flag when they
      diverge — the concrete form of the deception lesson Phase 3's
      attacks build toward. `TrendChart` plots the historian's sensed
      series with a setpoint reference line; `TagPanel`/`EventLog` cover
      the rest of the controller's tag state.
      Deliberately designed against the generic-AI-dashboard look:
      Source Serif 4 + IBM Plex Mono + IBM Plex Sans instead of
      Inter/Roboto/Open Sans; a warm graphite/parchment palette with
      three accents (rust/steel-blue/olive) instead of violet/indigo/
      teal; flat panels (one hairline border, zero box-shadow) instead
      of card-border-plus-shadow; an asymmetric 2fr/1fr grid instead of
      a centered stack or a 3-column icon-card grid.
      Added CORS to `hvac_twin/hmi.py` (`allow_origins=["*"]`, matching
      this project's unauthenticated-by-design instructor tooling) so
      the Vite dev server's origin can reach it at all.
      Verified for real: ran `hvac_twin.hmi` against a live closet twin
      side by side with the Vite dev server and took a headless-browser
      screenshot confirming live scan/elapsed counters, a real sensed
      reading, an actual historian-backed trend line, and correct
      controller tag values — not just that the code compiles. Node.js
      wasn't installed on this machine; installed via
      `winget install OpenJS.NodeJS.LTS` as part of this work.
      The alarm-state visual wasn't verified live (would take real
      wall-clock hours to trigger naturally under real-time pacing — the
      code path mirrors the already-verified nominal-state styling, but
      flag this as reasoned-through rather than screenshotted).
- [x] Red-team attack console UI — `frontend/attack.html`, a second,
      independent Vite entry (not a route in the operator console; the
      two run on two different students' laptops, pointed at two
      different backends). Form-driven cards for all five
      `hvac_twin.console` scenarios (setpoint spoof, alarm mask, MITM
      proxy, request flood, compromised EWS), each its own small
      component rather than one generic form-renderer. Status pills
      (IDLE/RUNNING/DONE/ERROR) poll `GET /attacks` every 3s and also
      update immediately from each LAUNCH/STOP response. This **is**
      Phase 4's "instructor/red-team view" — same console, just used by
      an attacking student group instead of an instructor; see
      `docs/ROADMAP.md`'s usability note on the real deployment model.
      Also added CORS to `hvac_twin/console.py` (missed when the console
      was first built in Phase 3, since nothing browser-based talked to
      it until now).
      Verified for real: ran the console backend + a live twin + the
      Vite dev server together, fired `setpoint-spoof` via curl (standing
      in for a click), and screenshotted the card picking up the real
      `DONE` state and detail message through its own poll loop.
- [x] Frontend backend target made runtime-configurable (`ConnectionBar`
      / `ConsoleTargetBar`, both localStorage-backed) instead of a
      build-time env var — required for the real deployment model
      (a pair of students per session, each pair potentially pointed at
      a different plant-laptop IP); a compile-time constant would mean
      rebuilding the app per pairing.
- [x] Office-wing screen — `frontend/office.html`, a third independent Vite
      entry (`src/office/`), its own backend target (own localStorage key,
      default port 8101 — a second `hvac_twin.hmi` process, same module,
      pointed at `office_wing_controlled.toml` instead of the closet's
      project file; two twins, two processes, same pattern as the
      operator/attack-console split). Three zone panels side by side
      (`GroundTruthPanel` + `TagPanel` per room), each real, not mocked:
      sensed temp, ground truth (polled from `/bus/room_N_temp`), setpoint,
      deadband, freeze threshold, heating relay. The status band names
      every alarming zone rather than just saying "ALARM" — the
      compromised-EWS attack's actual tell is room_1 and room_3 (which
      share no wall) freeze-alarming at once, and the whole pedagogical
      point is that this pattern, not a single failed heater, is what
      says "attack." No trend chart or event log here — deliberate, not
      an oversight: `office_wing_controlled.toml` still has no
      `[observability]` configured (kept that way on purpose, since
      `test_hmi.py` uses exactly that gap to prove the HMI's 404 case),
      so there's no historian data to chart yet.
      Required two small refactors to reuse rather than duplicate:
      `config.ts`'s `getApiBase/setApiBase/getWsBase` and `api.ts`'s REST
      getters + `useLiveStream` became `createApiTarget`/`createApiClient`
      factories (the closet's own top-level exports are just one instance
      of each, unchanged for existing callers); `GroundTruthPanel` and
      `ConnectionBar` gained explicit `title`/`mismatchThresholdF` and
      `target`/`placeholder` props instead of reading the closet's
      constants directly.
      Verified for real: ran a live `hvac_twin.hmi` against
      `office_wing_controlled.toml` on port 8101, opened `office.html`
      against it, and screenshotted all three zones showing live scan
      count/elapsed and real sensed readings (71.5–71.6°F) matching the
      twin's actual state. The freeze-alarm visual state itself wasn't
      screenshotted — reaching it takes real wall-clock hours under
      real-time pacing even before an attack (same reasoning already
      accepted for the closet's alarm banner) — but it's the same
      already-proven `StatusBand` alarm styling, driven by real
      `/tags` booleans `test_hmi.py` already covers.
- [ ] Blueprint/floorplan view (room tiles positioned/sized from project
      config, a floorplan-native ground-truth-vs-sensed toggle, the
      closet's damage gauge) — still not started, and still needs a new
      position/dimension schema this repo doesn't have. The office-wing
      screen's 3-up zone grid covers the *room-tiles-with-live-data* part
      of this in spirit, without inventing that schema; true free-form
      floorplan layout remains deferred, not required for the core loop.
- Note: nothing currently feeds ground-truth bus signals (`closet_temp`,
  `closet_damage`, per-room temps, …) into the historian — DigiTwin's own
  `Historian.record()` only samples `plc.tags` (the sensed side), so
  `/bus/{signal}` gives a live current value but no trend history for
  ground truth yet. Revisit if the floorplan/trend view needs a
  ground-truth trend, not just a live snapshot.

**Done when:** a student can watch live trends and alarms in a browser, and
an instructor can trigger an attack from the same session and see its effect
propagate into the dashboard in real time. **Met for both twins** —
verified with the full loop running at once for the closet flagship
scenario: `hvac_twin.hmi` as the plant (twin + Modbus + HTTP/WS),
`hvac_twin.console` as the attack backend, and both frontends open against
them simultaneously. Firing `setpoint-spoof` from the attack console moved
`index.html`'s SETPOINT readout from 75.0°F to 900.0°F live, with no manual
refresh — an attack fired from one screen, observed from the other, over
real network calls throughout. The office wing now has its own live screen
too (see above). Free-form floorplan view remains as polish, not a blocker
to the core loop.

## Phase 5 — Hardening / defense layer

- [x] `hvac_twin/defenses/auth_proxy.py` — an auth/allowlist Modbus TCP
      proxy a student puts in front of the twin's real port. Structurally
      the mirror of `attacks/mitm_proxy.py` (same MBAP-parsing, same
      per-connection two-thread relay), opposite job. `enabled=False` is
      a transparent passthrough (today's undefended baseline);
      `enabled=True` applies two independently toggleable allowlists —
      source IP (a disallowed connection is refused immediately, before
      any Modbus is exchanged) and function code (a disallowed request
      gets a real Modbus exception response, ILLEGAL FUNCTION, instead
      of being forwarded — the connection itself stays open).
      `test_auth_proxy.py` proves the function-code allowlist alone
      defeats `setpoint_spoof.py`'s attack, which `test_setpoint_spoof.py`
      already proves lands unconditionally against an undefended twin.
      Verified manually too: the real attack script got a real exception
      response (`function_code=144`, `exception_code=1`) through the
      proxy while the twin's actual setpoint never moved, and a
      legitimate read still passed through untouched.
- [x] `hvac_twin/defenses/anomaly_detection.py` — `find_rate_anomalies()`
      scans a tag's historian series for any consecutive pair of samples
      exceeding a caller-supplied max rate of change. Pure function over
      `Historian.series()`, no new DigiTwin primitives, per the roadmap.
      Scope stated plainly in its own docstring: since the historian only
      ever records the twin's real internal `plc.tags`, this catches
      `setpoint_spoof`/`alarm_mask`/`compromised_ews` (each writes a real
      instantaneous jump into a real tag) but can **never** catch
      `mitm_proxy` (touches only what a remote client sees, not the
      twin's actual state) or `dos_flood` (touches no tag at all).
      Different attacks need different defenses; this covers three of
      five, honestly. Wired into `hvac_twin.hmi` as `GET /anomalies/{tag}`.
      Verified manually against a live twin: empty before an attack, a
      real anomaly record (`750.0 → 9000.0`, rate `183.3`/s against a
      limit of `50`/s) appearing immediately after one.
      Found and fixed a real commissioning-timing gap while writing the
      test for this: `Executive._observe()` calls `historian.record()`
      *before* `modbus_slave.sync()` each tick, so a live Modbus write
      used to commission a tag (the pattern every other attack test
      uses) leaves one real tick where the historian records the tag's
      zeroed pre-write default — a spurious rate "anomaly" that's an
      artifact of commissioning order, not a real one. Fixed by
      commissioning via `live_runner._commission_accept_tags` (seeds the
      register store directly, no live write needed) instead — the same
      mechanism `hvac_twin.hmi`/`live_runner` already use by default.
- [x] Auth proxy wired into `hvac_twin.hmi` and the operator console — since
      `hmi.py` already owns the running twin and its Modbus slave, it now
      also owns starting/stopping an `AuthProxy` in front of that slave's
      real port via `GET /defenses/auth-proxy`, `POST .../start`,
      `POST .../stop` (same start/stop/status shape as `hvac_twin.console`'s
      attack endpoints). The operator console gained a `DefensePanel`: an
      ENABLE/DISABLE toggle showing the assigned listen port once running
      (what the blue-team student hands the red team as the "defended"
      address), plus a live poll of the existing `/anomalies/{tag}`
      endpoint showing CLEAR vs. ANOMALY DETECTED for the setpoint tag.
      `test_hmi.py` proves the wiring itself over a real socket (start,
      double-start 409s, a client through the proxy has reads pass and
      writes blocked, stop, double-stop 409s). Verified manually too:
      started the proxy over HTTP against a live twin, fired
      `setpoint_spoof` at the proxy's port (blocked — real exception
      response, setpoint unchanged), confirmed the anomaly monitor stayed
      clear, then stopped it cleanly.
- [ ] Network segmentation exercise (separate Docker networks per zone,
      demonstrating blocked vs. unblocked attack paths) — deferred to
      Phase 6, since it needs the Docker Compose infrastructure that
      phase builds; not meaningful to simulate without it.

**Done when:** each mitigation is toggleable independently and visibly
changes whether a Phase 3 attack succeeds. **Met** for both landed
defenses — toggleable from the operator console, not just the CLI, and
each verified against a real attack over real sockets. The
network-segmentation exercise remains, correctly deferred to Phase 6.

## Phase 6 — Multi-building scale-out / deployment

- [x] `Dockerfile` (repo root) — builds `hvac_twin` for any of three
      services (`plant` / `office-plant`: `hvac_twin.hmi`, i.e. the twin +
      Modbus slave + HMI API in one process, same as bare-metal, pointed
      at a different project file each; `attack-console`:
      `hvac_twin.console`), differing only in `compose.yaml`'s `command:`.
      DigiTwin has no published package yet, so this repo's own
      `pyproject.toml` already resolves it from a sibling checkout
      (`[tool.uv.sources]`, `../Documents/DigiTwin`) — rather than changing
      that for Docker specifically, the Dockerfile recreates the same
      sibling layout inside the image (DigiTwin copied in from a named
      build context to `/root/Documents/DigiTwin`, this repo to
      `/root/HVAC`), so `uv sync` resolves the relative path unmodified.
- [x] `frontend/Dockerfile` — multi-stage (`node:22-slim` build, `nginx:
      1.27-alpine` serve); all three HTML entries (`index.html`,
      `attack.html`, `office.html`) land in one `dist/` and are served as
      plain static files at their own paths, no server-side routing needed.
- [x] `compose.yaml` — four services (`plant`, `office-plant`,
      `attack-console`, `frontend`), using Compose's `additional_contexts`
      to hand DigiTwin's sibling checkout into each backend build.
      Confirmed clean end-to-end on this machine (Docker Desktop installed
      via winget for this): `docker compose up --build` brought up all
      four containers; `plant`'s and `office-plant`'s `/status` and the
      console's `/attacks` all responded correctly; all three HTML entries
      served 200; firing `setpoint-spoof` from the `attack-console`
      container at `plant:5020` (Compose's internal DNS name for the
      twin's service — documented since `127.0.0.1` from inside that
      container means the console itself, not a twin) landed for real
      (`setpoint_tenths`: 750 → 9000) exactly like every other bare-metal
      attack test in this repo; `docker compose down` tore everything down
      cleanly.
- [x] `scripts/verify_compose_stack.sh` — the manual check above, made
      reproducible: brings the stack up, polls all three backends until
      they respond, checks all three frontend pages serve 200, fires a
      real cross-container `setpoint-spoof`, asserts it landed, then tears
      down — exiting non-zero on any failure. Run this on any host with
      Docker to get the same pass/fail signal this repo's own dev machine
      got, without needing a person to eyeball curl output by hand.
- [ ] Per-building containers beyond the two zones this repo already
      models (closet, office wing) — not needed unless a third twin gets
      built; the pattern (`Dockerfile` + a `command:` override + a
      frontend entry) is already established twice over, not a redesign.

**Done when:** the whole stack comes up clean under `docker compose up`.
**Met** on this machine, including a real cross-container attack, for all
four services. Lab-host verification remains — the tooling to check it
exists now, but running it there hasn't happened yet.

## Phase 7 (optional) — Upstream contribution

Not started.
