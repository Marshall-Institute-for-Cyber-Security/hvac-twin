"""Phase 0 checkpoint: this repo can import and run DigiTwin before any
HVAC-specific code exists. If this fails, the dependency wiring (not
anything HVAC-specific) is broken.

Builds a twin entirely from DigiTwin's public API rather than loading one of
its example project files: DigiTwin resolves as a git dependency now (see
pyproject.toml), and a git/wheel install carries the ``digitwin`` package,
not the sibling ``examples/`` directory an editable sibling checkout used to
expose. Reaching into another package's repo layout was always incidental to
what this test actually checks.
"""

from digitwin import PLC_Generic, TagType
from digitwin.executive import Executive
from digitwin.io import InProcessTransport, IOBus
from digitwin.plant import NullPlant


def test_can_import_and_run_a_digitwin_twin() -> None:
    def program(plc: PLC_Generic) -> None:
        plc.write_output("lamp", plc.read_input("button"))

    plc = PLC_Generic("smoke", program)
    plc.define_tag("button", TagType.DISCRETE_INPUT, False, "%I0.0")
    plc.define_tag("lamp", TagType.DISCRETE_OUTPUT, False, "%Q0.0")

    bus = IOBus()
    sim = Executive(plc=plc, plant=NullPlant(), bus=bus, transport=InProcessTransport(bus=bus))
    sim.run(10)
