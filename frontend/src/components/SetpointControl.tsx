import { useState } from "react";

interface SetpointControlProps {
  apiBase: string;
  tag: string;
  label?: string;
  currentF: number | null;
  minF?: number;
  maxF?: number;
}

/** Legitimate operator write: posts to the HMI's own /control/setpoint,
 * which writes the twin's real Modbus accept register -- the same
 * channel the Red Team console's Setpoint Spoof attack uses. */
export function SetpointControl({
  apiBase,
  tag,
  label = "Setpoint",
  currentF,
  minF = 40,
  maxF = 100,
}: SetpointControlProps) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<string | null>(null);

  const submit = async () => {
    const parsed = Number(draft);
    if (draft.trim() === "" || !Number.isFinite(parsed)) {
      setError("enter a number");
      return;
    }
    setBusy(true);
    setError(null);
    setConfirmed(null);
    try {
      const response = await fetch(`${apiBase}/control/setpoint`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag, value_tenths: Math.round(parsed * 10) }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        setError(body?.detail ?? `request failed (${response.status})`);
      } else {
        setConfirmed(`set to ${parsed.toFixed(1)}°F`);
        setDraft("");
      }
    } catch {
      setError("could not reach the HMI backend");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="setpoint-control">
      <div className="setpoint-control__row">
        <span className="reading__label">{label}</span>
        <span className="reading__value">
          {currentF !== null ? `${currentF.toFixed(1)}°F` : "--"}
        </span>
      </div>
      <div className="setpoint-control__row">
        <input
          className="field__input"
          type="number"
          step="0.5"
          min={minF}
          max={maxF}
          placeholder={`${minF}-${maxF}`}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={busy}
        />
        <button
          type="button"
          className="view-toggle__btn"
          onClick={submit}
          disabled={busy || draft.trim() === ""}
        >
          Set
        </button>
      </div>
      {error && <p className="defense-desc mismatch-flag">{error}</p>}
      {confirmed && <p className="defense-desc">{confirmed}</p>}
    </div>
  );
}
