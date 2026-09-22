import type { TagPrimitive } from "../api";

interface TagRow {
  label: string;
  key: string;
  format?: (value: TagPrimitive | undefined) => string;
}

interface TagPanelProps {
  title: string;
  tags: Record<string, TagPrimitive>;
  rows: TagRow[];
}

const defaultFormat = (value: TagPrimitive | undefined): string => {
  if (value === undefined) return "--";
  if (typeof value === "boolean") return value ? "ON" : "OFF";
  return String(value);
};

export function TagPanel({ title, tags, rows }: TagPanelProps) {
  return (
    <section className="panel">
      <h2 className="panel__title">{title}</h2>
      <dl className="tag-panel">
        {rows.map((row) => (
          <div className="tag-panel__row" key={row.key}>
            <dt className="tag-panel__label">{row.label}</dt>
            <dd className="tag-panel__value">{(row.format ?? defaultFormat)(tags[row.key])}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
