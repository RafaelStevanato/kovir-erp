import { CheckCircle2 } from "lucide-react";

type StatusItemProps = {
  label: string;
};

export function StatusItem({ label }: StatusItemProps) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 transition-all duration-200 hover:border-[var(--color-primary-border)] hover:bg-[var(--color-hover)] hover:shadow-lg hover:shadow-[var(--color-card-shadow)]">
      <span className="text-sm text-[var(--color-text)]">{label}</span>

      <span className="flex items-center gap-2 text-sm text-[var(--color-primary)]">
        <CheckCircle2 className="h-4 w-4" />
        ativo
      </span>
    </div>
  );
}