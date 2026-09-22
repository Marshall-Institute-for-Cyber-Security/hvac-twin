import type { FormEvent, ReactNode } from "react";
import type { ScenarioStatus } from "./attackApi";

interface ScenarioCardProps {
  title: string;
  description: string;
  status: ScenarioStatus | undefined;
  stoppable: boolean;
  busy: boolean;
  onSubmit: (event: FormEvent) => void;
  onStop?: () => void;
  children: ReactNode;
}

export function ScenarioCard({
  title,
  description,
  status,
  stoppable,
  busy,
  onSubmit,
  onStop,
  children,
}: ScenarioCardProps) {
  const state = status?.state ?? "idle";
  return (
    <form className="panel scenario-card" onSubmit={onSubmit}>
      <div className="panel__header">
        <h2 className="panel__title">{title}</h2>
        <span className={`scenario-state scenario-state--${state}`}>
          {state.charAt(0).toUpperCase() + state.slice(1)}
        </span>
      </div>
      <p className="scenario-card__desc">{description}</p>
      <div className="scenario-card__fields">{children}</div>
      {status?.detail && <p className="scenario-card__detail">{status.detail}</p>}
      <div className="scenario-card__actions">
        <button type="submit" className="view-toggle__btn view-toggle__btn--active" disabled={busy}>
          Launch
        </button>
        {stoppable && (
          <button
            type="button"
            className="view-toggle__btn"
            onClick={onStop}
            disabled={busy || state !== "running"}
          >
            Stop
          </button>
        )}
      </div>
    </form>
  );
}
