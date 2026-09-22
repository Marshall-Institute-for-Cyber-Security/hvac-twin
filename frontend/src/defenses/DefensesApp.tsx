import { useEffect, useState } from "react";
import { getConsoleBase } from "../attack/attackApi";
import { DefenseControls } from "../components/DefenseControls";
import { NavBar } from "../components/NavBar";
import { ROOMS } from "../home/rooms";

interface DefenseInfo {
  id: string;
  title: string;
  summary: string;
  how_it_works: string;
  mitigates: string[];
  live_control: boolean;
}

export default function DefensesApp() {
  const [catalog, setCatalog] = useState<DefenseInfo[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedRoomId, setSelectedRoomId] = useState<string>(ROOMS[0]?.id ?? "");

  useEffect(() => {
    fetch(`${getConsoleBase()}/defenses/catalog`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setCatalog)
      .catch((err: unknown) => setCatalogError(String(err)));
  }, []);

  const selectedRoom = ROOMS.find((room) => room.id === selectedRoomId);

  return (
    <div className="app">
      <NavBar />
      <header className="status-band">
        <span className="status-band__title">Defenses</span>
      </header>
      <main className="defenses-grid">
        <section className="defenses-catalog">
          {catalogError && (
            <p className="defense-desc">
              Could not reach the attack console at {getConsoleBase()}: {catalogError}
            </p>
          )}
          {catalog.map((defense) => (
            <article key={defense.id} className="panel defense-card">
              <div className="panel__header">
                <h2 className="panel__title">{defense.title}</h2>
                <span
                  className={
                    defense.live_control
                      ? "scenario-state scenario-state--done"
                      : "scenario-state"
                  }
                >
                  {defense.live_control ? "Toggleable" : "Always on"}
                </span>
              </div>
              <p className="defense-desc">{defense.summary}</p>
              <p className="defense-desc">{defense.how_it_works}</p>
              {defense.mitigates.length > 0 && (
                <p className="defense-desc">Mitigates: {defense.mitigates.join(", ")}</p>
              )}
            </article>
          ))}
          <article className="panel defense-card defense-card--extend">
            <div className="panel__header">
              <h2 className="panel__title">Add Your Own Defense</h2>
              <span className="scenario-state">Extension point</span>
            </div>
            <p className="defense-desc">
              Cards above come from <code>src/hvac_twin/defenses/catalog.py</code>. Add a{" "}
              <code>DefenseDescriptor</code> there and it appears here automatically.
            </p>
            <p className="defense-desc">
              For a live toggle like Auth Proxy: add a module under{" "}
              <code>src/hvac_twin/defenses/</code> with <code>start()</code>/
              <code>stop()</code>, wire start/stop routes into{" "}
              <code>hvac_twin/hmi.py</code>, and extend{" "}
              <code>components/DefenseControls.tsx</code> to drive it.
            </p>
          </article>
        </section>
        <aside className="defenses-controls">
          <div className="panel">
            <h2 className="panel__title">Live Control</h2>
            <label className="field">
              <span className="field__label">Room</span>
              <select
                className="field__input"
                value={selectedRoomId}
                onChange={(event) => setSelectedRoomId(event.target.value)}
              >
                {ROOMS.map((room) => (
                  <option key={room.id} value={room.id}>
                    {room.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {selectedRoom && (
            <DefenseControls
              apiBase={selectedRoom.defaultApiBase}
              label={selectedRoom.label}
              watchTags={selectedRoom.watchTags}
            />
          )}
        </aside>
      </main>
    </div>
  );
}
