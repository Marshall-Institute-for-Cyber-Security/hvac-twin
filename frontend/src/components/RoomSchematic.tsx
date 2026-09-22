import { useId } from "react";

interface RoomSchematicProps {
  label: string;
  variant: "server" | "office";
  sensedF: number | null;
  setpointF?: number | null;
  equipmentOn: boolean;
  equipmentKind: "cooling" | "heating";
  alarming?: boolean;
  damagePct?: number | null;
  minF?: number;
  maxF?: number;
  joinSide?: "left" | "right" | "both";
}

const COLD_RGB: [number, number, number] = [79, 156, 214]; // --color-accent
const NEUTRAL_RGB: [number, number, number] = [54, 59, 64]; // --color-border
const HOT_RGB: [number, number, number] = [207, 82, 69]; // --color-alarm

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function mixRgb(a: [number, number, number], b: [number, number, number], t: number): string {
  return `rgb(${Math.round(lerp(a[0], b[0], t))}, ${Math.round(lerp(a[1], b[1], t))}, ${Math.round(
    lerp(a[2], b[2], t),
  )})`;
}

/** Maps a temperature to a color along cold (accent blue) -> neutral ->
 * hot (alarm red) -- the same two functional colors used elsewhere for
 * accent/alarm state, just continuous instead of a two-state badge.
 * minF/maxF should bracket the room's *realistic* operating band (not
 * some wide absolute range), otherwise everyday temperatures all land
 * near the flat neutral midpoint and the schematic never visibly reacts
 * to anything short of an extreme attack. */
function tempColor(f: number | null, minF: number, maxF: number): string {
  if (f === null) return "var(--color-border)";
  const mid = (minF + maxF) / 2;
  if (f <= mid) {
    return mixRgb(COLD_RGB, NEUTRAL_RGB, Math.min(1, Math.max(0, (f - minF) / (mid - minF))));
  }
  return mixRgb(NEUTRAL_RGB, HOT_RGB, Math.min(1, Math.max(0, (f - mid) / (maxF - mid))));
}

/** A live SCADA-style schematic, not a chart: a room outline whose fill
 * shifts with sensed temperature, a wall-mounted equipment unit that
 * animates while running, and an alarm flash -- the "see the room" view a
 * trend chart alone can't give. `variant` picks a bit of room-specific
 * set dressing (server racks vs. a window+desk) so a server closet and an
 * office actually read as different kinds of room, not the same gray
 * pane with a different label. Reusable for any twin: it only takes plain
 * data, never an API target. */
export function RoomSchematic({
  label,
  variant,
  sensedF,
  setpointF = null,
  equipmentOn,
  equipmentKind,
  alarming = false,
  damagePct = null,
  minF = 55,
  maxF = 100,
  joinSide,
}: RoomSchematicProps) {
  const gridId = useId();
  const fill = tempColor(sensedF, minF, maxF);
  const classes = ["room-schematic"];
  if (alarming) classes.push("room-schematic--alarm");
  if (joinSide === "left" || joinSide === "both") classes.push("room-schematic--join-left");
  if (joinSide === "right" || joinSide === "both") classes.push("room-schematic--join-right");

  return (
    <div className={classes.join(" ")}>
      <svg
        viewBox="0 0 200 140"
        className="room-schematic__svg"
        role="img"
        aria-label={`${label} schematic`}
      >
        <defs>
          <pattern id={gridId} width="14" height="14" patternUnits="userSpaceOnUse">
            <path d="M 14 0 L 0 0 0 14" className="room-schematic__grid-line" />
          </pattern>
        </defs>

        <rect x="8" y="8" width="184" height="124" rx="2" fill={fill} className="room-schematic__floor" />
        <rect
          x="8"
          y="8"
          width="184"
          height="124"
          rx="2"
          fill={`url(#${gridId})`}
          className="room-schematic__floor-grid"
        />

        {variant === "server" ? (
          <g className="room-schematic__racks">
            {[0, 1, 2].map((i) => (
              <g key={i} transform={`translate(${18 + i * 22}, 18)`}>
                <rect width="16" height="94" rx="1" className="room-schematic__rack" />
                {[0, 1, 2, 3, 4, 5].map((j) => (
                  <line
                    key={j}
                    x1="2.5"
                    x2="13.5"
                    y1={9 + j * 14}
                    y2={9 + j * 14}
                    className="room-schematic__rack-slot"
                  />
                ))}
              </g>
            ))}
          </g>
        ) : (
          <>
            <rect x="34" y="8" width="56" height="5" className="room-schematic__window" />
            <g transform="translate(22, 96)" className="room-schematic__desk">
              <rect width="38" height="12" rx="1" className="room-schematic__desk-top" />
              <rect x="3" y="12" width="4" height="14" className="room-schematic__desk-leg" />
              <rect x="31" y="12" width="4" height="14" className="room-schematic__desk-leg" />
            </g>
          </>
        )}

        <g transform="translate(148, 18)">
          <rect width="38" height="26" rx="2" className="room-schematic__equipment-housing" />
          <line x1="4" x2="4" y1="4" y2="22" className="room-schematic__equipment-grille" />
          <line x1="34" x2="34" y1="4" y2="22" className="room-schematic__equipment-grille" />
          <circle
            cx="32"
            cy="6"
            r="1.6"
            className={equipmentOn ? "room-schematic__led room-schematic__led--on" : "room-schematic__led"}
          />
          <g
            transform="translate(19, 15)"
            className={
              equipmentOn
                ? `room-schematic__equipment room-schematic__equipment--${equipmentKind} room-schematic__equipment--on`
                : `room-schematic__equipment room-schematic__equipment--${equipmentKind}`
            }
          >
            {equipmentKind === "cooling" ? (
              <g className="room-schematic__fan">
                <circle r="9" className="room-schematic__equipment-body" />
                <path d="M0,0 L0,-7.5 A4,4 0 0 1 3.5,-3.5 Z" className="room-schematic__blade" />
                <path d="M0,0 L7.5,0 A4,4 0 0 1 3.5,3.5 Z" className="room-schematic__blade" />
                <path d="M0,0 L0,7.5 A4,4 0 0 1 -3.5,3.5 Z" className="room-schematic__blade" />
                <path d="M0,0 L-7.5,0 A4,4 0 0 1 -3.5,-3.5 Z" className="room-schematic__blade" />
              </g>
            ) : (
              <g>
                <rect x="-9" y="-6.5" width="18" height="13" rx="2" className="room-schematic__equipment-body" />
                <path d="M-5.5,-6.5 V6.5 M-2,-6.5 V6.5 M2,-6.5 V6.5 M5.5,-6.5 V6.5" className="room-schematic__coil" />
              </g>
            )}
          </g>
        </g>

        <g transform="translate(85, 118)" className="room-schematic__vent">
          <rect width="30" height="7" rx="1" className="room-schematic__vent-housing" />
          {[4, 9, 14, 19, 24].map((x) => (
            <line key={x} x1={x} x2={x} y1="1.5" y2="5.5" className="room-schematic__vent-slat" />
          ))}
        </g>

        <rect x="2" y="2" width="196" height="136" rx="3" className="room-schematic__wall" />
      </svg>
      <div className="room-schematic__readout">
        <span className="room-schematic__label">{label}</span>
        <span className="room-schematic__temp">{sensedF !== null ? `${sensedF.toFixed(1)}°F` : "--"}</span>
        {setpointF !== null && (
          <span className="room-schematic__setpoint">set {setpointF.toFixed(1)}°F</span>
        )}
        {alarming && <span className="room-schematic__alarm-badge">Alarm</span>}
      </div>
      {damagePct !== null && (
        <div className="room-schematic__damage">
          <span className="room-schematic__damage-label">Damage</span>
          <div className="room-schematic__damage-bar">
            <div
              className="room-schematic__damage-fill"
              style={{ width: `${Math.min(100, Math.max(0, damagePct))}%` }}
            />
          </div>
          <span className="room-schematic__damage-value">{damagePct.toFixed(0)}%</span>
        </div>
      )}
    </div>
  );
}
