export interface RoomDescriptor {
  id: string;
  label: string;
  description: string;
  href: string;
  defaultApiBase: string;
  watchTags: string[];
}

// The extensibility point for future twins: adding a room here (plus its
// own src/<room>/ folder and vite entry, same recipe as closet/office) is
// the whole change -- this list and the pages that read it (including the
// Defenses page's room picker) need no other edits.
export const ROOMS: RoomDescriptor[] = [
  {
    id: "closet",
    label: "Server Closet",
    description:
      "A single high-density server room on CRAC cooling, with continuous sensor and equipment telemetry.",
    href: "/closet.html",
    defaultApiBase: "http://127.0.0.1:8100",
    watchTags: ["setpoint_tenths"],
  },
  {
    id: "office",
    label: "Office Wing",
    description:
      "Three perimeter offices, each on its own independent heating zone and setpoint.",
    href: "/office.html",
    defaultApiBase: "http://127.0.0.1:8101",
    watchTags: ["room_1_setpoint_tenths", "room_2_setpoint_tenths", "room_3_setpoint_tenths"],
  },
];
