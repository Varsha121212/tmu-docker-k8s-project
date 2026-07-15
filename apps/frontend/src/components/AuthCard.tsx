import type { ReactNode } from "react";

export function AuthCard({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="w-full max-w-sm animate-[rise_0.5s_ease-out]">
      <div className="relative rounded-md border border-paper-line bg-paper-dim px-8 py-9 shadow-[0_1px_2px_rgb(36_31_28_/_0.06),0_18px_36px_-24px_rgb(36_31_28_/_0.45)]">
        <div className="absolute inset-x-0 top-0 h-1 rounded-t-md bg-gradient-to-r from-accent via-primary to-accent" />
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-accent">{eyebrow}</p>
        <h1 className="mt-2 text-3xl text-ink">{title}</h1>
        <div className="mt-7 flex flex-col gap-5">{children}</div>
      </div>
    </div>
  );
}
