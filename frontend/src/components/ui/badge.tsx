import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?:
    | "default"
    | "secondary"
    | "outline"
    | "success"
    | "warning"
    | "destructive"
    | "glow";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const baseStyles =
    "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2";

  const variantStyles: Record<string, string> = {
    default:
      "border-transparent bg-sky-500/10 text-sky-400 border border-sky-500/20",
    secondary:
      "border-transparent bg-slate-800 text-slate-300 border border-slate-700/60",
    outline: "text-slate-300 border border-slate-700 bg-transparent",
    success:
      "border-emerald-500/20 bg-emerald-500/10 text-emerald-400 border",
    warning: "border-amber-500/20 bg-amber-500/10 text-amber-400 border",
    destructive: "border-rose-500/20 bg-rose-500/10 text-rose-400 border",
    glow: "bg-sky-500/20 text-sky-300 border border-sky-400/30 shadow-[0_0_12px_rgba(56,189,248,0.25)]",
  };

  return (
    <div
      className={cn(baseStyles, variantStyles[variant], className)}
      {...props}
    />
  );
}

export { Badge };
