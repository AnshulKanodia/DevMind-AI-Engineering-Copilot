"use client";

import React from "react";
import {
  MessageSquareCode,
  FolderTree,
  ShieldAlert,
  FileCheck2,
  GitPullRequestDraft,
  Settings,
  ChevronLeft,
  ChevronRight,
  Database,
  Activity,
  Terminal,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip } from "@/components/ui/tooltip";

export type NavTabId =
  | "chat"
  | "repo"
  | "security"
  | "tests"
  | "pr_review"
  | "settings";

export interface SidebarProps {
  activeTab: NavTabId;
  onTabChange: (tab: NavTabId) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

export function Sidebar({
  activeTab,
  onTabChange,
  collapsed,
  onToggleCollapsed,
}: SidebarProps) {
  const navItems = [
    {
      id: "chat" as NavTabId,
      label: "Code Q&A Copilot",
      icon: MessageSquareCode,
      badge: "SSE Stream",
      description: "Natural language query with AST citations",
    },
    {
      id: "repo" as NavTabId,
      label: "Repository Ingestion",
      icon: FolderTree,
      badge: "AST + BM25",
      description: "Cloning, filtering, AST parser & indexer",
    },
    {
      id: "security" as NavTabId,
      label: "Security Audit & SAST",
      icon: ShieldAlert,
      badge: "OWASP",
      description: "Static analysis, Bandit, Semgrep & LLM verify",
    },
    {
      id: "tests" as NavTabId,
      label: "Test & Doc Synthesis",
      icon: FileCheck2,
      badge: "pytest / Jest",
      description: "Automated unit test mocks & documentation",
    },
    {
      id: "pr_review" as NavTabId,
      label: "PR Review & Autofix",
      icon: GitPullRequestDraft,
      badge: "Human-in-Loop",
      description: "Diff analysis, review verdicts & draft PRs",
    },
    {
      id: "settings" as NavTabId,
      label: "Environment & Keys",
      icon: Settings,
      description: "OpenAI, GitHub OAuth, MongoDB Atlas",
    },
  ];

  return (
    <aside
      className={cn(
        "relative flex flex-col border-r border-slate-800/80 bg-slate-950 transition-all duration-300 ease-in-out z-30",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Collapse Toggle Button */}
      <button
        onClick={onToggleCollapsed}
        className="absolute -right-3 top-5 z-40 flex h-6 w-6 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors shadow-md"
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? (
          <ChevronRight className="h-3.5 w-3.5" />
        ) : (
          <ChevronLeft className="h-3.5 w-3.5" />
        )}
      </button>

      {/* Navigation List */}
      <div className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        <div className={cn("px-2 mb-2", collapsed ? "hidden" : "block")}>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Workspaces
          </span>
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          const buttonContent = (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={cn(
                "flex items-center w-full rounded-lg text-left transition-all group relative",
                collapsed ? "justify-center p-2.5" : "px-3 py-2.5 gap-3",
                isActive
                  ? "bg-sky-500/10 text-sky-400 border border-sky-500/20 font-medium"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60"
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors",
                  isActive ? "text-sky-400" : "text-slate-400 group-hover:text-slate-200"
                )}
              />

              {!collapsed && (
                <div className="flex-1 min-w-0 flex items-center justify-between">
                  <span className="text-xs truncate">{item.label}</span>
                  {item.badge && (
                    <span
                      className={cn(
                        "text-[9px] px-1.5 py-0.5 rounded font-mono",
                        isActive
                          ? "bg-sky-500/20 text-sky-300"
                          : "bg-slate-900 text-slate-500 border border-slate-800"
                      )}
                    >
                      {item.badge}
                    </span>
                  )}
                </div>
              )}
            </button>
          );

          if (collapsed) {
            return (
              <Tooltip key={item.id} content={item.label} position="right">
                {buttonContent}
              </Tooltip>
            );
          }

          return buttonContent;
        })}
      </div>

      {/* System Telemetry Monitor */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-900/30">
        {!collapsed ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5">
                <Database className="h-3 w-3 text-emerald-400" />
                MongoDB Atlas
              </span>
              <span className="text-[10px] text-emerald-400 font-mono">Connected</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5">
                <Activity className="h-3 w-3 text-sky-400" />
                AST Nodes
              </span>
              <span className="text-[10px] font-mono text-slate-300">142 Indexed</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5">
                <Terminal className="h-3 w-3 text-purple-400" />
                FastAPI Host
              </span>
              <span className="text-[10px] font-mono text-slate-300">localhost:8000</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" title="System Connected" />
          </div>
        )}
      </div>
    </aside>
  );
}
