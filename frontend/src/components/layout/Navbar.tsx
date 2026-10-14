"use client";

import React from "react";
import { 
  Cpu, 
  GitBranch, 
  FolderGit2, 
  Github, 
  CheckCircle2, 
  Layers,
  Sparkles
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dropdown } from "@/components/ui/dropdown";

export interface NavbarProps {
  currentRepo: string;
  currentBranch: string;
  availableBranches?: string[];
  onBranchChange: (branch: string) => void;
  onConnectRepoClick: () => void;
}

export function Navbar({
  currentRepo,
  currentBranch,
  availableBranches = ["main", "dev", "feat/phase8-ui-repo-onboarding"],
  onBranchChange,
  onConnectRepoClick,
}: NavbarProps) {
  const branchOptions = availableBranches.map((b) => ({
    value: b,
    label: b,
    icon: <GitBranch className="h-3 w-3 text-sky-400" />,
  }));

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="flex h-14 items-center justify-between px-4 md:px-6">
        {/* Brand & Repo Info */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-sky-500/20">
              <Cpu className="h-4 w-4" />
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="font-bold text-base tracking-tight text-white">DevMind</span>
              <span className="text-[10px] text-sky-400 font-mono font-medium px-1.5 py-0.2 rounded bg-sky-500/10 border border-sky-500/20">
                v0.1.0
              </span>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2 pl-4 border-l border-slate-800 text-xs">
            <button
              onClick={onConnectRepoClick}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-slate-900 border border-slate-800 text-slate-300 hover:border-slate-700 hover:text-white transition-colors"
              title="Change repository"
            >
              <FolderGit2 className="h-3.5 w-3.5 text-sky-400" />
              <span className="font-mono text-[11px] truncate max-w-[200px]">
                {currentRepo}
              </span>
            </button>

            <Dropdown
              options={branchOptions}
              value={currentBranch}
              onChange={onBranchChange}
              className="w-48"
              placeholder="Select branch"
            />
          </div>
        </div>

        {/* Global Controls & Status */}
        <div className="flex items-center gap-3">
          <Badge variant="success" className="hidden sm:inline-flex">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            LangGraph Core Active
          </Badge>

          <Button
            size="sm"
            variant="glow"
            onClick={onConnectRepoClick}
            className="text-xs flex items-center gap-1.5"
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Connect Repo</span>
          </Button>

          <a
            href="https://github.com/AnshulKanodia/DevMind-AI-Engineering-Copilot"
            target="_blank"
            rel="noreferrer"
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 transition-colors"
            title="View Source on GitHub"
          >
            <Github className="h-4 w-4" />
          </a>
        </div>
      </div>
    </header>
  );
}
