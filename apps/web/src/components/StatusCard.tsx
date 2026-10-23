import type { LucideIcon } from "lucide-react";

type Props = { icon: LucideIcon; label: string; value: string; detail: string };

export function StatusCard({ icon: Icon, label, value, detail }: Props) {
  return (
    <article className="status-card">
      <div className="status-card__icon"><Icon size={20} aria-hidden="true" /></div>
      <div>
        <p className="eyebrow">{label}</p>
        <strong>{value}</strong>
        <p>{detail}</p>
      </div>
    </article>
  );
}

