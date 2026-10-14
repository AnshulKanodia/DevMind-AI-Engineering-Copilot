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
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function PRReviewView() {
  const [prNumber, setPrNumber] = useState("42");
  const [approved, setApproved] = useState(false);
  const [tokenCopied, setTokenCopied] = useState(false);

  const sampleToken = "devmind-appr-9a4f2e18d6c7b3";

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/50">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <GitPullRequestDraft className="h-5 w-5 text-amber-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              PR Review & Safe Autofix Hub
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Reviews GitHub PR diffs, flags breaking changes, and enforces cryptographic Human-in-the-Loop approvals.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="glow" className="text-xs">
            Human-in-the-Loop Gate Enforced
          </Badge>
        </div>
      </div>

      {/* PR Diff Overview Card */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2.5">
              <span className="text-sm font-semibold text-white">
                PR #{prNumber}: Add AES-256 Token Decryption & AST Ingestion
              </span>
              <Badge variant="warning">Changes Requested</Badge>
            </div>
            <div className="text-xs text-slate-400 font-mono">
              Branch: <span className="text-sky-300">feat/ast-ingest</span> ➔{" "}
              <span className="text-indigo-300">main</span>
            </div>
          </div>

          {/* Static Verdict & Defect Check */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-slate-400">Files Changed</span>
              <div className="font-semibold text-slate-200">3 files (+142, -18)</div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-slate-400">Security Gate</span>
              <div className="font-semibold text-emerald-400 flex items-center gap-1">
                <CheckCircle className="h-3.5 w-3.5" /> No Secrets Leaked
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-slate-400">Verdict</span>
              <div className="font-semibold text-amber-400">1 Missing Test Fixture</div>
            </div>
          </div>

          {/* Inline Suggestion Box */}
          <div className="rounded-lg border border-slate-800 bg-slate-950 p-4 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono text-slate-300 flex items-center gap-1.5">
                <FileDiff className="h-3.5 w-3.5 text-sky-400" />
                backend/app/services/github_client.py:65
              </span>
              <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded">
                Recommendation
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              &quot;Consider raising a typed <code>GitHubAPIError</code> instead of generic <code>RuntimeError</code> when token resolution fails.&quot;
            </p>
          </div>

          {/* Cryptographic Approval Token Gate */}
          <div className="p-4 rounded-xl border border-sky-500/30 bg-sky-950/20 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-sky-400" />
                <span className="text-xs font-semibold text-white">
                  Cryptographic Approval Gate (HMAC-SHA256)
                </span>
              </div>
              <Badge variant={approved ? "success" : "secondary"}>
                {approved ? "Approved & Verified" : "Pending Sign-off"}
              </Badge>
            </div>
            <p className="text-xs text-slate-400">
              DevMind guarantees zero unverified git mutations. To generate an autofix branch and open a draft PR, verify the cryptographic token.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <div className="px-3 py-1.5 rounded-md bg-slate-950 border border-slate-800 text-xs font-mono text-sky-300">
                {sampleToken}
              </div>
              <Button
                size="sm"
                variant={approved ? "secondary" : "glow"}
                onClick={() => setApproved(true)}
                disabled={approved}
                className="text-xs"
              >
                {approved ? "Signed & Authorized" : "Approve Autofix Patch"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
