// Server closet tag/signal names -- moved out of the root config.ts so the
// closet is a named room like the office wing, not "the default."
export const CLOSET = {
  sensedTag: "closet_temp_raw", // PLC tag, tenths of a degree F
  groundTruthSignal: "closet_temp", // bus signal, true float F
  setpointTag: "setpoint_tenths",
  deadbandTag: "deadband_tenths",
  alarmThresholdTag: "alarm_threshold_tenths",
  alarmTag: "high_temp_alarm",
  coolingRelayTag: "cooling_relay",
  damageSignal: "closet_damage",
  mismatchThresholdF: 2.0,
} as const;
