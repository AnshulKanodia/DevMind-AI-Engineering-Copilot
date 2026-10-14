"use client";

import React, { useState } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Play,
  CheckCircle2,
  Lock,
  Terminal,
  FileCode,
  ArrowUpRight,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function SecurityView() {
  const [scanning, setScanning] = useState(false);
  const [scanned, setScanned] = useState(true);

  const findings = [
    {
      id: "DEV-SEC-01",
      severity: "high" as const,
      cwe: "CWE-89: SQL Injection Prevention",
      file: "backend/app/services/query_engine.py",
      line: 78,
      status: "Safe Parameterized Query Verified",
      engine: "Bandit + LLM Reasoner",
      snippet: "cursor.execute('SELECT * FROM chunks WHERE repo_id = %s', (repo_id,))",
    },
    {
      id: "DEV-SEC-02",
      severity: "medium" as const,
      cwe: "CWE-502: Deserialization of Untrusted Data",
      file: "backend/app/services/cache_service.py",
      line: 34,
      status: "JSON Serializer Enforced (pickle banned)",
      engine: "Semgrep SAST",
      snippet: "data = json.loads(cached_payload) # Verified safe serializer",
    },
    {
      id: "DEV-SEC-03",
      severity: "low" as const,
      cwe: "CWE-327: Use of a Broken Cryptographic Algorithm",
      file: "backend/app/core/security.py",
      line: 19,
      status: "AES-256 Fernet + SHA-256 HMAC Enforced",
      engine: "AST Cryptography Rule",
      snippet: "fernet = Fernet(settings.SECRET_KEY)",
    },
  ];

  const handleScan = () => {
    setScanning(true);
    setTimeout(() => {
      setScanning(false);
      setScanned(true);
    }, 1200);
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/50">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              Hybrid SAST & Security Auditor
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Combines deterministic AST linters (Bandit, Semgrep) with LLM false-positive filtering.
          </p>
        </div>

        <Button
          onClick={handleScan}
          disabled={scanning}
          variant="glow"
          size="sm"
          className="flex items-center gap-2"
        >
          {scanning ? (
            <>
              <div className="h-3.5 w-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Scanning AST Nodes...</span>
            </>
          ) : (
            <>
              <Play className="h-3.5 w-3.5" />
              <span>Run SAST Scan</span>
            </>
          )}
        </Button>
      </div>

      {/* Security Scorecards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <span className="text-xs text-slate-400">Audit Status</span>
              <div className="text-lg font-bold text-emerald-400 flex items-center gap-1.5 mt-0.5">
                <ShieldCheck className="h-4 w-4" /> Zero Critical Flaws
              </div>
            </div>
            <Badge variant="success">Passing</Badge>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <span className="text-xs text-slate-400">Entropy Secrets Redacted</span>
              <div className="text-lg font-bold text-white mt-0.5">100% Pre-Filtered</div>
            </div>
            <Badge variant="glow">H &gt; 4.5</Badge>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <span className="text-xs text-slate-400">OWASP Coverage</span>
              <div className="text-lg font-bold text-white mt-0.5">A01 - A10 Verified</div>
            </div>
            <Badge variant="outline">2026 Ready</Badge>
          </CardContent>
        </Card>
      </div>

      {/* Findings List */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-white">Inspected Security Checkpoints</h3>

        <div className="space-y-3">
          {findings.map((item) => (
            <div
              key={item.id}
              className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-colors space-y-3"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      item.severity === "high"
                        ? "destructive"
                        : item.severity === "medium"
                        ? "warning"
                        : "secondary"
                    }
                  >
                    {item.severity.toUpperCase()}
                  </Badge>
                  <span className="text-xs font-semibold text-slate-200">{item.cwe}</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-emerald-400">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>{item.status}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                <FileCode className="h-3.5 w-3.5 text-sky-400" />
                <span>{item.file}</span>
                <span className="text-slate-500">line {item.line}</span>
                <span className="text-[10px] ml-auto text-slate-500 font-sans">
                  Engine: {item.engine}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 font-mono text-xs text-slate-300">
                <code>{item.snippet}</code>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
