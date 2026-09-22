interface GroundTruthPanelProps {
  title: string;
  groundTruthF: number | null;
  sensedF: number | null;
  mismatchThresholdF: number;
}

/** Always shows both readings rather than hiding "actual" behind a tab:
 * Sensed is what the controller (and an operator) sees; Actual is the
 * plant's real value. Normally they track each other closely -- a gap
 * beyond the threshold is the tell that something upstream of the sensor
 * reading is lying, which is exactly the case a sensor-spoofing attack
 * produces. */
export function GroundTruthPanel({
  title,
  groundTruthF,
  sensedF,
  mismatchThresholdF,
}: GroundTruthPanelProps) {
  const mismatch =
    groundTruthF !== null && sensedF !== null
      ? Math.abs(groundTruthF - sensedF) >= mismatchThresholdF
      : false;

  return (
    <section className="panel">
      <div className="panel__header">
        <h2 className="panel__title">{title}</h2>
        {mismatch && <span className="mismatch-flag">Sensor mismatch</span>}
      </div>
      <div className="reading-pair">
        <div className="reading">
          <span className="reading__label">Sensed</span>
          <span className="reading__value">{sensedF !== null ? sensedF.toFixed(1) : "--"}°F</span>
        </div>
        <div className="reading reading--secondary">
          <span className="reading__label">Actual</span>
          <span className="reading__value">
            {groundTruthF !== null ? groundTruthF.toFixed(1) : "--"}°F
          </span>
        </div>
      </div>
    </section>
  );
}
