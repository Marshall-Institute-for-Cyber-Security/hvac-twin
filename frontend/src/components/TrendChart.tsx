import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SeriesPoint } from "../api";

interface TrendChartProps {
  data: SeriesPoint[];
  setpointF: number | null;
}

const MONO_FONT = '"IBM Plex Mono", ui-monospace, monospace';

export function TrendChart({ data, setpointF }: TrendChartProps) {
  const points = data.map((point) => ({
    t: point.timestamp,
    value: typeof point.value === "number" ? point.value / 10 : null,
  }));

  return (
    <section className="panel">
      <h2 className="panel__title">Sensed Temperature, Trailing</h2>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="t"
            tick={{ fill: "var(--color-text-tertiary)", fontFamily: MONO_FONT, fontSize: 11 }}
            axisLine={{ stroke: "var(--color-border)" }}
            tickLine={false}
          />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fill: "var(--color-text-tertiary)", fontFamily: MONO_FONT, fontSize: 11 }}
            axisLine={{ stroke: "var(--color-border)" }}
            tickLine={false}
            width={40}
          />
          {setpointF !== null && (
            <ReferenceLine y={setpointF} stroke="var(--color-text-tertiary)" strokeDasharray="4 4" />
          )}
          <Tooltip
            contentStyle={{
              background: "var(--color-surface-raised)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              fontFamily: MONO_FONT,
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--color-text-secondary)" }}
            itemStyle={{ color: "var(--color-accent)" }}
            formatter={(value) => [
              typeof value === "number" ? `${value.toFixed(1)}°F` : "--",
              "sensed",
            ]}
            labelFormatter={(t) => `t=${typeof t === "number" ? t.toFixed(0) : t}s`}
          />
          <Line
            type="stepAfter"
            dataKey="value"
            stroke="var(--color-accent)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </section>
  );
}
