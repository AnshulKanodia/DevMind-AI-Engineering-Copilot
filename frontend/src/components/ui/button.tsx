import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?:
    | "default"
    | "secondary"
    | "outline"
    | "ghost"
    | "destructive"
    | "glow";
  size?: "default" | "sm" | "lg" | "icon";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer";

    const variantStyles: Record<string, string> = {
      default:
        "bg-sky-600 text-white shadow-sm hover:bg-sky-500 active:bg-sky-700",
      secondary:
        "bg-slate-800 text-slate-100 shadow-sm hover:bg-slate-700 active:bg-slate-800 border border-slate-700/60",
      outline:
        "border border-slate-700/80 bg-slate-900/40 text-slate-200 hover:bg-slate-800 hover:text-white active:bg-slate-800/80",
      ghost:
        "text-slate-300 hover:bg-slate-800/60 hover:text-white active:bg-slate-800",
      destructive:
        "bg-rose-600 text-white shadow-sm hover:bg-rose-500 active:bg-rose-700",
      glow:
        "bg-gradient-to-r from-sky-500 to-indigo-600 text-white shadow-lg shadow-sky-500/25 hover:from-sky-400 hover:to-indigo-500 active:scale-[0.98]",
    };

    const sizeStyles: Record<string, string> = {
      default: "h-9 px-4 py-2",
      sm: "h-8 rounded-md px-3 text-xs",
      lg: "h-10 rounded-lg px-6 text-base",
      icon: "h-9 w-9 p-0",
    };

    return (
      <button
        ref={ref}
        className={cn(
          baseStyles,
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
