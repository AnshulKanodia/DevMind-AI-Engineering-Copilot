"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DropdownOption {
  value: string;
  label: string;
  icon?: React.ReactNode;
  badge?: string;
}

export interface DropdownProps {
  options: DropdownOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export function Dropdown({
  options,
  value,
  onChange,
  placeholder = "Select option...",
  className,
}: DropdownProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.value === value);

  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className={cn("relative inline-block text-left", className)}>
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center justify-between w-full h-9 rounded-lg border border-slate-700/80 bg-slate-900/60 px-3 py-1.5 text-xs md:text-sm text-slate-200 hover:border-slate-600 focus:outline-none focus:ring-1 focus:ring-sky-500 transition-colors"
      >
        <span className="flex items-center gap-2 truncate">
          {selectedOption?.icon}
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-slate-400 ml-2" />
      </button>

      {isOpen && (
        <div className="absolute left-0 mt-1.5 w-full min-w-[160px] rounded-lg border border-slate-700 bg-slate-900 shadow-xl z-50 py-1 overflow-hidden animate-in fade-in zoom-in-95">
          {options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                onChange(opt.value);
                setIsOpen(false);
              }}
              className={cn(
                "flex items-center justify-between w-full px-3 py-2 text-xs md:text-sm text-left hover:bg-slate-800 transition-colors",
                opt.value === value ? "text-sky-400 bg-slate-800/60 font-medium" : "text-slate-300"
              )}
            >
              <span className="flex items-center gap-2 truncate">
                {opt.icon}
                {opt.label}
              </span>
              {opt.badge && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                  {opt.badge}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
