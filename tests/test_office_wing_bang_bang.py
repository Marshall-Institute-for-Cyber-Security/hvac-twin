"""OfficeWingBangBangProgram's latch/hysteresis behavior for each zone,
isolated from the thermal physics -- same style as test_crac_bang_bang.py,
but heating-direction (inverted vs. the closet's cooling logic) and
checked across zones to prove the PLC scan keeps them independent."""

from __future__ import annotations

from digitwin import PLC_Generic, TagType

from hvac_twin.programs.office_wing_bang_bang import OfficeWingBangBangProgram

# zone -> (io channel, %MW base, %M base)
_ZONE_ADDRESSES = {
    "room_1": (0, 0, 0),
    "room_2": (1, 3, 2),
    "room_3": (2, 6, 4),
}


def _plc() -> PLC_Generic:
    plc = PLC_Generic("office-wing-plc", OfficeWingBangBangProgram())
    for zone, (io_n, mw_base, m_base) in _ZONE_ADDRESSES.items():
        plc.define_tag(f"{zone}_temp_raw", TagType.ANALOG_INPUT, 0, f"%IW0.{io_n}")
        plc.define_tag(f"{zone}_setpoint_tenths", TagType.WORD, 720, f"%MW{mw_base}")
        plc.define_tag(f"{zone}_deadband_tenths", TagType.WORD, 20, f"%MW{mw_base + 1}")
        plc.define_tag(
            f"{zone}_freeze_threshold_tenths", TagType.WORD, 500, f"%MW{mw_base + 2}"
        )
        plc.define_tag(f"{zone}_heating_on", TagType.INTERNAL_BIT, False, f"%M{m_base}")
        plc.define_tag(
            f"{zone}_freeze_alarm", TagType.INTERNAL_BIT, False, f"%M{m_base + 1}"
        )
        plc.define_tag(
            f"{zone}_heating_relay", TagType.DISCRETE_OUTPUT, False, f"%Q0.{io_n}"
        )
    return plc


def _set_temp(plc: PLC_Generic, zone: str, tenths: int) -> None:
    plc.tags[f"{zone}_temp_raw"].value = tenths


def test_heating_turns_on_past_setpoint_minus_deadband() -> None:
    plc = _plc()
    _set_temp(plc, "room_1", 690)  # 69.0 F, < 720 - 20
    plc.scan()
    assert plc.read("room_1_heating_on") is True
    assert plc.read("room_1_heating_relay") is True


def test_heating_turns_off_past_setpoint_plus_deadband() -> None:
    plc = _plc()
    _set_temp(plc, "room_1", 690)
    plc.scan()  # turn on first
    _set_temp(plc, "room_1", 745)  # 74.5 F, > 720 + 20
    plc.scan()
    assert plc.read("room_1_heating_on") is False
    assert plc.read("room_1_heating_relay") is False


def test_heating_holds_state_inside_the_deadband() -> None:
    plc = _plc()
    _set_temp(plc, "room_1", 690)
    plc.scan()  # heating on
    _set_temp(plc, "room_1", 720)  # right at setpoint, inside the deadband
    plc.scan()
    assert plc.read("room_1_heating_on") is True  # holds, doesn't chatter


def test_freeze_alarm_is_independent_of_heating_state() -> None:
    plc = _plc()
    _set_temp(plc, "room_1", 480)  # 48.0 F, past the 50.0 freeze threshold
    plc.scan()
    assert plc.read("room_1_freeze_alarm") is True


def test_zones_are_controlled_independently() -> None:
    plc = _plc()
    _set_temp(plc, "room_1", 690)  # room_1 needs heat
    _set_temp(plc, "room_2", 720)  # room_2 already at setpoint
    _set_temp(plc, "room_3", 745)  # room_3 too warm
    plc.scan()
    assert plc.read("room_1_heating_on") is True
    assert plc.read("room_2_heating_on") is False
    assert plc.read("room_3_heating_on") is False


def test_setpoint_is_a_plain_writable_tag() -> None:
    """Same attack surface as the closet: writing this tag changes control
    behavior with no authentication."""
    plc = _plc()
    _set_temp(plc, "room_1", 690)
    plc.write("room_1_setpoint_tenths", 600)  # spoof the setpoint way down
    plc.scan()
    assert plc.read("room_1_heating_on") is False  # 69.0 F no longer looks "too cold"
