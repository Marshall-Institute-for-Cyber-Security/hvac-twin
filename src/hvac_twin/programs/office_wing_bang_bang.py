"""Bang-bang heating control for the three-zone office wing: the same
seal-in latch as programs.crac_bang_bang.CracBangBangProgram, but
inverted -- this is heating, not cooling, since outdoor is the cold side
here -- and run independently for each of the three rooms within one PLC
scan, the way a single multi-zone RTU controller serves several zones.

All temperatures are tenths of a degree Fahrenheit, as an integer -- the
PLC only ever sees each room's AnalogSensor-scaled reading, never the
plant's true float temperature. freeze_alarm is the heating-side
equivalent of the closet's high_temp_alarm: an independent decision from
whether the heater happens to be running, meant to catch a room getting
dangerously cold (e.g. heater failure), not merely being below setpoint.
"""

from __future__ import annotations

from digitwin.plc import PLC

_ZONES = ("room_1", "room_2", "room_3")


class OfficeWingBangBangProgram:
    def __call__(self, plc: PLC) -> None:
        for zone in _ZONES:
            temp_tenths = int(plc.read_input(f"{zone}_temp_raw"))
            setpoint_tenths = int(plc.read(f"{zone}_setpoint_tenths"))
            deadband_tenths = int(plc.read(f"{zone}_deadband_tenths"))
            freeze_threshold_tenths = int(plc.read(f"{zone}_freeze_threshold_tenths"))

            if temp_tenths <= setpoint_tenths - deadband_tenths:
                plc.write(f"{zone}_heating_on", True)
            elif temp_tenths >= setpoint_tenths + deadband_tenths:
                plc.write(f"{zone}_heating_on", False)
            # else: inside the deadband -- hold whatever heating_on already is

            plc.write_output(f"{zone}_heating_relay", bool(plc.read(f"{zone}_heating_on")))
            plc.write(f"{zone}_freeze_alarm", temp_tenths <= freeze_threshold_tenths)
