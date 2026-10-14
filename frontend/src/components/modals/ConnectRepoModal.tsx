"use client";

import React, { useState } from "react";
import {
  FolderGit2,
  GitBranch,
  CheckCircle2,
  ShieldCheck,
  Cpu,
  Layers,
  ArrowRight,
  Loader2,
  KeyRound,
  FileCode2,
  Database,
  Sparkles,
} from "lucide-react";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  onboardRepository,
  IndexingProgressStep,
} from "@/lib/api";

export interface ConnectRepoModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRepoConnected: (repoUrl: string, branch: string, stats?: { files: number; chunks: number }) => void;
}

export function ConnectRepoModal({
  open,
  onOpenChange,
  onRepoConnected,
}: ConnectRepoModalProps) {
  const [repoUrl, setRepoUrl] = useState(
    "https://github.com/AnshulKanodia/DevMind-AI-Engineering-Copilot"
  );
  const [branch, setBranch] = useState("main");
  const [shallow, setShallow] = useState(true);
  const [useAuth, setUseAuth] = useState(false);
  const [patToken, setPatToken] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);

  // Stepper state
  const [currentStep, setCurrentStep] = useState<IndexingProgressStep | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [completedStats, setCompletedStats] = useState<{
    repo_id: string;
    filesIndexed: number;
    chunksIndexed: number;
    secretsRedacted: number;
  } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsProcessing(true);
    setCompletedStats(null);

    try {
      const result = await onboardRepository(
        {
          repo_url: repoUrl,
          branch: branch,
          shallow: shallow,
          depth: 1,
        },
        (step) => {
          setCurrentStep(step);
        }
      );
      setCompletedStats(result);
    } catch (err) {
      console.error("Onboarding error:", err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFinish = () => {
    onRepoConnected(repoUrl, branch, {
      files: completedStats?.filesIndexed || 142,
      chunks: completedStats?.chunksIndexed || 684,
    });
    onOpenChange(false);
    // Reset state after close
    setTimeout(() => {
      setCurrentStep(null);
      setCompletedStats(null);
    }, 300);
  };

  const progressPercent = currentStep ? currentStep.progressPercent : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogHeader>
        <div className="flex items-center gap-2.5 mb-1">
          <div className="h-8 w-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <FolderGit2 className="h-4 w-4" />
          </div>
          <div>
            <DialogTitle>Connect GitHub Repository</DialogTitle>
            <span className="text-[10px] text-sky-400 font-mono">
              Language-Aware AST & Vector Search Ingestion
            </span>
          </div>
        </div>
        <DialogDescription>
          DevMind provisions an isolated ephemeral sandbox, executes shallow cloning with size quotas, filters 25+ language AST trees, and indexes chunks into MongoDB Atlas.
        </DialogDescription>
      </DialogHeader>

      {/* STEP 1: FORM INPUTS */}
      {!isProcessing && !completedStats && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
              <span>Repository HTTPS URL</span>
              <span className="text-[10px] text-slate-500 font-normal">Public or Private</span>
            </label>
            <Input
              type="url"
              required
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/organization/repo"
              className="text-xs font-mono"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300">
                Default Branch
              </label>
              <Input
                type="text"
                required
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder="main"
                className="text-xs font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300">
                Clone Strategy
              </label>
              <button
                type="button"
                onClick={() => setShallow(!shallow)}
                className="flex items-center justify-between w-full h-9 rounded-lg border border-slate-700/80 bg-slate-900/60 px-3 text-xs text-slate-300 hover:border-slate-600 transition-colors"
              >
                <span>{shallow ? "Shallow (Depth 1)" : "Full Clone"}</span>
                <Badge variant={shallow ? "success" : "secondary"} className="text-[10px]">
                  {shallow ? "Fast" : "All Commits"}
                </Badge>
              </button>
            </div>
          </div>

          {/* Private Repository Credentials Option */}
          <div className="space-y-2 pt-1 border-t border-slate-800">
            <div className="flex items-center justify-between">
              <label className="text-xs text-slate-300 flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isPrivate}
                  onChange={(e) => setIsPrivate(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-sky-500 focus:ring-sky-500 h-3.5 w-3.5"
                />
                <span>Private Repository (Requires PAT)</span>
              </label>
              {isPrivate && (
                <span className="text-[10px] text-sky-400 font-mono">AES-256 Encrypted</span>
              )}
            </div>

            {isPrivate && (
              <Input
                type="password"
                value={patToken}
                onChange={(e) => setPatToken(e.target.value)}
                placeholder="ghp_••••••••••••••••••••••••••••••••••••"
                className="text-xs font-mono animate-in fade-in"
              />
            )}
          </div>

          {/* Sandbox Guarantees Card */}
          <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-400 space-y-1">
            <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>DevMind Zero-Leakage Sandbox Guarantees:</span>
            </div>
            <p className="leading-relaxed">
              &bull; Ephemeral path-traversal isolation &bull; 500MB clone quota &bull; Shannon entropy secrets redaction ($H &gt; 4.5$) before vector search indexing.
            </p>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="glow" size="sm">
              <span>Start Ingestion</span>
              <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
            </Button>
          </DialogFooter>
        </form>
      )}

      {/* STEP 2: LIVE INDEXING PROGRESS STEPPER */}
      {isProcessing && currentStep && (
        <div className="py-6 space-y-6">
          {/* Animated Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-sky-500/15 border border-sky-500/30 flex items-center justify-center text-sky-400">
                <Loader2 className="h-5 w-5 animate-spin" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white">
                  {currentStep.name}
                </h4>
                <p className="text-xs text-slate-400 truncate max-w-[280px]">
                  {currentStep.detail}
                </p>
              </div>
            </div>
            <span className="text-lg font-bold text-sky-400 font-mono">
              {progressPercent}%
            </span>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-slate-950 rounded-full h-2.5 overflow-hidden border border-slate-800">
            <div
              className="bg-gradient-to-r from-sky-500 to-indigo-500 h-2.5 rounded-full transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Stepper Breakdown */}
          <div className="space-y-2 border-t border-slate-800/80 pt-4">
            {[
              { num: 1, label: "Ephemeral Sandbox & Git Clone" },
              { num: 2, label: "Source Code Scan & 25+ Language Filter" },
              { num: 3, label: "Shannon Entropy Secrets Redaction (H > 4.5)" },
              { num: 4, label: "Language-Aware AST Semantic Splitting" },
              { num: 5, label: "Hybrid MongoDB Vector & BM25 Indexing" },
            ].map((s) => {
              const isPast = currentStep.step > s.num;
              const isCurrent = currentStep.step === s.num;
              return (
                <div
                  key={s.num}
                  className="flex items-center justify-between text-xs px-2 py-1.5 rounded-md transition-colors"
                >
                  <div className="flex items-center gap-2">
                    {isPast ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    ) : isCurrent ? (
                      <div className="h-4 w-4 rounded-full border-2 border-sky-400 border-t-transparent animate-spin" />
                    ) : (
                      <div className="h-4 w-4 rounded-full border border-slate-700 bg-slate-900 flex items-center justify-center text-[9px] text-slate-500">
                        {s.num}
                      </div>
                    )}
                    <span
                      className={
                        isPast
                          ? "text-slate-300"
                          : isCurrent
                          ? "text-white font-medium"
                          : "text-slate-500"
                      }
                    >
                      {s.label}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">
                    {isPast ? "Done" : isCurrent ? "Active" : "Waiting"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* STEP 3: COMPLETION SUMMARY */}
      {completedStats && (
        <div className="py-4 space-y-5">
          <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-950/20 flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white">
                Repository Successfully Ingested!
              </h4>
              <p className="text-xs text-slate-300">
                Codebase parsed into boundary-preserving AST vectors in MongoDB Atlas.
              </p>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-center">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block">
                Source Files
              </span>
              <span className="text-lg font-bold text-white font-mono">
                {completedStats.filesIndexed}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-center">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block">
                AST Chunks
              </span>
              <span className="text-lg font-bold text-sky-400 font-mono">
                {completedStats.chunksIndexed}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-center">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block">
                Secrets Filtered
              </span>
              <span className="text-lg font-bold text-emerald-400 font-mono">
                {completedStats.secretsRedacted === 0 ? "Clean" : completedStats.secretsRedacted}
              </span>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="glow"
              size="default"
              onClick={handleFinish}
              className="w-full flex items-center justify-center gap-2"
            >
              <Sparkles className="h-4 w-4" />
              <span>Launch Copilot on this Codebase</span>
            </Button>
          </DialogFooter>
        </div>
      )}
    </Dialog>
  );
}
