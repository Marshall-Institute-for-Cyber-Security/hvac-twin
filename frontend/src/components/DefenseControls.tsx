import { useEffect, useState } from "react";

interface AuthProxyStatus {
  running: boolean;
  listen_host: string | null;
  listen_port: number | null;
  allowed_source_ips: string[] | null;
  allowed_function_codes: number[] | null;
}

interface RateAnomaly {
  tag: string;
  from_value: number;
  to_value: number;
  rate: number;
  limit: number;
}

interface AnomalyDetectionStatus {
  enabled: boolean;
}

const ANOMALY_MAX_RATE = 50;
const POLL_MS = 4000;

interface DefenseControlsProps {
  apiBase: string;
  label?: string;
  watchTags: string[];
}

/** The live per-room control half of the defenses story (the other half
 * is the catalog on defenses.html) -- reusable for any twin's HMI: it
 * only takes a backend target and which tags to watch, never assumes
 * which room it's controlling. */
export function DefenseControls({ apiBase, label, watchTags }: DefenseControlsProps) {
  const [proxyStatus, setProxyStatus] = useState<AuthProxyStatus>({
    running: false,
    listen_host: null,
    listen_port: null,
    allowed_source_ips: null,
    allowed_function_codes: null,
  });
  const [anomaliesByTag, setAnomaliesByTag] = useState<Record<string, RateAnomaly[]>>({});
  const [anomalyStatus, setAnomalyStatus] = useState<AnomalyDetectionStatus>({ enabled: true });
  const [allowIps, setAllowIps] = useState("");
  const [busy, setBusy] = useState(false);
  const [anomalyBusy, setAnomalyBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const watchKey = watchTags.join(",");

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      fetch(`${apiBase}/defenses/auth-proxy`)
        .then((r) => r.json())
        .then((data) => {
          if (!cancelled) setProxyStatus(data);
        })
        .catch(() => undefined);
      fetch(`${apiBase}/defenses/anomaly-detection`)
        .then((r) => r.json())
        .then((data) => {
          if (!cancelled) setAnomalyStatus(data);
        })
        .catch(() => undefined);
      for (const tag of watchKey.split(",").filter(Boolean)) {
        fetch(`${apiBase}/anomalies/${tag}?max_rate_per_s=${ANOMALY_MAX_RATE}`)
          .then((r) => (r.ok ? r.json() : []))
          .then((data) => {
            if (!cancelled) setAnomaliesByTag((prev) => ({ ...prev, [tag]: data }));
          })
          .catch(() => undefined);
      }
    };
    poll();
    const interval = window.setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [apiBase, watchKey]);

  const toggleProxy = async () => {
    setBusy(true);
    setError(null);
    try {
      const parsedIps = allowIps
        .split(",")
        .map((ip) => ip.trim())
        .filter((ip) => ip.length > 0);
      const response = proxyStatus.running
        ? await fetch(`${apiBase}/defenses/auth-proxy/stop`, { method: "POST" })
        : await fetch(`${apiBase}/defenses/auth-proxy/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              allow_functions: [3, 4],
              ...(parsedIps.length > 0 ? { allow_ips: parsedIps } : {}),
            }),
          });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setError(body?.detail ?? `request failed (${response.status})`);
      }
    } catch {
      setError("could not reach the HMI backend");
    } finally {
      // Always resync from the server, whether the toggle succeeded, was
      // rejected (e.g. 409 because another tab already changed it), or the
      // request failed outright.
      try {
        const updated = await fetch(`${apiBase}/defenses/auth-proxy`).then((r) => r.json());
        setProxyStatus(updated);
      } catch {
        // leave proxyStatus as-is; the next poll tick will retry
      }
      setBusy(false);
    }
  };

  const toggleAnomalyDetection = async () => {
    setAnomalyBusy(true);
    try {
      const response = await fetch(
        `${apiBase}/defenses/anomaly-detection/${anomalyStatus.enabled ? "stop" : "start"}`,
        { method: "POST" },
      );
      if (response.ok) setAnomalyStatus(await response.json());
    } catch {
      // next poll tick retries
    } finally {
      setAnomalyBusy(false);
    }
  };

  const allAnomalies = Object.values(anomaliesByTag).flat();
  const anomalous = allAnomalies.length > 0;
  const latest = anomalous ? allAnomalies[allAnomalies.length - 1] : null;

  return (
    <section className="panel">
      <h2 className="panel__title">{label ? `Defenses — ${label}` : "Defenses"}</h2>

      <div className="defense-row">
        <div>
          <span className="reading__label">Auth proxy (reads only)</span>
          <p className="defense-desc">
            {proxyStatus.running
              ? `Enforcing on port ${proxyStatus.listen_port} — point attackers here.`
              : "Not running — the real Modbus port is wide open."}
          </p>
          {proxyStatus.running && (
            <p className="defense-desc">
              Allowed IPs:{" "}
              {proxyStatus.allowed_source_ips?.length
                ? proxyStatus.allowed_source_ips.join(", ")
                : "any (no source-IP restriction)"}
            </p>
          )}
        </div>
        <button
          type="button"
          className={
            proxyStatus.running ? "view-toggle__btn view-toggle__btn--active" : "view-toggle__btn"
          }
          onClick={toggleProxy}
          disabled={busy}
        >
          {proxyStatus.running ? "Disable" : "Enable"}
        </button>
      </div>
      {!proxyStatus.running && (
        <label className="field">
          <span className="field__label">Allowed IPs (comma-separated, blank = any source)</span>
          <input
            className="field__input"
            value={allowIps}
            onChange={(event) => setAllowIps(event.target.value)}
            placeholder="127.0.0.1, 192.168.1.50"
            disabled={busy}
          />
        </label>
      )}
      {error && <p className="defense-desc mismatch-flag">{error}</p>}

      <div className="defense-row">
        <div>
          <span className="reading__label">Anomaly detection ({watchTags.join(", ")})</span>
          <p className="defense-desc">
            {!anomalyStatus.enabled
              ? "Disabled."
              : anomalous
                ? "Anomaly detected."
                : "Clear — monitoring."}
          </p>
        </div>
        <button
          type="button"
          className={
            anomalyStatus.enabled ? "view-toggle__btn view-toggle__btn--active" : "view-toggle__btn"
          }
          onClick={toggleAnomalyDetection}
          disabled={anomalyBusy}
        >
          {anomalyStatus.enabled ? "Disable" : "Enable"}
        </button>
      </div>
      {anomalyStatus.enabled && latest && (
        <p className="defense-desc">
          {latest.tag}: {latest.from_value} → {latest.to_value} ({latest.rate.toFixed(1)}/s, limit{" "}
          {latest.limit})
        </p>
      )}
    </section>
  );
}
