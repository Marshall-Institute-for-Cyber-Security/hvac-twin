"""CracBangBangProgram's latch/hysteresis behavior, isolated from the
thermal physics -- drive the sensed-temperature tag directly and check the
control decision, the same way DigiTwin's own test_start_stop_tank.py tests
StartStopTankProgram."""

from __future__ import annotations

from digitwin import PLC_Generic, TagType

from hvac_twin.programs.crac_bang_bang import CracBangBangProgram


def _plc() -> PLC_Generic:
    plc = PLC_Generic("closet-plc", CracBangBangProgram())
    plc.define_tag("closet_temp_raw", TagType.ANALOG_INPUT, 0, "%IW0.0")
    plc.define_tag("setpoint_tenths", TagType.WORD, 750, "%MW0")
    plc.define_tag("deadband_tenths", TagType.WORD, 20, "%MW1")
    plc.define_tag("alarm_threshold_tenths", TagType.WORD, 950, "%MW2")
    plc.define_tag("cooling_on", TagType.INTERNAL_BIT, False, "%M0")
    plc.define_tag("high_temp_alarm", TagType.INTERNAL_BIT, False, "%M1")
    plc.define_tag("cooling_relay", TagType.DISCRETE_OUTPUT, False, "%Q0.0")
    return plc


def _set_temp(plc: PLC_Generic, tenths: int) -> None:
    plc.tags["closet_temp_raw"].value = tenths


def test_cooling_turns_on_past_setpoint_plus_deadband() -> None:
    plc = _plc()
    _set_temp(plc, 771)  # 77.1 F, > 750 + 20
    plc.scan()
    assert plc.read("cooling_on") is True
    assert plc.read("cooling_relay") is True


def test_cooling_turns_off_past_setpoint_minus_deadband() -> None:
    plc = _plc()
    _set_temp(plc, 771)
    plc.scan()  # turn on first
    _set_temp(plc, 729)  # 72.9 F, < 750 - 20
    plc.scan()
    assert plc.read("cooling_on") is False
    assert plc.read("cooling_relay") is False


def test_cooling_holds_state_inside_the_deadband() -> None:
    plc = _plc()
    _set_temp(plc, 771)
    plc.scan()  # cooling on
    _set_temp(plc, 750)  # right at setpoint, inside the deadband
    plc.scan()
    assert plc.read("cooling_on") is True  # holds, doesn't chatter


def test_high_temp_alarm_is_independent_of_cooling_state() -> None:
    plc = _plc()
    _set_temp(plc, 960)  # 96.0 F, past the 95.0 alarm threshold
    plc.scan()
    assert plc.read("high_temp_alarm") is True


def test_setpoint_is_a_plain_writable_tag() -> None:
    """The literal attack surface: writing this tag changes control
    behavior with no authentication -- exactly what Phase 3 will target."""
    plc = _plc()
    _set_temp(plc, 771)
    plc.write("setpoint_tenths", 900)  # spoof the setpoint way up
    plc.scan()
    assert plc.read("cooling_on") is False  # 77.1 F no longer looks "too hot"
