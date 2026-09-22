import type { EventOut } from "../api";

interface EventLogProps {
  events: EventOut[];
}

export function EventLog({ events }: EventLogProps) {
  const ordered = [...events].reverse();
  return (
    <section className="panel panel--events">
      <h2 className="panel__title">Event Log</h2>
      {ordered.length === 0 ? (
        <p className="event-log__empty">No events recorded.</p>
      ) : (
        <ul className="event-log">
          {ordered.map((event, index) => (
            <li className={`event-log__row event-log__row--${event.severity}`} key={index}>
              <span className="event-log__time">T+{event.timestamp.toFixed(0)}s</span>
              <span className="event-log__category">[{event.category.toUpperCase()}]</span>
              <span className="event-log__message">{event.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
