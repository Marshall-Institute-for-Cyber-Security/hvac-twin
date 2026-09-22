import { createApiTarget } from "../config";

// The office wing runs as its own hvac_twin.hmi process, on its own port,
// separate from the closet's -- two twins, two backends, same as the
// operator/attack-console split. Own storage key, own default port
// (8101), so pointing one screen at a different machine never touches
// the other's saved target.
export const officeApiTarget = createApiTarget(
  "hvac-twin.office-api-base",
  "http://127.0.0.1:8101",
);

export interface OfficeZone {
  id: string;
  label: string;
  sensedTag: string; // PLC tag, tenths of a degree F
  groundTruthSignal: string; // bus signal, true float F
  setpointTag: string;
  deadbandTag: string;
  freezeThresholdTag: string;
  freezeAlarmTag: string;
  heatingRelayTag: string;
}

function zone(n: 1 | 2 | 3, label: string): OfficeZone {
  return {
    id: `room_${n}`,
    label,
    sensedTag: `room_${n}_temp_raw`,
    groundTruthSignal: `room_${n}_temp`,
    setpointTag: `room_${n}_setpoint_tenths`,
    deadbandTag: `room_${n}_deadband_tenths`,
    freezeThresholdTag: `room_${n}_freeze_threshold_tenths`,
    freezeAlarmTag: `room_${n}_freeze_alarm`,
    heatingRelayTag: `room_${n}_heating_relay`,
  };
}

export const OFFICE_ZONES: OfficeZone[] = [
  zone(1, "Room 1"),
  zone(2, "Room 2"),
  zone(3, "Room 3"),
];

export const OFFICE_MISMATCH_THRESHOLD_F = 2.0;
