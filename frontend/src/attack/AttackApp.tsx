import { useEffect, useState } from "react";
import { NavBar } from "../components/NavBar";
import { ConsoleTargetBar } from "./ConsoleTargetBar";
import { ModbusTerminal } from "./ModbusTerminal";
import { AlarmMaskCard } from "./scenarios/AlarmMaskCard";
import { CompromisedEwsCard } from "./scenarios/CompromisedEwsCard";
import { DosFloodCard } from "./scenarios/DosFloodCard";
import { MitmProxyCard } from "./scenarios/MitmProxyCard";
import { SetpointSpoofCard } from "./scenarios/SetpointSpoofCard";
import { listAttacks, type ScenarioStatus } from "./attackApi";

const POLL_MS = 3000;

export default function AttackApp() {
  const [statuses, setStatuses] = useState<Record<string, ScenarioStatus>>({});

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      listAttacks()
        .then((results) => {
          if (cancelled) return;
          const byName: Record<string, ScenarioStatus> = {};
          for (const status of results) byName[status.name] = status;
          setStatuses(byName);
        })
        .catch(() => undefined);
    };
    poll();
    const interval = window.setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const onChanged = (status: ScenarioStatus) => {
    setStatuses((current) => ({ ...current, [status.name]: status }));
  };

  return (
    <div className="app">
      <NavBar />
      <header className="status-band status-band--alarm">
        <span className="status-band__title">Red Team Console</span>
        <span className="status-band__state">Unauthenticated Modbus access</span>
        <span className="status-band__readout">Five scenarios plus a raw command terminal</span>
      </header>
      <ConsoleTargetBar />
      <p className="defense-desc attack-grid__hint">
        Under Docker Compose, Host needs the twin's service name, not 127.0.0.1 --{" "}
        <code>plant</code> (closet) or <code>office-plant</code> (office).
      </p>
      <main className="attack-grid">
        <SetpointSpoofCard status={statuses["setpoint-spoof"]} onChanged={onChanged} />
        <AlarmMaskCard status={statuses["alarm-mask"]} onChanged={onChanged} />
        <MitmProxyCard status={statuses["mitm-proxy"]} onChanged={onChanged} />
        <DosFloodCard status={statuses["dos-flood"]} onChanged={onChanged} />
        <CompromisedEwsCard status={statuses["compromised-ews"]} onChanged={onChanged} />
        <ModbusTerminal />
        <article className="panel defense-card defense-card--extend attack-grid__extend">
          <div className="panel__header">
            <h2 className="panel__title">Add Your Own Attack</h2>
            <span className="scenario-state">Extension point</span>
          </div>
          <p className="defense-desc">
            No code: the Modbus Terminal above sends any read or write this console
            can. Try it live before writing anything permanent.
          </p>
          <p className="defense-desc">
            To make it permanent: write{" "}
            <code>src/hvac_twin/attacks/my_attack.py</code> like{" "}
            <code>setpoint_spoof.py</code>, add a{" "}
            <code>POST /attacks/&lt;name&gt;/start</code> route in{" "}
            <code>console.py</code>, then copy <code>SetpointSpoofCard.tsx</code> for
            a new card above.
          </p>
        </article>
      </main>
    </div>
  );
}
