import type { ReactNode } from "react";

export function Kpi({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {note && <div className="kpi-note">{note}</div>}
    </div>
  );
}

export function Card({ title, caption, children }: { title: string; caption?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {caption && <p className="caption">{caption}</p>}
      {children}
    </section>
  );
}

export function Status({ loading, error }: { loading: boolean; error: unknown }) {
  if (error) return <p className="error" role="alert">Could not load this section. {String(error)}</p>;
  if (loading) return <p className="muted">Loading</p>;
  return null;
}
