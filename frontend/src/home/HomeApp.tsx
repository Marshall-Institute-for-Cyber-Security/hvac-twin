import { NavBar } from "../components/NavBar";
import { ROOMS } from "./rooms";

export default function HomeApp() {
  return (
    <div className="home-app">
      <NavBar />
      <header className="home-hero">
        <p className="home-hero__eyebrow">Building automation — facility overview</p>
        <h1 className="home-hero__title">Zones</h1>
        <p className="home-hero__desc">
          Live HVAC digital twins for two facility zones. Each one runs its own controller,
          sensors, and Modbus-connected equipment — pick a zone below to view its current
          state and adjust setpoints.
        </p>
      </header>
      <main className="home-grid">
        {ROOMS.map((room) => (
          <a key={room.id} className="room-card" href={room.href}>
            <h2 className="room-card__title">{room.label}</h2>
            <p className="room-card__desc">{room.description}</p>
            <span className="room-card__cta">Open zone →</span>
          </a>
        ))}
      </main>
      <section className="home-section">
        <h2 className="home-section__title">Research tools</h2>
      </section>
      <div className="home-grid home-grid--tools">
        <a className="room-card room-card--accent" href="/attack.html">
          <h2 className="room-card__title">Red Team Console</h2>
          <p className="room-card__desc">
            Run canned Modbus attack scenarios against a zone, or send raw commands from a
            terminal, to study how this system fails under attack.
          </p>
          <span className="room-card__cta">Open →</span>
        </a>
        <a className="room-card room-card--accent" href="/defenses.html">
          <h2 className="room-card__title">Defenses</h2>
          <p className="room-card__desc">
            See what mitigations exist, what each one actually catches, and turn them on for
            whichever zone you're defending.
          </p>
          <span className="room-card__cta">Open →</span>
        </a>
      </div>
    </div>
  );
}
