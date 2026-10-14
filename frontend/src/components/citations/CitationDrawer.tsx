"use client";

import React, { useEffect, useState } from "react";
import {
  X,
  FileCode,
  Copy,
  Check,
  ExternalLink,
  Layers,
  Database,
  Cpu,
  Sparkles,
  MessageSquare,
  Terminal,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getCitationData, CitationData } from "@/lib/citationSnippets";

export interface CitationDrawerProps {
  open: boolean;
  citation: { file: string; lines: string } | null;
  currentRepo?: string;
  currentBranch?: string;
  onClose: () => void;
  onAskCopilot?: (question: string) => void;
}

export function CitationDrawer({
  open,
  citation,
  currentRepo = "AnshulKanodia/DevMind-AI-Engineering-Copilot",
  currentBranch = "main",
  onClose,
  onAskCopilot,
}: CitationDrawerProps) {
  const [copied, setCopied] = useState(false);
  const [citationData, setCitationData] = useState<CitationData | null>(null);

  useEffect(() => {
    if (citation) {
      const data = getCitationData(citation.file, citation.lines);
      setCitationData(data);
    } else {
      setCitationData(null);
    }
  }, [citation]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open || !citationData) return null;

  const handleCopyCode = () => {
    navigator.clipboard.writeText(citationData.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleAsk = () => {
    onAskCopilot?.(
      `Explain how ${citationData.symbolName} in \`${citationData.file}:${citationData.lines}\` operates.`
    );
    onClose();
  };

  const githubUrl = `https://github.com/${currentRepo}/blob/${currentBranch}/${citationData.file}#L${citationData.lines.replace("-", "-L")}`;
  const codeLines = citationData.code.split("\n");

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity animate-in fade-in"
        onClick={onClose}
      />

      {/* Slide-out Drawer Panel */}
      <div className="fixed inset-y-0 right-0 z-50 flex max-w-full pl-10">
        <div className="w-screen max-w-xl md:max-w-2xl bg-slate-950 border-l border-slate-800 shadow-2xl flex flex-col h-full animate-in slide-in-from-right duration-300">
          {/* Header Bar */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-slate-900/70">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="h-8 w-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
                <FileCode className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-xs md:text-sm font-bold text-white font-mono truncate">
                    {citationData.file}
                  </h3>
                  <Badge variant="glow" className="text-[10px] shrink-0 font-mono">
                    L{citationData.lines}
                  </Badge>
                </div>
                <span className="text-[10px] text-slate-400 font-mono block truncate">
                  AST Symbol: <span className="text-sky-300 font-semibold">{citationData.symbolName}</span> ({citationData.nodeType})
                </span>
              </div>
            </div>

            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors ml-3"
              title="Close drawer (Esc)"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Retrieval Telemetry Bar */}
          <div className="grid grid-cols-3 gap-2 px-5 py-3 border-b border-slate-800/80 bg-slate-950/80 text-[11px]">
            <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 space-y-0.5">
              <span className="text-slate-500 text-[10px] uppercase font-semibold">Dense Vector</span>
              <div className="font-mono text-sky-400 font-bold">
                {(citationData.denseScore * 100).toFixed(1)}% match
              </div>
            </div>
            <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 space-y-0.5">
              <span className="text-slate-500 text-[10px] uppercase font-semibold">BM25 Okapi</span>
              <div className="font-mono text-emerald-400 font-bold">
                {citationData.bm25Score.toFixed(1)} score
              </div>
            </div>
            <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 space-y-0.5">
              <span className="text-slate-500 text-[10px] uppercase font-semibold">RRF Combined</span>
              <div className="font-mono text-purple-400 font-bold">
                {(citationData.combinedScore * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Code Viewer Viewport */}
          <div className="flex-1 overflow-y-auto p-4 bg-[#060911]">
            <div className="rounded-xl border border-slate-800 bg-slate-950/90 overflow-hidden shadow-inner">
              <div className="flex items-center justify-between px-3.5 py-2 border-b border-slate-800 bg-slate-900/70 text-[11px] text-slate-400">
                <span className="font-mono uppercase text-sky-400 font-medium">
                  {citationData.language} &bull; Syntax-Aware AST Chunk
                </span>
                <button
                  onClick={handleCopyCode}
                  className="flex items-center gap-1 text-slate-400 hover:text-white transition-colors"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>

              <div className="p-3 overflow-x-auto text-xs font-mono leading-relaxed">
                <table className="w-full border-collapse">
                  <tbody>
                    {codeLines.map((line, i) => {
                      const isHighlighted = i >= 0 && i < 15;
                      return (
                        <tr
                          key={i}
                          className={
                            isHighlighted
                              ? "bg-sky-500/10 hover:bg-sky-500/15 transition-colors border-l-2 border-sky-400"
                              : "hover:bg-slate-900/40"
                          }
                        >
                          <td className="pr-4 text-right text-slate-600 select-none w-10 text-[11px] align-top pl-2">
                            {i + 1}
                          </td>
                          <td className="text-slate-200 whitespace-pre font-mono">
                            {line}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Action Footer */}
          <div className="p-4 border-t border-slate-800 bg-slate-900/60 flex flex-wrap items-center justify-between gap-3">
            <a
              href={githubUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white hover:underline transition-colors"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              <span>View file on GitHub</span>
            </a>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopyCode}
                className="text-xs"
              >
                {copied ? "Copied Snippet" : "Copy Snippet"}
              </Button>

              {onAskCopilot && (
                <Button
                  variant="glow"
                  size="sm"
                  onClick={handleAsk}
                  className="text-xs flex items-center gap-1.5"
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  <span>Ask Copilot</span>
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
