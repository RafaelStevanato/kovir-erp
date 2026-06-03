type StatusBadgeProps = {
  status: string;
  active?: boolean;
};

export function StatusBadge({ status, active = false }: StatusBadgeProps) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs ${
        active
          ? "border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
          : "bg-[var(--color-surface-elevated)] text-[var(--color-text-weak)]"
      }`}
    >
      {status}
    </span>
  );
}