"use client";

import React, { useState } from "react";
import {
  FileCheck2,
  Play,
  Copy,
  Check,
  CheckCircle2,
  FileCode,
  Layers,
  Sparkles,
  Terminal,
  BookOpen,
  Network,
  RotateCw,
  Download,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function TestsView() {
  const [selectedModule, setSelectedModule] = useState("backend/app/services/hybrid_search.py");
  const [framework, setFramework] = useState<"pytest" | "jest">("pytest");
  const [activeTab, setActiveTab] = useState<"test" | "diagram" | "docs">("test");
  const [isGenerating, setIsGenerating] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [isRunningTests, setIsRunningTests] = useState(false);
  const [copied, setCopied] = useState(false);

  const sampleSuites: Record<string, string> = {
    "backend/app/services/hybrid_search.py": `import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.hybrid_search import HybridSearchService

@pytest.mark.asyncio
async def test_hybrid_search_fusion_ranking():
    """Verify reciprocal rank fusion correctly unifies dense vector and BM25 results."""
    # 1. Arrange mocks for vector store and BM25 indexer
    mock_vector = AsyncMock()
    mock_vector.vector_search.return_value = [
        {"chunk_id": "chunk_01", "score": 0.94, "content": "def authenticate(): pass"}
    ]

    mock_bm25 = MagicMock()
    mock_bm25.search.return_value = [
        {"chunk_id": "chunk_01", "score": 14.8, "content": "def authenticate(): pass"}
    ]

    service = HybridSearchService(vector_store=mock_vector, bm25_index=mock_bm25)

    # 2. Act
    results = await service.hybrid_search(
        query="OAuth token encryption",
        repo_id="devmind-repo",
        alpha=0.5,
        top_k=3,
    )

    # 3. Assert
    assert len(results) > 0
    assert results[0]["chunk_id"] == "chunk_01"
    assert "combined_score" in results[0]
    assert results[0]["combined_score"] > 0.85
    mock_vector.vector_search.assert_awaited_once()
    mock_bm25.search.assert_called_once()`,

    "backend/app/services/secrets_sanitizer.py": `import pytest
from app.services.secrets_sanitizer import SecretsSanitizerService

def test_entropy_and_regex_redaction():
    """Verify high-entropy keys (H > 4.5) and AWS secrets are redacted."""
    service = SecretsSanitizerService()
    raw_source = 'AWS_SECRET="AKIAIOSFODNN7EXAMPLE_SECRET_KEY_1234567890"'
    
    result = service.scan_and_redact(raw_source, file_path="config.py")
    
    assert len(result.findings) >= 1
    assert "[REDACTED_SECRET" in result.content
    assert "AKIAIOSFODNN7EXAMPLE" not in result.content`,
  };

  const currentCode = sampleSuites[selectedModule] || sampleSuites["backend/app/services/hybrid_search.py"];

  const handleCopy = () => {
    navigator.clipboard.writeText(currentCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSynthesize = () => {
    setIsGenerating(true);
    setTestResult(null);
    setTimeout(() => {
      setIsGenerating(false);
    }, 900);
  };

  const handleRunTest = () => {
    setIsRunningTests(true);
    setTestResult(null);
    setTimeout(() => {
      setIsRunningTests(false);
      setTestResult("PASSED (3 passed in 0.42s)");
    }, 1100);
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FileCheck2 className="h-5 w-5 text-purple-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              Unit Test & Living Architecture Synthesizer
            </h2>
            <Badge variant="glow" className="text-[10px]">
              pytest & Jest Support
            </Badge>
          </div>
          <p className="text-xs text-slate-400">
            Produces runnable unit tests with complete mock isolation (<code className="text-sky-300">unittest.mock</code>) and Mermaid diagrams.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={handleSynthesize}
            disabled={isGenerating}
            variant="glow"
            size="sm"
            className="text-xs flex items-center gap-1.5"
          >
            <Sparkles className={`h-3.5 w-3.5 ${isGenerating ? "animate-spin" : ""}`} />
            <span>{isGenerating ? "Synthesizing Tests..." : "Generate New Suite"}</span>
          </Button>
        </div>
      </div>

      {/* Target Module Picker & Framework Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl border border-slate-800 bg-slate-950/80">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-400">Target Module:</span>
          <select
            value={selectedModule}
            onChange={(e) => setSelectedModule(e.target.value)}
            className="h-8 rounded-lg border border-slate-700 bg-slate-900 px-3 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
          >
            <option value="backend/app/services/hybrid_search.py">
              backend/app/services/hybrid_search.py (Python)
            </option>
            <option value="backend/app/services/secrets_sanitizer.py">
              backend/app/services/secrets_sanitizer.py (Python)
            </option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setFramework("pytest")}
            className={`px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors ${
              framework === "pytest"
                ? "bg-purple-500/10 text-purple-400 border border-purple-500/30 font-bold"
                : "text-slate-400 hover:text-white"
            }`}
          >
            pytest (Python)
          </button>
          <button
            onClick={() => setFramework("jest")}
            className={`px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors ${
              framework === "jest"
                ? "bg-sky-500/10 text-sky-400 border border-sky-500/30 font-bold"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Jest (TS/JS)
          </button>
        </div>
      </div>

      {/* View Tabs: Test Suite vs Architecture Diagram vs Docstrings */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 border-b border-slate-800/80 pb-2">
          <button
            onClick={() => setActiveTab("test")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === "test"
                ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Terminal className="h-3.5 w-3.5" />
            <span>Generated Test Suite</span>
          </button>

          <button
            onClick={() => setActiveTab("diagram")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === "diagram"
                ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Network className="h-3.5 w-3.5" />
            <span>Mermaid Architecture Flow</span>
          </button>

          <button
            onClick={() => setActiveTab("docs")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === "docs"
                ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>Living Documentation</span>
          </button>
        </div>

        {/* TAB 1: GENERATED TEST CODE */}
        {activeTab === "test" && (
          <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden shadow-xl">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/70">
              <div className="flex items-center gap-2">
                <FileCode className="h-4 w-4 text-purple-400" />
                <span className="text-xs font-mono text-slate-300">
                  backend/tests/test_hybrid_search_generated.py
                </span>
                <Badge variant="outline" className="text-[10px]">
                  Mock Isolation 100%
                </Badge>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleRunTest}
                  disabled={isRunningTests}
                  className="text-xs h-7 flex items-center gap-1.5"
                >
                  <Play className={`h-3 w-3 ${isRunningTests ? "animate-spin text-purple-400" : "text-emerald-400"}`} />
                  <span>{isRunningTests ? "Running in Sandbox..." : "Run Test Suite"}</span>
                </Button>

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleCopy}
                  className="text-xs h-7 text-slate-400 hover:text-white"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 mr-1 text-emerald-400" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3 mr-1" /> Copy Suite
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* Test Run Output Notification */}
            {testResult && (
              <div className="px-4 py-2.5 bg-emerald-950/20 border-b border-emerald-500/30 flex items-center justify-between text-xs text-emerald-400 font-mono animate-in fade-in">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4" /> {testResult}
                </span>
                <span className="text-[11px] text-slate-400">Exit Code: 0</span>
              </div>
            )}

            {/* Code Body */}
            <div className="p-4 overflow-x-auto font-mono text-xs text-slate-200 leading-relaxed bg-slate-950">
              <pre>{currentCode}</pre>
            </div>
          </div>
        )}

        {/* TAB 2: MERMAID ARCHITECTURE FLOW */}
        {activeTab === "diagram" && (
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Network className="h-4 w-4 text-purple-400" />
                <h4 className="text-sm font-bold text-white">Hybrid Retrieval Pipeline Topology</h4>
              </div>
              <Badge variant="outline" className="text-[10px]">Mermaid AST Graph</Badge>
            </div>

            {/* Visual Flow Representation */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 py-4 text-xs">
              <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 text-center space-y-2">
                <div className="h-8 w-8 mx-auto rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 font-bold">1</div>
                <div className="font-semibold text-white">User Query</div>
                <p className="text-[11px] text-slate-400">Natural language developer question</p>
              </div>

              <div className="p-4 rounded-xl border border-sky-500/30 bg-sky-950/15 text-center space-y-2">
                <div className="h-8 w-8 mx-auto rounded-lg bg-sky-500/15 border border-sky-500/30 flex items-center justify-center text-sky-400 font-bold">2</div>
                <div className="font-semibold text-white">Dense Embedding</div>
                <p className="text-[11px] text-slate-400">text-embedding-3-small (1536d)</p>
              </div>

              <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-950/15 text-center space-y-2">
                <div className="h-8 w-8 mx-auto rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold">3</div>
                <div className="font-semibold text-white">BM25 Okapi Match</div>
                <p className="text-[11px] text-slate-400">Sparse keyword term frequencies</p>
              </div>

              <div className="p-4 rounded-xl border border-purple-500/30 bg-purple-950/15 text-center space-y-2">
                <div className="h-8 w-8 mx-auto rounded-lg bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 font-bold">4</div>
                <div className="font-semibold text-white">RRF Fusion (α=0.5)</div>
                <p className="text-[11px] text-slate-400">Boundary-preserving AST chunk output</p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: LIVING DOCUMENTATION */}
        {activeTab === "docs" && (
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h4 className="text-base font-bold text-white font-mono">
                HybridSearchService API Reference
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                Auto-extracted from Abstract Syntax Tree docstrings and type annotations.
              </p>
            </div>

            <div className="space-y-4 text-xs">
              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                <div className="font-mono text-sky-400 font-semibold">
                  hybrid_search(query: str, repo_id: str, alpha: float = 0.5, top_k: int = 5)
                </div>
                <p className="text-slate-300">
                  Executes dense vector k-NN search on MongoDB Atlas in parallel with BM25 Okapi lexical scoring, then computes alpha-balanced reciprocal rank fusion.
                </p>
                <div className="pt-2 text-[11px] text-slate-400 space-y-1">
                  <div><strong>Parameters:</strong> <code>query</code> (search string), <code>alpha</code> (weight between 0.0 and 1.0)</div>
                  <div><strong>Returns:</strong> <code>List[HybridSearchResult]</code> with verified line numbers</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
