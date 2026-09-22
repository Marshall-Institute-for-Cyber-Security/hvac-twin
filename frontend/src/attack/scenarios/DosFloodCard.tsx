import { useState, type FormEvent } from "react";
import { Field } from "../Field";
import { ScenarioCard } from "../ScenarioCard";
import { startAttack, stopAttack, type ScenarioStatus } from "../attackApi";

interface Props {
  status: ScenarioStatus | undefined;
  onChanged: (status: ScenarioStatus) => void;
}

export function DosFloodCard({ status, onChanged }: Props) {
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("5020");
  const [connections, setConnections] = useState("50");
  const [durationS, setDurationS] = useState("15");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await startAttack("dos-flood", {
        host,
        port: Number(port),
        connections: Number(connections),
        duration_s: Number(durationS),
      });
      onChanged(result);
    } catch (error) {
      onChanged({ name: "dos-flood", state: "error", detail: String(error) });
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      onChanged(await stopAttack("dos-flood"));
    } catch (error) {
      onChanged({ name: "dos-flood", state: "error", detail: String(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScenarioCard
      title="Request Flood"
      description="Flood the Modbus port with concurrent connections -- the HMI goes slow/dark while the physical process keeps running unattended."
      status={status}
      stoppable
      busy={busy}
      onSubmit={submit}
      onStop={stop}
    >
      <Field label="Host" value={host} onChange={setHost} />
      <Field label="Port" value={port} onChange={setPort} type="number" />
      <Field label="Connections" value={connections} onChange={setConnections} type="number" />
      <Field label="Duration (s)" value={durationS} onChange={setDurationS} type="number" />
    </ScenarioCard>
  );
}
