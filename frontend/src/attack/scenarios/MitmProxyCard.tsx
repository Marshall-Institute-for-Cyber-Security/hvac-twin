import { useState, type FormEvent } from "react";
import { CheckboxField, Field } from "../Field";
import { ScenarioCard } from "../ScenarioCard";
import { startAttack, stopAttack, type ScenarioStatus } from "../attackApi";

interface Props {
  status: ScenarioStatus | undefined;
  onChanged: (status: ScenarioStatus) => void;
}

export function MitmProxyCard({ status, onChanged }: Props) {
  const [listenHost, setListenHost] = useState("127.0.0.1");
  const [listenPort, setListenPort] = useState("5021");
  const [targetHost, setTargetHost] = useState("127.0.0.1");
  const [targetPort, setTargetPort] = useState("5020");
  const [spoofTemp, setSpoofTemp] = useState("75");
  const [hideAlarm, setHideAlarm] = useState(true);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await startAttack("mitm-proxy", {
        listen_host: listenHost,
        listen_port: Number(listenPort),
        target_host: targetHost,
        target_port: Number(targetPort),
        spoof_temp: spoofTemp.trim() === "" ? null : Number(spoofTemp),
        hide_alarm: hideAlarm,
      });
      onChanged(result);
    } catch (error) {
      onChanged({ name: "mitm-proxy", state: "error", detail: String(error) });
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      onChanged(await stopAttack("mitm-proxy"));
    } catch (error) {
      onChanged({ name: "mitm-proxy", state: "error", detail: String(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScenarioCard
      title="MITM Proxy"
      description="Sit between the HMI and the twin; rewrite read responses in flight so the display lies while the wire keeps working."
      status={status}
      stoppable
      busy={busy}
      onSubmit={submit}
      onStop={stop}
    >
      <Field label="Listen host" value={listenHost} onChange={setListenHost} />
      <Field label="Listen port" value={listenPort} onChange={setListenPort} type="number" />
      <Field label="Target host" value={targetHost} onChange={setTargetHost} />
      <Field label="Target port" value={targetPort} onChange={setTargetPort} type="number" />
      <Field label="Spoof temp °F" value={spoofTemp} onChange={setSpoofTemp} type="number" />
      <CheckboxField label="Hide alarm" checked={hideAlarm} onChange={setHideAlarm} />
    </ScenarioCard>
  );
}
