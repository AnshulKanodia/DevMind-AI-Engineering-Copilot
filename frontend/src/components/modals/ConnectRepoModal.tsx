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

export interface ConnectRepoModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRepoConnected: (repoUrl: string, branch: string) => void;
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
  const [connecting, setConnecting] = useState(false);
  const [step, setStep] = useState<"form" | "indexing" | "done">("form");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setConnecting(true);
    setStep("indexing");

    setTimeout(() => {
      setConnecting(false);
      setStep("done");
      setTimeout(() => {
        onRepoConnected(repoUrl, branch);
        onOpenChange(false);
        setStep("form");
      }, 1200);
    }, 1800);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogHeader>
        <div className="flex items-center gap-2 mb-1">
          <div className="h-8 w-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <FolderGit2 className="h-4 w-4" />
          </div>
          <DialogTitle>Connect GitHub Repository</DialogTitle>
        </div>
        <DialogDescription>
          DevMind will clone the repository into an isolated sandbox, filter source files, redact secrets, and generate AST vector embeddings.
        </DialogDescription>
      </DialogHeader>

      {step === "form" && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300">
              Repository URL
            </label>
            <Input
              type="url"
              required
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              className="text-xs font-mono"
            />
          </div>

          <div className="space-y-2">
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

          <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-400 space-y-1">
            <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Zero Leakage Sandbox Safeguards:</span>
            </div>
            <p>
              • Path-traversal blocked &bull; Storage quota 500MB &bull; Shannon entropy secrets redaction ($H &gt; 4.5$)
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

      {step === "indexing" && (
        <div className="py-8 flex flex-col items-center justify-center space-y-4 text-center">
          <div className="h-12 w-12 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400 animate-pulse">
            <Layers className="h-6 w-6 animate-spin" />
          </div>
          <div className="space-y-1">
            <h4 className="text-sm font-semibold text-white">
              Parsing AST & Creating Vector Embeddings
            </h4>
            <p className="text-xs text-slate-400">
              Preserving function/class syntax boundaries in MongoDB Atlas...
            </p>
          </div>
        </div>
      )}

      {step === "done" && (
        <div className="py-8 flex flex-col items-center justify-center space-y-3 text-center">
          <div className="h-12 w-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <h4 className="text-sm font-semibold text-emerald-400">
            Repository Successfully Indexed!
          </h4>
          <p className="text-xs text-slate-400">
            AST chunks ready for grounded Q&A and security reviews.
          </p>
        </div>
      )}
    </Dialog>
  );
}
