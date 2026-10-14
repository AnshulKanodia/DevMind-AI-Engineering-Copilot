"use client";

import React, { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Sparkles,
  Search,
  Database,
  Brain,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { AgentThought } from "@/lib/chatStream";

export interface AgentThoughtTimelineProps {
  thoughts: AgentThought[];
  isStreaming?: boolean;
}

export function AgentThoughtTimeline({
  thoughts,
  isStreaming,
}: AgentThoughtTimelineProps) {
  const [expanded, setExpanded] = useState(true);

  if (thoughts.length === 0) return null;

  const getIcon = (node: string) => {
    switch (node) {
      case "router":
        return <Brain className="h-3.5 w-3.5 text-indigo-400" />;
      case "retriever":
        return <Database className="h-3.5 w-3.5 text-sky-400" />;
      case "synthesizer":
        return <Sparkles className="h-3.5 w-3.5 text-purple-400" />;
      default:
        return <Search className="h-3.5 w-3.5 text-slate-400" />;
    }
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/70 overflow-hidden mb-3 text-xs">
      {/* Header bar */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full px-3 py-2 bg-slate-900/60 hover:bg-slate-900 transition-colors text-slate-400 hover:text-slate-200"
      >
        <div className="flex items-center gap-2">
          {isStreaming ? (
            <Loader2 className="h-3.5 w-3.5 text-sky-400 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5 text-purple-400" />
          )}
          <span className="font-semibold text-slate-300">
            Multi-Agent Reasoning Chain ({thoughts.length} steps)
          </span>
        </div>
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
        )}
      </button>

      {/* Steps List */}
      {expanded && (
        <div className="p-3 space-y-2 border-t border-slate-800/80 divide-y divide-slate-800/40">
          {thoughts.map((thought, idx) => (
            <div key={idx} className="flex items-start gap-2.5 pt-2 first:pt-0">
              <div className="mt-0.5 shrink-0">{getIcon(thought.node)}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px] text-slate-300 uppercase tracking-wider">
                    {thought.node} agent
                  </span>
                  {thought.status === "completed" ? (
                    <CheckCircle2 className="h-3 w-3 text-emerald-400 shrink-0" />
                  ) : (
                    <div className="h-3 w-3 rounded-full border border-sky-400 border-t-transparent animate-spin shrink-0" />
                  )}
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">
                  {thought.message}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
