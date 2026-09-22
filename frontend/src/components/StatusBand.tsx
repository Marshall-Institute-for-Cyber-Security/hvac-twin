interface StatusBandProps {
  twinName: string;
  scanCount: number;
  elapsed: number;
  alarming: boolean;
  alarmMessage: string;
  connected: boolean;
}

function formatElapsed(seconds: number): string {
  const total = Math.floor(seconds);
  const hh = String(Math.floor(total / 3600)).padStart(2, "0");
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

export function StatusBand({
  twinName,
  scanCount,
  elapsed,
  alarming,
  alarmMessage,
  connected,
}: StatusBandProps) {
  return (
    <header className={`status-band ${alarming ? "status-band--alarm" : "status-band--ok"}`}>
      <span className="status-band__title">{twinName}</span>
      <span className="status-band__state">{alarming ? alarmMessage : "Nominal"}</span>
      <span className="status-band__readout">
        Scan {String(scanCount).padStart(5, "0")} &middot; Runtime {formatElapsed(elapsed)}
        {!connected && " · Link lost"}
      </span>
    </header>
  );
}
