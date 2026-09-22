import { useState, type FormEvent } from "react";
import { Field } from "../Field";
import { ScenarioCard } from "../ScenarioCard";
import { startAttack, type ScenarioStatus } from "../attackApi";

interface Props {
  status: ScenarioStatus | undefined;
  onChanged: (status: ScenarioStatus) => void;
}

export function AlarmMaskCard({ status, onChanged }: Props) {
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("5020");
  const [threshold, setThreshold] = useState("999");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await startAttack("alarm-mask", {
        host,
        port: Number(port),
        threshold: Number(threshold),
      });
      onChanged(result);
    } catch (error) {
      onChanged({ name: "alarm-mask", state: "error", detail: String(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScenarioCard
      title="Alarm Mask"
      description="Spoof the high-temp alarm's comparison threshold so it never trips, while ground truth keeps climbing."
      status={status}
      stoppable={false}
      busy={busy}
      onSubmit={submit}
    >
      <Field label="Host" value={host} onChange={setHost} />
      <Field label="Port" value={port} onChange={setPort} type="number" />
      <Field label="Threshold °F" value={threshold} onChange={setThreshold} type="number" />
    </ScenarioCard>
  );
}
