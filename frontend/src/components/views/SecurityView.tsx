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
  Filter,
  Search,
  Sparkles,
  Wrench,
  Check,
  ExternalLink,
  Code2,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface SecurityFinding {
  id: string;
  severity: "critical" | "high" | "medium" | "low";
  cwe: string;
  title: string;
  file: string;
  line: number;
  status: "verified_safe" | "flagged" | "fixed";
  engine: string;
  owaspCategory: string;
  description: string;
  remediation: string;
  snippet: string;
}

export function SecurityView() {
  const [scanning, setScanning] = useState(false);
  const [scanStage, setScanStage] = useState<string | null>(null);
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [fixedFindings, setFixedFindings] = useState<Record<string, boolean>>({});

  const initialFindings: SecurityFinding[] = [
    {
      id: "DEV-SEC-01",
      severity: "high",
      cwe: "CWE-89",
      title: "SQL Injection Prevention & Query Parameterization",
      file: "backend/app/services/query_engine.py",
      line: 78,
      status: "verified_safe",
      engine: "Bandit + LLM Reasoner",
      owaspCategory: "A03:2021 - Injection",
      description: "Inspected dynamic query execution. Verified that cursor executes parameterized SQL with tuple bindings rather than f-string formatting.",
      remediation: "Always use parameterized queries: cursor.execute(query, (param1, param2))",
      snippet: "cursor.execute('SELECT * FROM chunks WHERE repo_id = %s', (repo_id,))",
    },
    {
      id: "DEV-SEC-02",
      severity: "medium",
      cwe: "CWE-502",
      title: "Untrusted Deserialization Prevention (Pickle Banned)",
      file: "backend/app/services/cache_service.py",
      line: 34,
      status: "verified_safe",
      engine: "Semgrep SAST",
      owaspCategory: "A08:2021 - Software and Data Integrity Failures",
      description: "Scanned serialization modules. Python standard pickle is strictly disallowed; JSON and Pydantic v2 serialization is enforced.",
      remediation: "Use standard json.loads or Pydantic model_validate_json for caching.",
      snippet: "data = json.loads(cached_payload) # Pydantic/JSON verified safe",
    },
    {
      id: "DEV-SEC-03",
      severity: "low",
      cwe: "CWE-327",
      title: "Cryptographic Algorithm Robustness",
      file: "backend/app/core/security.py",
      line: 19,
      status: "verified_safe",
      engine: "AST Cryptography Rule",
      owaspCategory: "A02:2021 - Cryptographic Failures",
      description: "Enforces AES-256 Fernet encryption for GitHub tokens and HMAC-SHA256 for approval signatures.",
      remediation: "Use Fernet(settings.SECRET_KEY) with 256-bit symmetric keys.",
      snippet: "fernet = Fernet(settings.ENCRYPTION_KEY.encode())\ntoken = fernet.encrypt(raw_token.encode())",
    },
    {
      id: "DEV-SEC-04",
      severity: "high",
      cwe: "CWE-798",
      title: "Hardcoded Credentials Pre-Ingestion Filter",
      file: "backend/app/services/secrets_sanitizer.py",
      line: 45,
      status: "verified_safe",
      engine: "Shannon Entropy (H > 4.5)",
      owaspCategory: "A07:2021 - Identification & Authentication Failures",
      description: "Shannon entropy scan detected no raw API keys in source files. Shannon entropy check ensures all API keys are masked before vector embedding.",
      remediation: "Never commit raw secrets; store in environment variables or key vault.",
      snippet: "if calculate_shannon_entropy(token) > 4.5:\n    clean_line = mask_token(token)",
    },
  ];

  const handleScan = () => {
    setScanning(true);
    setScanStage("1/4: Running Bandit AST Security Linter...");
    setTimeout(() => {
      setScanStage("2/4: Running Semgrep Polyglot SAST Engine...");
      setTimeout(() => {
        setScanStage("3/4: Scanning Shannon Entropy for Leaked Secrets...");
        setTimeout(() => {
          setScanStage("4/4: LLM Filtering False Positives...");
          setTimeout(() => {
            setScanning(false);
            setScanStage(null);
          }, 600);
        }, 600);
      }, 600);
    }, 600);
  };

  const handleAutofix = (id: string) => {
    setFixedFindings((prev) => ({ ...prev, [id]: true }));
  };

  const filtered = initialFindings.filter((f) => {
    const matchesSeverity = selectedSeverity === "all" || f.severity === selectedSeverity;
    const matchesSearch =
      f.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.file.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.cwe.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSeverity && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              Hybrid SAST & Security Auditor
            </h2>
            <Badge variant="glow" className="text-[10px]">
              OWASP Top 10 Compliant
            </Badge>
          </div>
          <p className="text-xs text-slate-400">
            Combines deterministic AST linters (Bandit, Semgrep) with LLM false-positive filtering and secrets redaction.
          </p>
        </div>

        <Button
          onClick={handleScan}
          disabled={scanning}
          variant="glow"
          size="sm"
          className="flex items-center gap-2 text-xs"
        >
          {scanning ? (
            <>
              <div className="h-3.5 w-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>{scanStage || "Scanning AST Nodes..."}</span>
            </>
          ) : (
            <>
              <Play className="h-3.5 w-3.5" />
              <span>Run SAST Scan</span>
            </>
          )}
        </Button>
      </div>

      {/* Security Health Scorecard */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card className="border-emerald-500/20 bg-emerald-950/10">
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">Security Grade</span>
            <div className="text-2xl font-bold text-emerald-400 font-mono flex items-center gap-1.5">
              <span>A+</span>
              <span className="text-xs font-normal text-emerald-300/80">(Zero Criticals)</span>
            </div>
            <p className="text-[11px] text-slate-500">All injection gates passed</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">Secrets Sanitization</span>
            <div className="text-2xl font-bold text-sky-400 font-mono">100%</div>
            <p className="text-[11px] text-slate-500">Shannon entropy ($H &gt; 4.5$)</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">OWASP Verification</span>
            <div className="text-2xl font-bold text-purple-400 font-mono">10 / 10</div>
            <p className="text-[11px] text-slate-500">Injection to Crypto audited</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">LLM Filtering</span>
            <div className="text-2xl font-bold text-white font-mono">0 False Positives</div>
            <p className="text-[11px] text-slate-500">Heuristic reasoning verified</p>
          </CardContent>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-xl border border-slate-800 bg-slate-900/40">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          <Filter className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          {["all", "high", "medium", "low"].map((sev) => (
            <button
              key={sev}
              onClick={() => setSelectedSeverity(sev)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-colors ${
                selectedSeverity === sev
                  ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {sev}
            </button>
          ))}
        </div>

        <div className="w-full sm:w-64">
          <Input
            icon={<Search className="h-3.5 w-3.5 text-slate-400" />}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search CWE or filename..."
            className="h-8 text-xs"
          />
        </div>
      </div>

      {/* Findings List */}
      <div className="space-y-4">
        {filtered.map((item) => {
          const isFixed = fixedFindings[item.id];
          return (
            <div
              key={item.id}
              className="p-5 rounded-xl border border-slate-800 bg-slate-950/80 hover:border-slate-700 transition-all space-y-3.5 shadow-md"
            >
              {/* Finding Title Row */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <Badge
                    variant={
                      item.severity === "high"
                        ? "destructive"
                        : item.severity === "medium"
                        ? "warning"
                        : "secondary"
                    }
                    className="uppercase font-mono text-[10px]"
                  >
                    {item.severity}
                  </Badge>

                  <span className="font-mono text-xs text-sky-400 font-semibold">
                    {item.cwe}
                  </span>

                  <span className="text-xs font-bold text-white">
                    {item.title}
                  </span>
                </div>

                <div className="flex items-center gap-2 text-xs">
                  <Badge variant={isFixed || item.status === "verified_safe" ? "success" : "warning"}>
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    {isFixed ? "Autofixed & Patched" : "Verified Safe"}
                  </Badge>
                </div>
              </div>

              {/* Description & OWASP metadata */}
              <div className="space-y-1.5 text-xs text-slate-300 leading-relaxed">
                <p>{item.description}</p>
                <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-500 pt-1">
                  <span>Category: <strong className="text-slate-400">{item.owaspCategory}</strong></span>
                  <span>&bull;</span>
                  <span>Engine: <strong className="text-slate-400">{item.engine}</strong></span>
                </div>
              </div>

              {/* Code Snippet Box */}
              <div className="rounded-lg border border-slate-800 bg-slate-900/80 overflow-hidden text-xs">
                <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900 border-b border-slate-800 text-[11px] font-mono text-slate-400">
                  <div className="flex items-center gap-1.5">
                    <FileCode className="h-3.5 w-3.5 text-sky-400" />
                    <span>{item.file}</span>
                    <span className="text-slate-500">:L{item.line}</span>
                  </div>
                  <span className="text-emerald-400 flex items-center gap-1 text-[10px]">
                    <Check className="h-3 w-3" /> Syntax Inspected
                  </span>
                </div>
                <div className="p-3 font-mono text-slate-200 text-xs overflow-x-auto bg-slate-950">
                  <pre>{item.snippet}</pre>
                </div>
              </div>

              {/* Remediation & Action Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-slate-800/60 text-xs text-slate-400">
                <div className="flex items-center gap-1.5 truncate">
                  <Sparkles className="h-3.5 w-3.5 text-sky-400 shrink-0" />
                  <span className="truncate">Remediation: {item.remediation}</span>
                </div>

                <Button
                  size="sm"
                  variant={isFixed ? "secondary" : "outline"}
                  onClick={() => handleAutofix(item.id)}
                  disabled={isFixed}
                  className="text-xs h-7 shrink-0"
                >
                  <Wrench className="h-3 w-3 mr-1" />
                  <span>{isFixed ? "Autofix Applied" : "Generate Autofix"}</span>
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
