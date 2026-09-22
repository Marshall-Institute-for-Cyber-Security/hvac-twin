import { useState, type FormEvent } from "react";
import { CheckboxField, Field } from "../Field";
import { ScenarioCard } from "../ScenarioCard";
import { startAttack, type ScenarioStatus } from "../attackApi";

interface Props {
  status: ScenarioStatus | undefined;
  onChanged: (status: ScenarioStatus) => void;
}

const ALL_ZONES = ["room_1", "room_2", "room_3"] as const;

export function CompromisedEwsCard({ status, onChanged }: Props) {
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("5040");
  const [setpoint, setSetpoint] = useState("0");
  const [zones, setZones] = useState<Set<string>>(new Set(ALL_ZONES));
  const [busy, setBusy] = useState(false);

  const toggleZone = (zone: string, checked: boolean) => {
    setZones((current) => {
      const next = new Set(current);
      if (checked) next.add(zone);
      else next.delete(zone);
      return next;
    });
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await startAttack("compromised-ews", {
        host,
        port: Number(port),
        setpoint: Number(setpoint),
        zones: ALL_ZONES.filter((zone) => zones.has(zone)),
      });
      onChanged(result);
    } catch (error) {
      onChanged({ name: "compromised-ews", state: "error", detail: String(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScenarioCard
      title="Compromised EWS"
      description="One scripted session reads then writes every office-wing zone's setpoint at once -- non-adjacent rooms freezing together signals an attack, not a failed heater."
      status={status}
      stoppable={false}
      busy={busy}
      onSubmit={submit}
    >
      <Field label="Host" value={host} onChange={setHost} />
      <Field label="Port" value={port} onChange={setPort} type="number" />
      <Field label="Setpoint °F" value={setpoint} onChange={setSetpoint} type="number" />
      {ALL_ZONES.map((zone) => (
        <CheckboxField
          key={zone}
          label={`Room ${zone.slice(-1)}`}
          checked={zones.has(zone)}
          onChange={(checked) => toggleZone(zone, checked)}
        />
      ))}
    </ScenarioCard>
  );
}
