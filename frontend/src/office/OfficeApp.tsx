import { useEffect, useState } from "react";
import { ConnectionBar } from "../components/ConnectionBar";
import { DefenseControls } from "../components/DefenseControls";
import { GroundTruthPanel } from "../components/GroundTruthPanel";
import { NavBar } from "../components/NavBar";
import { RoomSchematic } from "../components/RoomSchematic";
import { SetpointControl } from "../components/SetpointControl";
import { StatusBand } from "../components/StatusBand";
import { TagPanel } from "../components/TagPanel";
import { OFFICE_MISMATCH_THRESHOLD_F, OFFICE_ZONES, officeApiTarget } from "./officeConfig";
import { getBusSignal, useLiveStream } from "./officeApi";

const POLL_MS = 5000;

export default function OfficeApp() {
  const { tags, scanCount, elapsed, connected } = useLiveStream();
  const [groundTruthF, setGroundTruthF] = useState<Record<string, number>>({});

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      for (const zone of OFFICE_ZONES) {
        getBusSignal(zone.groundTruthSignal)
          .then((result) => {
            if (!cancelled && typeof result.value === "number") {
              setGroundTruthF((prev) => ({ ...prev, [zone.id]: result.value as number }));
            }
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
  }, []);

  const alarmingZones = OFFICE_ZONES.filter((zone) => tags[zone.freezeAlarmTag] === true);
  const alarming = alarmingZones.length > 0;
  // Deliberately names every alarming zone, not just "ALARM" -- the
  // compromised-EWS attack's tell is exactly this: room_1 and room_3 share
  // no wall, so both freeze-alarming at once is a signal one actor touched
  // every zone in the same breath, not that a single heater failed.
  const alarmMessage = `Freeze alarm — ${alarmingZones.map((z) => z.label).join(", ")}`;

  return (
    <div className="app">
      <NavBar />
      <StatusBand
        twinName="Office Wing"
        scanCount={scanCount}
        elapsed={elapsed}
        alarming={alarming}
        alarmMessage={alarmMessage}
        connected={connected}
      />
      <ConnectionBar target={officeApiTarget} placeholder="http://192.168.1.42:8101" />
      <div className="office-schematic-row">
        {OFFICE_ZONES.map((zone, index) => {
          const sensedF =
            typeof tags[zone.sensedTag] === "number" ? (tags[zone.sensedTag] as number) / 10 : null;
          const setpointF =
            typeof tags[zone.setpointTag] === "number" ? (tags[zone.setpointTag] as number) / 10 : null;
          const joinSide =
            index === 0 ? "right" : index === OFFICE_ZONES.length - 1 ? "left" : "both";
          return (
            <RoomSchematic
              key={zone.id}
              label={zone.label}
              variant="office"
              sensedF={sensedF}
              setpointF={setpointF}
              equipmentOn={tags[zone.heatingRelayTag] === true}
              equipmentKind="heating"
              alarming={tags[zone.freezeAlarmTag] === true}
              joinSide={joinSide}
              minF={50}
              maxF={94}
            />
          );
        })}
      </div>
      <main className="office-grid">
        {OFFICE_ZONES.map((zone) => {
          const sensedF =
            typeof tags[zone.sensedTag] === "number" ? (tags[zone.sensedTag] as number) / 10 : null;
          const setpointF =
            typeof tags[zone.setpointTag] === "number" ? (tags[zone.setpointTag] as number) / 10 : null;
          return (
            <div className="office-grid__zone" key={zone.id}>
              <div className="instrument-rail">
                <GroundTruthPanel
                  title={zone.label}
                  groundTruthF={groundTruthF[zone.id] ?? null}
                  sensedF={sensedF}
                  mismatchThresholdF={OFFICE_MISMATCH_THRESHOLD_F}
                />
                <div className="panel">
                  <h2 className="panel__title">Operator Setpoint</h2>
                  <SetpointControl
                    apiBase={officeApiTarget.getApiBase()}
                    tag={zone.setpointTag}
                    currentF={setpointF}
                    minF={50}
                    maxF={94}
                  />
                </div>
                <TagPanel
                  title="Controller"
                  tags={tags}
                  rows={[
                    {
                      label: "Setpoint",
                      key: zone.setpointTag,
                      format: (v) => (typeof v === "number" ? `${(v / 10).toFixed(1)}°F` : "--"),
                    },
                    {
                      label: "Deadband",
                      key: zone.deadbandTag,
                      format: (v) => (typeof v === "number" ? `±${(v / 10).toFixed(1)}°F` : "--"),
                    },
                    {
                      label: "Freeze threshold",
                      key: zone.freezeThresholdTag,
                      format: (v) => (typeof v === "number" ? `${(v / 10).toFixed(1)}°F` : "--"),
                    },
                    { label: "Heating relay", key: zone.heatingRelayTag },
                  ]}
                />
              </div>
            </div>
          );
        })}
      </main>
      <div className="office-defenses">
        <DefenseControls
          apiBase={officeApiTarget.getApiBase()}
          watchTags={OFFICE_ZONES.map((zone) => zone.setpointTag)}
        />
      </div>
    </div>
  );
}
