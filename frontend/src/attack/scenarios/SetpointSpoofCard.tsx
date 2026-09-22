import { useState, type FormEvent } from "react";
import { Field } from "../Field";
import { ScenarioCard } from "../ScenarioCard";
import { startAttack, type ScenarioStatus } from "../attackApi";

interface Props {
  status: ScenarioStatus | undefined;
  onChanged: (status: ScenarioStatus) => void;
}

export function SetpointSpoofCard({ status, onChanged }: Props) {
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("5020");
  const [setpoint, setSetpoint] = useState("900");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await startAttack("setpoint-spoof", {
        host,
        port: Number(port),
        setpoint: Number(setpoint),
      });
      onChanged(result);
    } catch (error) {
      onChanged({ name: "setpoint-spoof", state: "error", detail: String(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScenarioCard
      title="Setpoint Spoof"
      description="Write an inflated cooling setpoint to the closet's accept register -- plain, unauthenticated Modbus."
      status={status}
      stoppable={false}
      busy={busy}
      onSubmit={submit}
    >
      <Field label="Host" value={host} onChange={setHost} />
      <Field label="Port" value={port} onChange={setPort} type="number" />
      <Field label="Setpoint °F" value={setpoint} onChange={setSetpoint} type="number" />
    </ScenarioCard>
  );
}
