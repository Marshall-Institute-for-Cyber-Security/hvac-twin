import { useEffect, useState } from "react";
import { ConnectionBar } from "../components/ConnectionBar";
import { DefenseControls } from "../components/DefenseControls";
import { EventLog } from "../components/EventLog";
import { GroundTruthPanel } from "../components/GroundTruthPanel";
import { NavBar } from "../components/NavBar";
import { RoomSchematic } from "../components/RoomSchematic";
import { SetpointControl } from "../components/SetpointControl";
import { StatusBand } from "../components/StatusBand";
import { TagPanel } from "../components/TagPanel";
import { TrendChart } from "../components/TrendChart";
import { CLOSET } from "./closetConfig";
import { getApiBase } from "../config";
import { getBusSignal, getEvents, getSeries, useLiveStream, type SeriesPoint } from "../api";

const POLL_MS = 5000;

export default function ClosetApp() {
  const { tags, events: liveEvents, scanCount, elapsed, connected } = useLiveStream();
  const [groundTruthF, setGroundTruthF] = useState<number | null>(null);
  const [damagePct, setDamagePct] = useState<number | null>(null);
  const [series, setSeries] = useState<SeriesPoint[]>([]);
  const [initialEvents, setInitialEvents] = useState<Awaited<ReturnType<typeof getEvents>>>([]);

  useEffect(() => {
    getEvents()
      .then(setInitialEvents)
      .catch(() => setInitialEvents([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      getBusSignal(CLOSET.groundTruthSignal)
        .then((result) => {
          if (!cancelled && typeof result.value === "number") setGroundTruthF(result.value);
        })
        .catch(() => undefined);
      getBusSignal(CLOSET.damageSignal)
        .then((result) => {
          if (!cancelled && typeof result.value === "number") setDamagePct(result.value);
        })
        .catch(() => undefined);
      getSeries(CLOSET.sensedTag)
        .then((result) => {
          if (!cancelled) setSeries(result);
        })
        .catch(() => undefined);
    };
    poll();
    const interval = window.setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const alarming = tags[CLOSET.alarmTag] === true;
  const sensedF =
    typeof tags[CLOSET.sensedTag] === "number" ? (tags[CLOSET.sensedTag] as number) / 10 : null;
  const setpointF =
    typeof tags[CLOSET.setpointTag] === "number" ? (tags[CLOSET.setpointTag] as number) / 10 : null;
  const allEvents = initialEvents.length > 0 ? [...initialEvents, ...liveEvents] : liveEvents;

  return (
    <div className="app">
      <NavBar />
      <StatusBand
        twinName="Server Closet"
        scanCount={scanCount}
        elapsed={elapsed}
        alarming={alarming}
        alarmMessage="High temperature alarm"
        connected={connected}
      />
      <ConnectionBar />
      <section className="equipment-band">
        <RoomSchematic
          label="Server Closet"
          variant="server"
          sensedF={sensedF}
          setpointF={setpointF}
          equipmentOn={tags[CLOSET.coolingRelayTag] === true}
          equipmentKind="cooling"
          alarming={alarming}
          damagePct={damagePct}
          minF={55}
          maxF={95}
        />
        <div className="instrument-rail">
          <GroundTruthPanel
            title="Closet Temperature"
            groundTruthF={groundTruthF}
            sensedF={sensedF}
            mismatchThresholdF={CLOSET.mismatchThresholdF}
          />
          <div className="panel">
            <h2 className="panel__title">Operator Setpoint</h2>
            <SetpointControl
              apiBase={getApiBase()}
              tag={CLOSET.setpointTag}
              currentF={setpointF}
              minF={55}
              maxF={95}
            />
          </div>
        </div>
      </section>
      <main className="detail-band">
        <TrendChart data={series} setpointF={setpointF} />
        <div className="instrument-rail">
          <TagPanel
            title="Controller"
            tags={tags}
            rows={[
              {
                label: "Setpoint",
                key: CLOSET.setpointTag,
                format: (v) => (typeof v === "number" ? `${(v / 10).toFixed(1)}°F` : "--"),
              },
              {
                label: "Deadband",
                key: CLOSET.deadbandTag,
                format: (v) => (typeof v === "number" ? `±${(v / 10).toFixed(1)}°F` : "--"),
              },
              {
                label: "Alarm threshold",
                key: CLOSET.alarmThresholdTag,
                format: (v) => (typeof v === "number" ? `${(v / 10).toFixed(1)}°F` : "--"),
              },
              { label: "Cooling relay", key: CLOSET.coolingRelayTag },
            ]}
          />
          <DefenseControls apiBase={getApiBase()} watchTags={[CLOSET.setpointTag]} />
          <EventLog events={allEvents} />
        </div>
      </main>
    </div>
  );
}
