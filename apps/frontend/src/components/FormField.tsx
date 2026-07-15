import type { InputHTMLAttributes } from "react";

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
}

export function FormField({ label, id, ...inputProps }: FormFieldProps) {
  return (
    <label htmlFor={id} className="block text-left">
      <span className="text-xs font-semibold uppercase tracking-[0.15em] text-ink-soft">
        {label}
      </span>
      <input
        id={id}
        {...inputProps}
        className="mt-2 w-full rounded-sm border border-paper-line bg-paper px-3.5 py-2.5 text-ink placeholder:text-ink-soft/50 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
      />
    </label>
  );
}
