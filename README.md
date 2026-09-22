# HVAC Digital Twin

A working HVAC building-management system, digital twin, and live ICS/OT
security range in one package. It's built on
[DigiTwin](https://github.com/Marshall-Institute-for-Cyber-Security/DigiTwin)
(a soft-PLC + physics framework): real thermal physics, real bang-bang
control logic, and a real unauthenticated Modbus TCP interface — the same
protocol exposure a lot of real building equipment ships with.

The frontend (`ICS BMS Sim`) looks and works like an ordinary facility
monitoring app: two rooms, live sensor readings, an operator setpoint
control, trend charts. It also happens to be attackable, because that's
what it's teaching — a **Red Team Console** for launching real Modbus
attacks against it, and a **Defenses** page for turning on real mitigations
and watching them actually work.

For a guided tour — walkthrough scenarios, what the colors and icons mean,
how to play red team vs. blue team — see
**[docs/STUDENT_GUIDE.md](docs/STUDENT_GUIDE.md)**. This file covers just
getting it running.

## Quick start (Docker Compose)

The one-command way to bring up everything — both rooms' backends, the
attack console, and the frontend:

```bash
docker compose up --build
```

Then open **http://localhost:5173** and start from there.

That's it — no separate DigiTwin checkout needed; it's a public repo, so
Compose pulls it straight from GitHub during the build (see `compose.yaml`).

**After that first build**, you don't need the command line again: open
Docker Desktop, find the **hvac-twin** project, and use its Start/Stop
button. Every service reports real health (not just "running"), and the
frontend won't come up until its three backends are actually answering.

To sanity-check the whole stack on a given machine without clicking through
it by hand:

```bash
./scripts/verify_compose_stack.sh
```

It brings the stack up, waits for every service to be healthy, fires a real
attack across containers, confirms it landed, then tears everything down —
and exits non-zero if anything's wrong.

## Running it without Docker

Useful for development, or if you'd rather run things directly. You need
[uv](https://docs.astral.sh/uv/) and Node.js — `uv sync` fetches DigiTwin
itself (it's a git dependency, `[tool.uv.sources]` in `pyproject.toml`),
along with everything else:

```bash
uv sync
```

Then four processes, each in its own terminal:

```bash
# server closet twin + its backend (port 8100)
uv run python -m hvac_twin.hmi examples/server_closet_controlled.toml

# office wing twin + its backend (port 8101)
uv run python -m hvac_twin.hmi examples/office_wing_controlled.toml --port 8101

# attack console, shared by both rooms (port 8000)
uv run python -m uvicorn hvac_twin.console:app --port 8000

# frontend dev server
cd frontend && npm run dev
```

## What's in the repo

| Path | What it is |
|---|---|
| `src/hvac_twin/plant/`, `programs/` | The physics model and control logic each room runs. |
| `src/hvac_twin/attacks/` | Each red-team scenario, as a standalone script — runnable on its own or through the console. |
| `src/hvac_twin/defenses/` | Each defense's actual mechanism (e.g. `auth_proxy.py`), plus the catalog the Defenses page reads from. |
| `src/hvac_twin/hmi.py` | Per-room backend: live tags, trends, events, and the one legitimate write path (`/control/setpoint`). |
| `src/hvac_twin/console.py` | The shared attack console backend (one process serves attacks against either room). |
| `frontend/` | The ICS BMS Sim web app — five pages, one Vite entry each (see `frontend/vite.config.ts`). |
| `examples/*.toml` | Room definitions (physics parameters, tag map, Modbus register layout). |
| `docs/STUDENT_GUIDE.md` | The student-facing walkthrough and reference. |
| `docs/ROADMAP.md`, `docs/TODO.md` | Development history and planning notes — not needed to use the range. |

## Two people, two laptops

Every page's connection bar (Target / Console) is a runtime setting saved
in your browser — no rebuild needed. Point one laptop's page at the other
laptop's IP instead of `127.0.0.1` and you have a red-team laptop and a
blue-team laptop watching the same twin.

One Compose-specific wrinkle: an attack scenario's request runs *inside*
the `attack-console` container, so its form's default Host (`127.0.0.1`)
means that container, not a room. Under Compose, type the target's service
name instead — `plant` for the closet, `office-plant` for the office wing.

## Development

```bash
uv run pytest          # backend tests
uv run ruff check .    # lint
uv run mypy            # type check

cd frontend
npx tsc --noEmit -p tsconfig.app.json   # frontend type check
npx oxlint src/                         # frontend lint
npx vite build                          # production build
```
