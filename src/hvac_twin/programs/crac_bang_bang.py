"""Bang-bang cooling control for the server closet: latches the CRAC relay
on past setpoint + deadband, off past setpoint - deadband (a seal-in latch,
the same style as digitwin.programs.start_stop_tank.StartStopTankProgram --
not re-derived from scratch each scan), and raises a high-temp alarm as an
independent decision from whether cooling happens to be running.

All temperatures are tenths of a degree Fahrenheit, as an integer -- the
PLC only ever sees the AnalogSensor-scaled reading, never the plant's true
float temperature. That gap is deliberate: Phase 3 attacks target this tag,
not the physics.
"""

from __future__ import annotations

from digitwin.plc import PLC


class CracBangBangProgram:
    def __call__(self, plc: PLC) -> None:
        temp_tenths = int(plc.read_input("closet_temp_raw"))
        setpoint_tenths = int(plc.read("setpoint_tenths"))
        deadband_tenths = int(plc.read("deadband_tenths"))
        alarm_threshold_tenths = int(plc.read("alarm_threshold_tenths"))

        if temp_tenths >= setpoint_tenths + deadband_tenths:
            plc.write("cooling_on", True)
        elif temp_tenths <= setpoint_tenths - deadband_tenths:
            plc.write("cooling_on", False)
        # else: inside the deadband -- hold whatever cooling_on already is

        plc.write_output("cooling_relay", bool(plc.read("cooling_on")))
        plc.write("high_temp_alarm", temp_tenths >= alarm_threshold_tenths)