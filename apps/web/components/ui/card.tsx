import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-border bg-card shadow-sm", className)} {...props} />;
}

export function Badge({
  className,
  tone = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: "default" | "demo" | "success" | "muted" | "warning" }) {
  const tones = {
    default: "bg-primary/10 text-primary",
    demo: "bg-amber-100 text-amber-900 ring-1 ring-amber-300",
    success: "bg-emerald-100 text-emerald-900",
    muted: "bg-muted text-muted-foreground",
    warning: "bg-orange-100 text-orange-900",
  };
  return (
    <span
      className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold", tones[tone], className)}
      {...props}
    />
  );
}

export function Alert({
  className,
  tone = "info",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { tone?: "info" | "error" | "success" | "warning" }) {
  const tones = {
    info: "bg-sky-50 text-sky-900 border-sky-200",
    error: "bg-red-50 text-red-900 border-red-200",
    success: "bg-emerald-50 text-emerald-900 border-emerald-200",
    warning: "bg-amber-50 text-amber-900 border-amber-200",
  };
  return <div role="status" className={cn("rounded-lg border px-4 py-3 text-sm", tones[tone], className)} {...props} />;
}
