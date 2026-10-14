"use client";

import React, { useState } from "react";
import {
  FolderTree,
  FileCode2,
  Database,
  RefreshCw,
  CheckCircle2,
  Layers,
  FileCheck,
  Code,
  ShieldCheck,
  ShieldAlert,
  GitBranch,
  Lock,
  Search,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface RepoViewProps {
  currentRepo?: string;
  currentBranch?: string;
  filesCount?: number;
  chunksCount?: number;
  onOpenConnectModal?: () => void;
}

export function RepoView({
  currentRepo = "AnshulKanodia/DevMind-AI-Engineering-Copilot",
  currentBranch = "main",
  filesCount = 142,
  chunksCount = 684,
  onOpenConnectModal,
}: RepoViewProps) {
  const [reindexing, setReindexing] = useState(false);
  const [reindexStep, setReindexStep] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState("");
  const [activeTab, setActiveTab] = useState<"files" | "secrets">("files");

  const files = [
    { path: "backend/app/services/ast_parser.py", language: "Python", nodes: 42, size: "14.2 KB", status: "Indexed" },
    { path: "backend/app/services/hybrid_search.py", language: "Python", nodes: 28, size: "9.8 KB", status: "Indexed" },
    { path: "backend/app/agents/graph.py", language: "Python", nodes: 35, size: "12.1 KB", status: "Indexed" },
    { path: "backend/app/services/pr_review_agent.py", language: "Python", nodes: 31, size: "10.4 KB", status: "Indexed" },
    { path: "backend/app/services/secrets_sanitizer.py", language: "Python", nodes: 24, size: "8.6 KB", status: "Indexed" },
    { path: "frontend/src/app/page.tsx", language: "TypeScript", nodes: 18, size: "6.4 KB", status: "Indexed" },
    { path: "frontend/src/components/layout/Navbar.tsx", language: "TypeScript", nodes: 14, size: "4.8 KB", status: "Indexed" },
    { path: "frontend/src/components/modals/ConnectRepoModal.tsx", language: "TypeScript", nodes: 22, size: "7.9 KB", status: "Indexed" },
    { path: "frontend/src/lib/api.ts", language: "TypeScript", nodes: 16, size: "5.1 KB", status: "Indexed" },
  ];

  const secretsFindings = [
    {
      file: "backend/.env.example",
      type: "High-Entropy API Token Placeholder",
      line: 4,
      status: "Masked [REDACTED_SECRET:KEY]",
      entropy: "H = 4.62",
    },
    {
      file: "docker-compose.yml",
      type: "Database Password Variable",
      line: 12,
      status: "Verified Environment Reference",
      entropy: "H = 3.81",
    },
  ];

  const filteredFiles = files.filter((f) =>
    f.path.toLowerCase().includes(searchFilter.toLowerCase())
  );

  const handleReindex = () => {
    setReindexing(true);
    setReindexStep("Scanning AST syntax trees...");
    setTimeout(() => {
      setReindexStep("Computing 1536-dim OpenAI embeddings...");
      setTimeout(() => {
        setReindexStep("Updating MongoDB Atlas vector index...");
        setTimeout(() => {
          setReindexing(false);
          setReindexStep(null);
        }, 800);
      }, 800);
    }, 800);
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/50">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FolderTree className="h-5 w-5 text-sky-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              Repository Ingestion & Live AST Indexer
            </h2>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>Active Repository:</span>
            <span className="font-mono text-sky-300 font-semibold">{currentRepo}</span>
            <span>&bull;</span>
            <span className="flex items-center gap-1 font-mono text-slate-300">
              <GitBranch className="h-3 w-3 text-indigo-400" /> {currentBranch}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {onOpenConnectModal && (
            <Button
              onClick={onOpenConnectModal}
              variant="outline"
              size="sm"
              className="text-xs"
            >
              Change Repo
            </Button>
          )}

          <Button
            onClick={handleReindex}
            disabled={reindexing}
            variant="glow"
            size="sm"
            className="flex items-center gap-2 text-xs"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${reindexing ? "animate-spin text-white" : ""}`}
            />
            <span>{reindexing ? reindexStep || "Re-indexing..." : "Trigger Re-Index"}</span>
          </Button>
        </div>
      </div>

      {/* Indexing Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/80 space-y-1">
          <span className="text-xs text-slate-400">Total Indexed Files</span>
          <div className="text-xl font-bold text-white font-mono">{filesCount} files</div>
          <p className="text-[11px] text-slate-500">25+ programming languages supported</p>
        </div>
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/80 space-y-1">
          <span className="text-xs text-slate-400">Vector Embeddings</span>
          <div className="text-xl font-bold text-sky-400 font-mono">{chunksCount} AST chunks</div>
          <p className="text-[11px] text-slate-500">Dense text-embedding-3-small (1536d)</p>
        </div>
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/80 space-y-1">
          <span className="text-xs text-slate-400">Secrets Pre-Redaction</span>
          <div className="text-xl font-bold text-emerald-400 font-mono">100% Protected</div>
          <p className="text-[11px] text-slate-500">Shannon entropy ($H &gt; 4.5$) guards</p>
        </div>
      </div>

      {/* Tabs: Ingested Files vs Secrets Filter */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab("files")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === "files"
                  ? "bg-sky-500/10 text-sky-400 border border-sky-500/20"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Parsed AST Files ({files.length})
            </button>
            <button
              onClick={() => setActiveTab("secrets")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === "secrets"
                  ? "bg-sky-500/10 text-sky-400 border border-sky-500/20"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Secrets Pre-Filter Audit (2)
            </button>
          </div>

          {activeTab === "files" && (
            <div className="w-full sm:w-64">
              <Input
                icon={<Search className="h-3.5 w-3.5 text-slate-400" />}
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Search indexed files..."
                className="h-8 text-xs"
              />
            </div>
          )}
        </div>

        {/* Files View */}
        {activeTab === "files" && (
          <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
            <div className="divide-y divide-slate-800/80">
              {filteredFiles.map((file, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between px-5 py-3 hover:bg-slate-900/40 transition-colors text-xs"
                >
                  <div className="flex items-center gap-3">
                    <FileCode2 className="h-4 w-4 text-sky-400" />
                    <span className="font-mono text-slate-200">{file.path}</span>
                  </div>
                  <div className="flex items-center gap-4 text-slate-400">
                    <span className="hidden sm:inline font-mono text-[11px]">{file.size}</span>
                    <span className="text-sky-300 font-mono text-[11px]">{file.nodes} AST nodes</span>
                    <Badge variant="secondary" className="text-[10px]">
                      {file.language}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Secrets Audit View */}
        {activeTab === "secrets" && (
          <div className="space-y-3">
            {secretsFindings.map((item, i) => (
              <div
                key={i}
                className="p-4 rounded-xl border border-slate-800 bg-slate-950/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-emerald-400" />
                    <span className="font-mono text-white font-medium">{item.file}</span>
                    <Badge variant="glow" className="text-[10px]">
                      {item.entropy}
                    </Badge>
                  </div>
                  <p className="text-slate-400">{item.type} (line {item.line})</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded">
                    {item.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
