import { StatusBadge } from "./StatusBadge";

type ModuleCardProps = {
  name: string;
  title: string;
  status: string;
  description: string;
  active?: boolean;
};

export function ModuleCard({
  name,
  title,
  status,
  description,
  active = false,
}: ModuleCardProps) {
  return (
    <article className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-[var(--color-primary-border)] hover:bg-[var(--color-hover)] hover:shadow-xl hover:shadow-[var(--color-card-shadow)]">
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-[var(--color-text-weak)]">{name}</span>
        <StatusBadge status={status} active={active} />
      </div>

      <h3 className="font-semibold text-[var(--color-text)]">{title}</h3>

      <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">
        {description}
      </p>
    </article>
  );
}