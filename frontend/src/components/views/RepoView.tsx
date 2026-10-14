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
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function RepoView() {
  const [reindexing, setReindexing] = useState(false);

  const files = [
    { path: "backend/app/services/ast_parser.py", language: "Python", nodes: 42, size: "14.2 KB" },
    { path: "backend/app/services/hybrid_search.py", language: "Python", nodes: 28, size: "9.8 KB" },
    { path: "backend/app/agents/graph.py", language: "Python", nodes: 35, size: "12.1 KB" },
    { path: "backend/app/services/pr_review_agent.py", language: "Python", nodes: 31, size: "10.4 KB" },
    { path: "frontend/src/app/page.tsx", language: "TypeScript", nodes: 18, size: "6.4 KB" },
    { path: "frontend/src/components/layout/Navbar.tsx", language: "TypeScript", nodes: 12, size: "4.1 KB" },
  ];

  const handleReindex = () => {
    setReindexing(true);
    setTimeout(() => setReindexing(false), 1500);
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/50">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FolderTree className="h-5 w-5 text-sky-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              Repository Ingestion & AST Tree Indexer
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Clones repositories in isolated sandboxes, redacts secrets, and parses functions/classes into MongoDB Atlas vectors.
          </p>
        </div>

        <Button
          onClick={handleReindex}
          disabled={reindexing}
          variant="outline"
          size="sm"
          className="flex items-center gap-2"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${reindexing ? "animate-spin text-sky-400" : ""}`} />
          <span>{reindexing ? "Re-Indexing AST..." : "Trigger Re-Index"}</span>
        </Button>
      </div>

      {/* Indexing Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/80 space-y-1">
          <span className="text-xs text-slate-400">Total Indexed Files</span>
          <div className="text-xl font-bold text-white">142 source files</div>
          <p className="text-[11px] text-slate-500">Filtered by 25+ supported languages</p>
        </div>
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/80 space-y-1">
          <span className="text-xs text-slate-400">Vector Embeddings</span>
          <div className="text-xl font-bold text-sky-400">684 chunks</div>
          <p className="text-[11px] text-slate-500">1536-dim text-embedding-3-small</p>
        </div>
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/80 space-y-1">
          <span className="text-xs text-slate-400">Lexical Index</span>
          <div className="text-xl font-bold text-emerald-400">BM25 Okapi</div>
          <p className="text-[11px] text-slate-500">α-weighted reciprocal rank fusion</p>
        </div>
      </div>

      {/* Ingested Files Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <span className="text-xs font-semibold text-white">Parsed AST Modules</span>
          <Badge variant="outline" className="text-[10px]">
            Sandboxed Ephemeral Clone
          </Badge>
        </div>

        <div className="divide-y divide-slate-800/80">
          {files.map((file, i) => (
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
    </div>
  );
}
