"use client";

import React, { useState } from "react";
import {
  GitPullRequestDraft,
  GitCommit,
  CheckCircle,
  AlertCircle,
  ShieldAlert,
  GitMerge,
  KeyRound,
  FileDiff,
  ArrowRight,
  ExternalLink,
  Sparkles,
  GitBranch,
  ShieldCheck,
  Check,
  Wrench,
  Loader2,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface DiffLine {
  type: "context" | "add" | "del";
  oldLine?: number;
  newLine?: number;
  content: string;
}

export function PRReviewView() {
  const [prNumber, setPrNumber] = useState("42");
  const [selectedFile, setSelectedFile] = useState("backend/app/services/github_client.py");
  const [isApproved, setIsApproved] = useState(false);
  const [isApplyingAutofix, setIsApplyingAutofix] = useState(false);
  const [autofixBranch, setAutofixBranch] = useState<string | null>(null);

  const sampleToken = "devmind-appr-9a4f2e18d6c7b3";
  const checkpointId = "checkpoint-8f2a";

  const diffFiles = [
    { name: "backend/app/services/github_client.py", additions: 45, deletions: 8 },
    { name: "backend/app/services/approval_service.py", additions: 88, deletions: 2 },
    { name: "backend/app/api/v1/endpoints/approvals.py", additions: 32, deletions: 0 },
  ];

  const sampleDiffLines: Record<string, DiffLine[]> = {
    "backend/app/services/github_client.py": [
      { type: "context", oldLine: 40, newLine: 40, content: "    async def get_pr_diff(self, owner: str, repo: str, pull_number: int) -> str:" },
      { type: "context", oldLine: 41, newLine: 41, content: "        headers = await self._get_auth_headers()" },
      { type: "del", oldLine: 42, content: "-        response = await httpx.get(url, headers=headers)" },
      { type: "del", oldLine: 43, content: "-        return response.text" },
      { type: "add", newLine: 42, content: "+        # Enforce application/vnd.github.v3.diff header & timeout" },
      { type: "add", newLine: 43, content: "+        headers['Accept'] = 'application/vnd.github.v3.diff'" },
      { type: "add", newLine: 44, content: "+        async with httpx.AsyncClient(timeout=15.0) as client:" },
      { type: "add", newLine: 45, content: "+            response = await client.get(url, headers=headers)" },
      { type: "add", newLine: 46, content: "+            if response.status_code != 200:" },
      { type: "add", newLine: 47, content: "+                raise GitHubAPIError(f'Failed to fetch PR diff: {response.status_code}')" },
      { type: "add", newLine: 48, content: "+            return response.text" },
      { type: "context", oldLine: 44, newLine: 49, content: " " },
      { type: "context", oldLine: 45, newLine: 50, content: "    async def post_review_comment(self, owner: str, ...):" },
    ],
    "backend/app/services/approval_service.py": [
      { type: "context", oldLine: 15, newLine: 15, content: "class HumanInTheLoopApprovalService:" },
      { type: "add", newLine: 16, content: "+    def generate_approval_token(self, checkpoint_id: str) -> str:" },
      { type: "add", newLine: 17, content: "+        \"\"\"Generates HMAC-SHA256 signature for Human-in-the-Loop gates.\"\"\"" },
      { type: "add", newLine: 18, content: "+        sig = hmac.new(self.secret_key.encode(), checkpoint_id.encode(), hashlib.sha256).hexdigest()[:14]" },
      { type: "add", newLine: 19, content: "+        return f'devmind-appr-{sig}'" },
    ],
  };

  const currentDiff = sampleDiffLines[selectedFile] || sampleDiffLines["backend/app/services/github_client.py"];

  const handleApproveAndAutofix = () => {
    setIsApplyingAutofix(true);
    setTimeout(() => {
      setIsApproved(true);
      setIsApplyingAutofix(false);
      setAutofixBranch(`devmind/autofix-pr-${prNumber}`);
    }, 1200);
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <GitPullRequestDraft className="h-5 w-5 text-amber-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              PR Review & Safe Autofix Hub
            </h2>
            <Badge variant="glow" className="text-[10px]">
              Human-in-the-Loop Enforced
            </Badge>
          </div>
          <p className="text-xs text-slate-400">
            Reviews GitHub PR diffs, highlights breaking regressions, and executes cryptographic autofixes with zero unverified mutations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={isApproved ? "success" : "warning"} className="text-xs py-1">
            {isApproved ? "Autofix Signed & Merged" : "Approval Gate Pending"}
          </Badge>
        </div>
      </div>

      {/* PR Diff Overview Card */}
      <Card>
        <CardContent className="p-5 space-y-5">
          {/* PR Title and Branch Metadata */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2.5">
              <span className="text-sm font-bold text-white">
                PR #{prNumber}: Add AES-256 Token Decryption & AST Ingestion
              </span>
              <Badge variant="warning" className="text-[10px]">
                Review Verdict: COMMENT
              </Badge>
            </div>
            <div className="text-xs text-slate-400 font-mono flex items-center gap-1.5">
              <GitBranch className="h-3.5 w-3.5 text-sky-400" />
              <span className="text-sky-300">feat/ast-ingest</span> ➔{" "}
              <span className="text-indigo-300">main</span>
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-slate-400 text-[10px] uppercase font-semibold">Diff Size</span>
              <div className="font-semibold text-slate-200 font-mono">
                3 files (+165 lines, -10 lines)
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-slate-400 text-[10px] uppercase font-semibold">Security Gate</span>
              <div className="font-semibold text-emerald-400 flex items-center gap-1 font-mono">
                <CheckCircle className="h-3.5 w-3.5" /> 0 Secrets Leaked
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-slate-400 text-[10px] uppercase font-semibold">Static Defect Gate</span>
              <div className="font-semibold text-amber-400 font-mono">
                1 Inline Recommendation
              </div>
            </div>
          </div>

          {/* Inline Agent Recommendation */}
          <div className="rounded-xl border border-amber-500/30 bg-amber-950/15 p-4 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono text-amber-300 font-semibold flex items-center gap-1.5">
                <FileDiff className="h-4 w-4" />
                backend/app/services/github_client.py:47
              </span>
              <Badge variant="warning" className="text-[10px]">
                Agent Suggestion
              </Badge>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              &quot;Consider raising a typed <code>GitHubAPIError</code> instead of returning raw error responses so callers can differentiate rate-limits from auth failures.&quot;
            </p>
          </div>

          {/* File Selector Tabs */}
          <div className="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
            {diffFiles.map((file) => (
              <button
                key={file.name}
                onClick={() => setSelectedFile(file.name)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono transition-colors whitespace-nowrap ${
                  selectedFile === file.name
                    ? "bg-sky-500/10 text-sky-400 border border-sky-500/30 font-semibold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <span>{file.name.split("/").pop()}</span>
                <span className="text-[10px] text-emerald-400">+{file.additions}</span>
                <span className="text-[10px] text-rose-400">-{file.deletions}</span>
              </button>
            ))}
          </div>

          {/* Diff Viewer */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden font-mono text-xs shadow-inner">
            <div className="px-4 py-2 bg-slate-900 border-b border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
              <span>{selectedFile}</span>
              <span className="text-slate-500">Unified Diff View</span>
            </div>

            <div className="overflow-x-auto p-3 space-y-0.5">
              {currentDiff.map((line, idx) => {
                const isAdd = line.type === "add";
                const isDel = line.type === "del";

                return (
                  <div
                    key={idx}
                    className={`flex items-start px-2 py-0.5 rounded leading-relaxed ${
                      isAdd
                        ? "bg-emerald-500/15 text-emerald-300"
                        : isDel
                        ? "bg-rose-500/15 text-rose-300"
                        : "text-slate-400 hover:bg-slate-900/50"
                    }`}
                  >
                    <div className="w-8 text-right pr-2 text-slate-600 select-none text-[11px]">
                      {line.oldLine || ""}
                    </div>
                    <div className="w-8 text-right pr-3 text-slate-600 select-none text-[11px]">
                      {line.newLine || ""}
                    </div>
                    <div className="w-4 select-none text-slate-500 font-bold">
                      {isAdd ? "+" : isDel ? "-" : " "}
                    </div>
                    <div className="flex-1 whitespace-pre font-mono">
                      {line.content.replace(/^[+-]/, "")}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Cryptographic Human-in-the-Loop Approval Gate */}
          <div className="p-5 rounded-2xl border border-sky-500/30 bg-gradient-to-r from-slate-950 via-sky-950/20 to-slate-950 space-y-3.5 shadow-lg">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-sky-400" />
                <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                  Human-in-the-Loop Cryptographic Approval Gate
                </h4>
              </div>
              <Badge variant={isApproved ? "success" : "warning"} className="text-[10px]">
                {isApproved ? "Verified & Authorized" : "Sign-Off Required"}
              </Badge>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              DevMind guarantees zero unverified git mutations. To generate an autofix branch and open a draft PR, verify the cryptographic HMAC-SHA256 signature token.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase font-semibold block">Checkpoint ID</span>
                <span className="font-mono text-slate-200">{checkpointId}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase font-semibold block">Cryptographic Token</span>
                <span className="font-mono text-sky-300">{sampleToken}</span>
              </div>
            </div>

            {/* Success Branch Box if Approved */}
            {autofixBranch && (
              <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-between text-xs text-emerald-400 font-mono animate-in fade-in">
                <span className="flex items-center gap-1.5">
                  <Check className="h-4 w-4" /> Created Autofix Draft Branch: <strong className="text-white">{autofixBranch}</strong>
                </span>
                <a
                  href={`https://github.com/AnshulKanodia/DevMind-AI-Engineering-Copilot/tree/${autofixBranch}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-emerald-300 hover:underline"
                >
                  <span>View Branch</span>
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}

            <div className="pt-2 flex flex-wrap items-center justify-between gap-3">
              <span className="text-[11px] text-slate-400">
                Token expires in 15 minutes. Execution halted until verified.
              </span>

              <Button
                size="sm"
                variant={isApproved ? "secondary" : "glow"}
                onClick={handleApproveAndAutofix}
                disabled={isApproved || isApplyingAutofix}
                className="text-xs flex items-center gap-1.5"
              >
                {isApplyingAutofix ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Verifying Token & Branching...</span>
                  </>
                ) : isApproved ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                    <span>Autofix Applied</span>
                  </>
                ) : (
                  <>
                    <Wrench className="h-3.5 w-3.5" />
                    <span>Sign Token & Apply Autofix</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
