# Student Guide

A hands-on range for learning industrial control system (ICS/OT) security,
built as a working building-management system rather than a security demo.
**ICS BMS Sim** is the app you'll actually use: two live HVAC zones, real
sensor readings, a trend chart, an operator setpoint control — the kind of
thing a facilities engineer would run day to day. It also happens to run
over a real, unauthenticated Modbus TCP interface, which is exactly the
kind of exposure real building equipment has shipped with. The Red Team
Console and Defenses page are where that becomes the point.

Everything here runs over real network sockets — there's no simulated
"pretend" attack traffic. When you spoof a setpoint, you're writing an
actual Modbus TCP frame to an actual Modbus server that will act on it.

This guide covers four things: how to start the range, how to read the
interface (what the colors and icons actually mean), a set of walkthrough
scenarios, and reference material for instructors extending it.

## Starting the range

The one-command way (see the main [README](../README.md) for details):

```bash
docker compose up --build
```

Then open **http://localhost:5173** — that's the zone overview, and
everything else is reachable from its nav bar.

**No command line after the first run.** Once you've built it once with
the command above, every later session can start from Docker Desktop's GUI
instead: open Docker Desktop, find the **hvac-twin** project, and click its
**Start** button — then **Stop** the same way when you're done. A green
Start means the whole range is actually ready, not just "containers exist."

> If someone updates the app's code and things still look like the old
> version after clicking Start, the images are stale — Docker Desktop's
> Start button reuses whatever was last built, it doesn't rebuild. Run
> `docker compose build` once (or `docker compose up --build`) to pick up
> the change, then Start works normally again.

If you're running things by hand instead (e.g. for development), you need
four processes running at once, each in its own terminal:

```bash
# the server closet twin + its backend (port 8100)
uv run python -m hvac_twin.hmi examples/server_closet_controlled.toml

# the office wing twin + its backend (port 8101)
uv run python -m hvac_twin.hmi examples/office_wing_controlled.toml --port 8101

# the attack console, shared by both twins (port 8000)
uv run python -m uvicorn hvac_twin.console:app --port 8000

# the frontend dev server
cd frontend && npm run dev
```

**Two students, two laptops:** each of you opens the frontend from your
own laptop and points that page's **Target**/**Console** bar at the *other*
laptop's IP instead of `127.0.0.1`. No rebuild needed — it's a runtime
setting saved in your browser.

**One gotcha under Docker Compose:** the attack console's requests run
*inside* the `attack-console` container, so a scenario's default Host
(`127.0.0.1`) would mean that container, not a twin. Under Compose, type
the target's service name instead — `plant` for the closet, `office-plant`
for the office wing. (The Red Team page has this same note printed above
the scenario cards.)

## Navigation guide

Every page shares the same nav bar (**Overview · Server Closet · Office
Wing · Red Team · Defenses**) with the current page highlighted, so you're
never more than one click from anywhere else.

| Page | URL | What it's for |
|---|---|---|
| **Overview** | `/` | The zone picker: two HVAC zones, plus a separate "Research tools" section linking to Red Team and Defenses. Start here. |
| **Server Closet** | `/closet.html` | The flagship single-room scenario: a live equipment diagram, sensed/actual readings, an operator setpoint control, a trend chart, controller tag readout, event log, and this room's defense controls. |
| **Office Wing** | `/office.html` | Three heated zones side by side, each with its own diagram, readings, setpoint control, and controller readout, plus one shared defense panel watching all three zones. |
| **Red Team** | `/attack.html` | Five pre-built attack scenarios (set a target, click Launch) plus the Modbus Terminal for hand-built commands. Styled distinctly from the rest of the app on purpose — see below. |
| **Defenses** | `/defenses.html` | A catalog explaining what each defense is, how it works, and what it does and doesn't catch, plus a zone picker that gives you live Enable/Disable control for whichever zone you select. |

A couple of things worth knowing before you click around:

- **Target / Console bar** at the top of each page is that page's backend
  address. It's saved in your browser only, and changing it reloads the
  page against the new backend.
- **The Red Team page looks different on purpose.** Every other page uses
  the same neutral, professional styling as a real facility app. Red Team
  has a red accent stripe and status dot in its header — a deliberate
  signal that you've stepped from "operating the building" into "attacking
  it." The rest of the chrome (nav bar, fonts, layout) stays identical, so
  it's still obviously the same product, not a different tool.

## Reading the interface

The equipment diagram is the center of every room's page. It isn't trying
to be a realistic floor plan — it's a live instrument, and everything on it
means something specific:

| What you see | What it means |
|---|---|
| **Floor color** | Shifts continuously from blue (cold) through neutral gray (near setpoint) to red (hot), based on the room's *sensed* temperature. A room sitting quietly near its setpoint should look neutral; a room under a heat attack visibly reddens in real time. |
| **Fan (server closet)** | The CRAC unit's fan. It physically spins when the cooling relay is on, and sits still when it's off — not decorative, it's a direct readout of `cooling_relay`. |
| **Coil (office wing)** | The heater. Turns amber when the heating relay is on, gray when it's off. |
| **Small LED on the equipment housing** | Green when that room's equipment is actively running, gray when idle. Same information as the fan/coil state, readable at a glance even in a small screenshot. |
| **Red border + "Alarm" badge** | The room has crossed its alarm threshold (high temperature for the closet, freeze threshold for an office zone). Stays red for as long as the alarm condition holds. |
| **Damage bar (server closet only)** | A cumulative overtemperature counter that only ever goes up. A closet that overheats and then recovers its *temperature* does **not** recover its damage — the bar is a permanent record that the alarm threshold was crossed, which is the point: cooling coming back doesn't undo hardware stress that already happened. |
| **Sensed / Actual readings** | Shown side by side, always — not behind a toggle. **Sensed** is what the controller (and a real operator) sees. **Actual** is the plant's true physical value. They normally track each other closely; a gap beyond a couple of degrees triggers a **Sensor mismatch** flag next to the panel title. That gap is the tell that something upstream of the sensor reading is lying — exactly what a sensor-spoofing attack produces. |
| **Status dot in the page header** | Green "Nominal" or red with the specific alarm message (e.g. "High temperature alarm"). One glance tells you whether *anything* on this page needs attention. |

Elsewhere in the app, the same color language repeats:

- **Scenario status badges** (Red Team page): gray *Idle*, blue *Running*,
  green *Done*, red *Error*.
- **Defense badges** (Defenses page): green *Toggleable* (has a live
  Enable/Disable control) vs. neutral *Always on* (no toggle — it only
  ever monitors, never blocks). Both defenses in this build are currently
  toggleable; a defense with no live control would show *Always on*.
- **Event log rows**: alarm/error events are highlighted in red; everything
  else is neutral gray.

## Operator Setpoint: the legitimate control

Every room page has an **Operator Setpoint** control, separate from
anything on the Red Team page. Type a new value and click **Set**, and it
writes the new setpoint through that room's backend (`/control/setpoint`).

Here's the part worth sitting with: **that control uses the exact same
Modbus write the Red Team page's Setpoint Spoof attack uses** — a real
write to the twin's accept register, over the same unauthenticated wire.
The only difference is who's making the request and through what UI. This
isn't a shortcut we took — it's an honest picture of a real problem: on
plain Modbus, a legitimate operator's command and an attacker's command
look identical. That's exactly why the Auth Proxy defense exists (filtering
by source IP and function code), and it's worth noticing that if you
enable Auth Proxy with an overly strict allowlist, you can accidentally
lock out the legitimate Operator Setpoint control too — a real
operational trade-off, not just an attacker inconvenience.

**Try it:** open **Server Closet**, use Operator Setpoint to set the
cooling setpoint to something normal (say `72`), and watch the Controller
panel's Setpoint value and the schematic both update within a couple of
seconds — the same twin state, the same wire, doing exactly what
commissioning a real controller looks like.

## Roles: red team and blue team

Most of these scenarios make the most sense played by two people (or one
person switching hats): a **red team** student runs attacks from
`/attack.html` against a room, and a **blue team** student watches that
room's own page and, once they've felt the impact, goes to
`/defenses.html` to fight back. Nothing stops one person from doing both —
just do the "before" half fully before peeking at the fix.

---

## Walkthrough scenarios

### 1. Look around first (no attack yet)

1. Open the zone overview and read both zone descriptions.
2. Open **Server Closet**. Watch the trend chart and note the current
   Setpoint, Deadband, and Cooling Relay state. Sensed and Actual should
   already match — nothing is attacking it yet.
3. Open **Office Wing**. Notice each of the three rooms has its own
   setpoint and heating relay, and the middle room (which has two heated
   neighbors) tends to run a little warmer than the two end rooms.
4. Try the **Operator Setpoint** control on either page — type a value a
   couple of degrees off from the current one and click **Set**. Watch it
   land. This is the range working exactly as a real BMS would, before
   anything adversarial happens to it.

This is your baseline. Every attack below is measured against "what normal
looks like," which you've now seen.

### 2. Setpoint spoof vs. the server closet (undefended, then defended)

The flagship scenario: a direct, unauthenticated Modbus write that changes
control behavior immediately — contrast this with the legitimate Operator
Setpoint control you just used in step 1: same wire, same kind of write,
very different intent.

1. On **Red Team**, find the **Setpoint Spoof** card. Leave Host/Port at
   their defaults (`127.0.0.1` / `5020` for bare-metal or two-laptop; the
   closet's service name under Compose) and set Setpoint °F to something
   absurd, like `900`.
2. Click **Launch**.
3. Switch to **Server Closet** and watch: the Setpoint readout jumps, the
   floor color shifts toward red as the closet heats, the Cooling Relay
   turns off (there's nothing to cool toward), and eventually the Damage
   bar starts climbing and the room alarms.
4. Now defend it. Go to **Defenses**, leave the zone picker on **Server
   Closet**. Before clicking Enable, notice the **Allowed IPs** field —
   leave it blank for now (blank means any source IP may connect; only the
   function-code filter applies) and click **Enable**. Note the port it
   starts listening on.
5. Go back to **Red Team** and re-launch Setpoint Spoof — but this time
   point Host/Port at the **auth proxy's** port from step 4, not the
   twin's real Modbus port.
6. Watch the closet's Setpoint this time: it doesn't move. The proxy
   returned a Modbus exception response instead of forwarding the write.

The lesson: the defense doesn't touch the attack script or the twin — it
sits in front of the real port and simply refuses to forward a disallowed
write. Anyone still pointed at the *real* port (5020) can still get through
this way; a real deployment would need the network layer to make the real
port unreachable, not just offer a better-defended alternative.

**Try the source-IP allowlist too.** Disable the proxy, then Enable it
again with `127.0.0.1` typed into Allowed IPs (or, on a two-laptop setup,
the *blue team's* laptop IP — not the red team's). Re-run Setpoint Spoof
against the proxy's port from a source address that *isn't* on that list
(the other laptop, or a different IP if you're on one machine) — the
connection is refused before a single Modbus byte is exchanged, a
different failure mode than the function-code exception above: the client
doesn't get a polite error, the connection just doesn't open at all.

**Note the trade-off:** with the proxy's default function-code allowlist
(reads only), even the legitimate Operator Setpoint control stops working
through the proxy, because a setpoint write needs a write function code.
Defending against writes indiscriminately defends against *legitimate*
writes too — a real design tension, not a bug in this range.

### 3. Deceiving the operator — MITM Proxy

This one never writes a fake value into the twin at all — it lies about
what's on the wire.

1. On **Red Team**, open the **MITM Proxy** card. Set Target Host/Port to
   the closet's real Modbus address, pick a Listen Port, set a Spoof Temp
   well below the real one (e.g. `72`), and check Hide Alarm.
2. Click **Launch**, then point whatever client you're using at the
   proxy's listen port instead of the real one, and watch the closet's
   Sensed reading: it shows the spoofed 72°F, no matter what's really
   happening.
3. Compare Sensed against Actual on the same panel: Actual keeps climbing
   while Sensed stays frozen at the spoofed value — a clear **Sensor
   mismatch** flag, even though everything else on the page looks calm.

The lesson: an operator with no ground-truth channel has no way to tell
this is happening from Sensed alone. This is also structurally why the
anomaly detector (see the Defenses page) *can't* catch this one — it never
touches the twin's actual recorded tag values, only what's on the wire to
one particular client.

### 4. Denial of view — Request Flood

1. On **Red Team**, open **Request Flood**, target the closet's real port,
   and set Connections to something large (`100`+) with a Duration of `15`
   seconds or so.
2. Click **Launch**, then immediately switch to **Server Closet** and try
   to interact with it — the page will feel slow or stale while the flood
   runs.
3. Note what *doesn't* change: the physical simulation (the twin's own
   tick loop) keeps running the entire time, unaffected. Only visibility
   into it is degraded. This is the "loss of view, not loss of control"
   case: the room could genuinely be cooking and you wouldn't know from a
   flooded HMI.

### 5. Lateral movement — Compromised EWS on the office wing

1. On **Red Team**, open **Compromised EWS**, point it at the office
   wing's Modbus port, leave Room 1/2/3 all checked, and set a Setpoint
   that's clearly wrong for all three at once.
2. Click **Launch**, then switch to **Office Wing** and watch all three
   rooms' diagrams react together.
3. The tell that distinguishes this from an equipment fault: **room 1 and
   room 3 share no wall**, so both alarming in the same breath means one
   actor touched every zone at once — a real fault wouldn't do that.

### 6. Build your own attack — the Modbus Terminal

The five scenarios above are convenient, but they're not the only thing
you can do to an unauthenticated Modbus server.

1. On **Red Team**, scroll to the **Modbus Terminal** at the bottom.
2. Try a read first: Host/Port at the closet, Operation `Read Input
   Registers`, Address `0`, Quantity `1`, then **Send**. You should get
   back the raw sensed-temperature register (tenths of a degree F) — the
   exact value the Setpoint Spoof card's Host/Port reads from under the
   hood.
3. Now try a write of your own: Operation `Write Register`, Address `0`
   (the setpoint's *accept* register — see
   `examples/server_closet_controlled.toml`'s comment on why publish/accept
   are different addresses), Values `800`. Confirm on the Server Closet
   page that the setpoint actually moved.
4. Try something the canned scenarios don't do at all: `Read Coils` at
   address `0` to check `high_temp_alarm` directly, or a `Write Coils` at
   an address you don't recognize and see what happens (a well-formed but
   out-of-range write against `ModbusSlaveServer` should come back as a
   clean Modbus exception, not a crash — if you ever get something that
   looks like a hang instead, that's worth reporting).

### 7. Blue team walkthrough — the Defenses page

1. Open **Defenses**. Read both catalog entries. Both are currently marked
   **Toggleable** — Auth Proxy blocks disallowed traffic outright, while
   Anomaly Detection only flags a suspicious jump after the fact (its
   toggle turns the monitor's reporting on and off, not a block).
2. In the zone picker on the right, switch between **Server Closet** and
   **Office Wing** and watch the live control panel update to that zone's
   own Auth Proxy status and Anomaly Detection status — this is one live
   control component doing double duty for both rooms.
3. Re-run scenario 2 (Setpoint Spoof) against the closet's *real* port
   with the auth proxy still disabled — this time, watch Anomaly
   Detection. It should flip to **Anomaly detected** shortly after the
   spoof lands, since a `setpoint_tenths` jump from ~75 to 900 in one scan
   is exactly the kind of physically-implausible rate-of-change it's built
   to catch. Contrast this with what you saw in scenario 3 (MITM) or 4
   (flood) — Anomaly Detection stays **Clear** through both, because
   neither one ever touches a real recorded tag.
4. Now click **Disable** on Anomaly Detection and repeat the spoof. Even
   though the exact same attack lands, the panel now just reads
   **Disabled** — the detector isn't magically less capable, it's simply
   turned off, the same way a real analyst might silence noisy monitoring
   and lose the signal along with the noise.

---

## For instructors: adding a new defense

The Defenses page's catalog is generated, not hand-written, and the page
itself has a card explaining this (**Add Your Own Defense**, at the end of
the catalog list) — this section is the fuller version.

**Just want it listed, with no live control?** Add one entry to
`src/hvac_twin/defenses/catalog.py`:

```python
DefenseDescriptor(
    id="rate-limit",
    title="Per-Connection Rate Limit",
    summary="Caps how many requests a single connection can send per second.",
    how_it_works="...",
    mitigates=("dos-flood",),
    live_control=False,
),
```

That's the whole change — the Defenses page rebuilds its card list from
this file on every load, so nothing on the frontend needs to change.

**Want a real Enable/Disable toggle**, the way Auth Proxy and Anomaly
Detection have? That needs actual working code behind it, which is
unavoidably a bit more:

1. Write the mechanism itself as a new module under
   `src/hvac_twin/defenses/`, following `auth_proxy.py`'s shape — a class
   with `start()`/`stop()` (see its docstring for why it mirrors
   `attacks/mitm_proxy.py`: a defense and an attack are often the same
   network primitive, just used differently). A defense that's just an
   on/off flag (like Anomaly Detection's toggle) can be simpler still —
   see `hmi.py`'s `_anomaly_detection_enabled` closure variable for the
   minimal version.
2. Wire a `GET`/`POST .../start`/`POST .../stop` trio into
   `hvac_twin/hmi.py` next to the existing `/defenses/...` routes (that's
   the file that owns a twin's live Modbus slave, which is why the
   per-twin, start/stop-able defenses live there rather than in the
   twin-agnostic `hvac_twin/console.py`).
3. On the frontend, either extend `components/DefenseControls.tsx` (if
   your defense fits the same "one enable toggle + one status line" shape)
   or add a small sibling component next to it and mount it alongside
   `DefenseControls` on whichever page(s) should show it.
4. Add the matching `DefenseDescriptor` (`live_control=True`) so it also
   appears in the catalog.

There's no way around step 2 onward being real code — a defense that
students can actually turn on has to actually do something on the wire,
which isn't something a catalog entry alone can express.

## For instructors: adding a new attack scenario

Unlike defenses, attacks have no single catalog to append to — each of the
five canned scenarios is its own script, request shape, and card, because
each one genuinely does something different on the wire (a one-shot write,
a standing proxy, a flood, a multi-tag pivot). The Red Team page's own
**Add Your Own Attack** card (at the end of the grid) says the same thing.

**Fastest path, no code:** the Modbus Terminal on that page can already
send any read or write the console can. Every one of the five canned
scenarios started as someone manually finding the right operation/address/
value there before it became a permanent script. For a one-off demo or an
assignment where students discover the attack themselves, this is often
enough — nothing to add.

**To turn a working command into a permanent, shareable scenario:**

1. Write `src/hvac_twin/attacks/my_attack.py` following
   `setpoint_spoof.py`'s shape: connect with the shared
   `wait_for_connection` helper (`attacks/_client.py`), do the write (or
   sequence of writes), close the client in `finally`, and raise
   `ConnectionError`/`RuntimeError` on failure instead of exiting the
   process — that's what lets the console call it directly.
2. Add a small pydantic request model and a
   `POST /attacks/<name>/start` route to `hvac_twin/console.py`, next to
   the existing ones, with a matching idle entry in its module-level
   `_state` dict (add a `/stop` route too if the attack is standing, like
   `mitm-proxy`, rather than one-shot).
3. Copy `frontend/src/attack/scenarios/SetpointSpoofCard.tsx` to a new
   card for your attack's fields, and add it to the grid in
   `frontend/src/attack/AttackApp.tsx`.

If your attack should also show up as something a defense mitigates, add
its id string to the relevant `DefenseDescriptor.mitigates` tuple in
`src/hvac_twin/defenses/catalog.py` — that's what links, e.g., Auth Proxy
to `setpoint-spoof` on the Defenses page.

## For instructors: adding a new room/zone

Adding a third twin follows the exact recipe the closet and office wing
already used:

1. A new `examples/<room>_controlled.toml` project file (physics, control
   program, and Modbus register map — copy an existing one as a template).
2. A new `src/<room>/` frontend folder (`<Room>App.tsx`, `<room>Config.ts`,
   `main.tsx`) mirroring `src/closet/` or `src/office/`, plus a new HTML
   entry and a `vite.config.ts` line.
3. One new entry in `frontend/src/home/rooms.ts` — that alone makes the
   room show up on Overview and in the Defenses page's zone picker; no
   other shared code needs to change.

---

## Troubleshooting

- **A room's page shows "--" for everything / never connects.** Check that
  room's Target bar matches where its backend is actually listening (8100
  for the closet, 8101 for the office wing by default), and that the
  process is actually running.
- **Red Team / Defenses catalog shows a connection error.** Both talk to
  `hvac_twin.console` (port 8000 by default) — make sure that process (or
  the `attack-console` container) is up.
- **An attack "worked" but nothing changed.** Double-check you targeted the
  twin's real Modbus port (5020 for the closet, 5040 for the office wing),
  not a defended proxy's port from a previous scenario.
- **The Operator Setpoint control returns an error.** If Auth Proxy is
  enabled with a restrictive function-code allowlist, it can block
  legitimate writes too — see the note at the end of walkthrough 2. Check
  whether the twin's real port is reachable and whether a defense is
  currently intercepting it.
- **Modbus Terminal returns an error instead of a result.** The error text
  is the real exception from the backend (a connection failure, or a
  Modbus exception response) — it's telling you something true about the
  request you built, not a bug in the terminal.
- **The interface looks out of date / doesn't match this guide.** Under
  Docker, the Start button never rebuilds images on its own — see the note
  under "Starting the range." Ask whoever runs the range to run
  `docker compose build` once.
