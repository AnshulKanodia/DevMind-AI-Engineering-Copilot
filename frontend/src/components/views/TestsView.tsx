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
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function TestsView() {
  const [copied, setCopied] = useState(false);
  const [selectedFile, setSelectedFile] = useState("backend/app/services/hybrid_search.py");

  const sampleTestCode = `import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.hybrid_search import HybridSearchService

@pytest.mark.asyncio
async def test_hybrid_search_fusion_ranking():
    # Arrange mock vector and BM25 retrievers
    mock_vector = AsyncMock()
    mock_vector.search.return_value = [{"chunk_id": "c1", "score": 0.89}]
    
    mock_bm25 = MagicMock()
    mock_bm25.search.return_value = [{"chunk_id": "c1", "score": 12.4}]
    
    service = HybridSearchService(vector_search=mock_vector, bm25_index=mock_bm25)
    
    # Act
    results = await service.hybrid_search(query="OAuth token encryption", alpha=0.5, top_k=5)
    
    # Assert
    assert len(results) > 0
    assert results[0]["chunk_id"] == "c1"
    assert "combined_score" in results[0]
`;

  const handleCopy = () => {
    navigator.clipboard.writeText(sampleTestCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/50">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FileCheck2 className="h-5 w-5 text-purple-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              Unit Test & Living Documentation Synthesizer
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Generates runnable pytest & Jest test suites with mock isolation and auto-documents modules.
          </p>
        </div>

        <Button variant="glow" size="sm" className="flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Synthesize Test Suite</span>
        </Button>
      </div>

      {/* Target Module Picker */}
      <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs">
        <span className="text-slate-400 font-medium">Selected Target:</span>
        <span className="font-mono text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 rounded">
          {selectedFile}
        </span>
        <Badge variant="outline" className="ml-auto text-[10px]">
          Framework: pytest + unittest.mock
        </Badge>
      </div>

      {/* Synthesized Test Output */}
      <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800 bg-slate-900/60">
          <div className="flex items-center gap-2">
            <FileCode className="h-4 w-4 text-sky-400" />
            <span className="text-xs font-mono text-slate-300">
              backend/tests/test_hybrid_search_generated.py
            </span>
          </div>
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

        <div className="p-4 overflow-x-auto font-mono text-xs text-slate-300 leading-relaxed bg-slate-950/90">
          <pre>{sampleTestCode}</pre>
        </div>
      </div>
    </div>
  );
}
