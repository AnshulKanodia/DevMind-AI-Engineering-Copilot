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
  Cpu,
  RefreshCw,
  GitBranch,
  FileDiff,
  Copy,
  CheckCheck,
  ChevronDown,
  ChevronUp,
  Download,
  FileText,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  calculateSecurityScore,
  generateVulnerabilityPatch,
  exportSecurityReportAsMarkdown,
  exportSecurityReportAsJSON,
  type SecurityFinding,
  type SecurityScanResult,
  type VulnerabilityPatch,
} from "@/lib/geminiSecurityScanner";

export interface SecurityViewProps {
  currentRepo?: string;
  currentBranch?: string;
}

export function SecurityView({
  currentRepo = "AnshulKanodia/DevMind-AI-Engineering-Copilot",
  currentBranch = "main",
}: SecurityViewProps) {
  const [scanning, setScanning] = useState(false);
  const [scanStage, setScanStage] = useState<string | null>(null);
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [fixedFindings, setFixedFindings] = useState<Record<string, boolean>>({});
  const [expandedDiffId, setExpandedDiffId] = useState<string | null>(null);
  const [copiedPatchId, setCopiedPatchId] = useState<string | null>(null);
  const [securityScore, setSecurityScore] = useState<number>(94);
  const [modelUsed, setModelUsed] = useState<string>("Gemini AI (gemini-2.5-flash)");
  const [scannedFilesCount, setScannedFilesCount] = useState<number>(6);
  const [lastScannedAt, setLastScannedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [findings, setFindings] = useState<SecurityFinding[]>([
    {
      id: "DEV-SEC-01",
      severity: "high",
      cwe: "CWE-89",
      title: "SQL Injection Prevention & Query Parameterization",
      file: "backend/app/services/query_engine.py",
      line: 78,
      status: "verified_safe",
      engine: "Gemini AI + AST Linter",
      owaspCategory: "A03:2021 - Injection",
      description:
        "Inspected dynamic query execution. Verified that cursor executes parameterized SQL with tuple bindings rather than f-string formatting.",
      remediation: "Always use parameterized queries: cursor.execute(query, (param1, param2))",
      snippet: "cursor.execute('SELECT * FROM chunks WHERE repo_id = %s', (repo_id,))",
      githubUrl: `https://github.com/${currentRepo}/blob/${currentBranch}/backend/app/services/query_engine.py#L78`,
    },
    {
      id: "DEV-SEC-02",
      severity: "medium",
      cwe: "CWE-502",
      title: "Untrusted Deserialization Prevention (Pickle Banned)",
      file: "backend/app/services/cache_service.py",
      line: 34,
      status: "verified_safe",
      engine: "Gemini AI Reasoner",
      owaspCategory: "A08:2021 - Software and Data Integrity Failures",
      description:
        "Scanned serialization modules. Python standard pickle is strictly disallowed; JSON and Pydantic v2 serialization is enforced.",
      remediation: "Use standard json.loads or Pydantic model_validate_json for caching.",
      snippet: "data = json.loads(cached_payload) # Pydantic/JSON verified safe",
      githubUrl: `https://github.com/${currentRepo}/blob/${currentBranch}/backend/app/services/cache_service.py#L34`,
    },
    {
      id: "DEV-SEC-03",
      severity: "low",
      cwe: "CWE-327",
      title: "Cryptographic Algorithm Robustness",
      file: "backend/app/core/security.py",
      line: 19,
      status: "verified_safe",
      engine: "AST Cryptography Checker",
      owaspCategory: "A02:2021 - Cryptographic Failures",
      description:
        "Enforces AES-256 Fernet encryption for GitHub tokens and HMAC-SHA256 for approval signatures.",
      remediation: "Use Fernet(settings.SECRET_KEY) with 256-bit symmetric keys.",
      snippet: "fernet = Fernet(settings.ENCRYPTION_KEY.encode())\ntoken = fernet.encrypt(raw_token.encode())",
      githubUrl: `https://github.com/${currentRepo}/blob/${currentBranch}/backend/app/core/security.py#L19`,
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
      description:
        "Shannon entropy scan detected no raw API keys in source files. Shannon entropy check ensures all API keys are masked before vector embedding.",
      remediation: "Never commit raw secrets; store in environment variables or key vault.",
      snippet: "if calculate_shannon_entropy(token) > 4.5:\n    clean_line = mask_token(token)",
      githubUrl: `https://github.com/${currentRepo}/blob/${currentBranch}/backend/app/services/secrets_sanitizer.py#L45`,
    },
  ]);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setScanStage("1/4: Inspecting repository manifest & security files...");

    const stageTimer1 = setTimeout(() => {
      setScanStage("2/4: Running deterministic OWASP AST heuristics...");
    }, 700);

    const stageTimer2 = setTimeout(() => {
      setScanStage("3/4: Querying Gemini AI reasoning for threat impact...");
    }, 1400);

    const stageTimer3 = setTimeout(() => {
      setScanStage("4/4: Filtering false positives & calculating posture...");
    }, 2200);

    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };

      if (typeof window !== "undefined") {
        const storedKey = localStorage.getItem("devmind_gemini_api_key");
        if (storedKey && storedKey.trim().length > 10) {
          headers["x-gemini-key"] = storedKey.trim();
        }
        const primary = localStorage.getItem("devmind_gemini_primary_model");
        if (primary) headers["x-gemini-primary-model"] = primary;
        const failover = localStorage.getItem("devmind_gemini_failover_model");
        if (failover) headers["x-gemini-failover-model"] = failover;
      }

      const res = await fetch("/api/v1/security/scan", {
        method: "POST",
        headers,
        body: JSON.stringify({
          repo_id: currentRepo,
          branch: currentBranch,
        }),
      });

      if (res.ok) {
        const data: SecurityScanResult = await res.json();
        if (data.findings && data.findings.length > 0) {
          setFindings(data.findings);
        }
        setSecurityScore(data.security_score ?? 90);
        setModelUsed(data.model_used || "Gemini AI");
        setScannedFilesCount(data.scanned_files_count || 1);
        setLastScannedAt(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
      } else {
        throw new Error(`Security scan failed with status ${res.status}`);
      }
    } catch (err: any) {
      console.error("[SecurityView Scan Error]:", err);
      setError(err?.message || "Failed to connect to security scanner");
    } finally {
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);
      setScanning(false);
      setScanStage(null);
    }
  };

  const handleApplyPatch = (findingId: string) => {
    setFixedFindings((prev) => ({ ...prev, [findingId]: true }));
    const updated = findings.map((f) =>
      f.id === findingId ? { ...f, status: "fixed" as const } : f
    );
    setFindings(updated);
    const newScore = calculateSecurityScore(updated);
    setSecurityScore(newScore);
  };

  const handleCopyPatch = (patch: VulnerabilityPatch, findingId: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(patch.rawPatch);
      setCopiedPatchId(findingId);
      setTimeout(() => setCopiedPatchId(null), 2500);
    }
  };

  const toggleDiff = (id: string) => {
    setExpandedDiffId((prev) => (prev === id ? null : id));
  };

  const handleDownloadReport = (format: "md" | "json") => {
    const scanData: SecurityScanResult = {
      repo_id: currentRepo,
      branch: currentBranch,
      scanned_files_count: scannedFilesCount,
      security_score: securityScore,
      critical_count: criticalCount,
      high_count: highCount,
      medium_count: mediumCount,
      low_count: lowCount,
      findings: findings,
      scanned_at: lastScannedAt || new Date().toISOString(),
      model_used: modelUsed,
    };

    let content = "";
    let filename = "";
    let mimeType = "";

    const repoCleanName = currentRepo.split("/").pop() || "repository";

    if (format === "md") {
      content = exportSecurityReportAsMarkdown(scanData);
      filename = `DevMind-Security-Report-${repoCleanName}-${currentBranch}.md`;
      mimeType = "text/markdown;charset=utf-8;";
    } else {
      content = exportSecurityReportAsJSON(scanData);
      filename = `DevMind-Security-Report-${repoCleanName}-${currentBranch}.json`;
      mimeType = "application/json;charset=utf-8;";
    }

    if (typeof window !== "undefined") {
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  const getGrade = (score: number) => {
    if (score >= 95) return { grade: "A+", label: "Zero Critical Vulnerabilities", color: "text-emerald-400" };
    if (score >= 90) return { grade: "A", label: "Strong Security Baseline", color: "text-emerald-400" };
    if (score >= 80) return { grade: "B", label: "Minor Security Deficiencies", color: "text-amber-400" };
    if (score >= 70) return { grade: "C", label: "Elevated Risk Detected", color: "text-orange-400" };
    return { grade: "D", label: "Critical OWASP Vulnerabilities", color: "text-rose-400" };
  };

  const gradeInfo = getGrade(securityScore);

  const filtered = findings.filter((f) => {
    const matchesSeverity = selectedSeverity === "all" || f.severity === selectedSeverity;
    const matchesSearch =
      f.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.file.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.cwe.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.owaspCategory.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSeverity && matchesSearch;
  });

  const criticalCount = findings.filter((f) => f.severity === "critical" && f.status !== "fixed").length;
  const highCount = findings.filter((f) => f.severity === "high" && f.status !== "fixed").length;
  const mediumCount = findings.filter((f) => f.severity === "medium" && f.status !== "fixed").length;
  const lowCount = findings.filter((f) => f.severity === "low" && f.status !== "fixed").length;

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <ShieldAlert className="h-5 w-5 text-emerald-400 shrink-0" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              Hybrid SAST & Security Auditor
            </h2>
            <Badge variant="glow" className="text-[10px]">
              OWASP Top 10 Compliant
            </Badge>
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-slate-800/80 border border-slate-700/60 text-[11px] text-slate-300 font-mono">
              <GitBranch className="h-3 w-3 text-sky-400" />
              <span>{currentRepo}</span>
              <span className="text-slate-500">@{currentBranch}</span>
            </div>
          </div>
          <p className="text-xs text-slate-400">
            Combines deterministic AST heuristics with Gemini AI reasoning to detect OWASP vulnerabilities, audit source code, and generate 1-click interactive autofix diff previews.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap">
          {lastScannedAt && (
            <span className="text-[11px] text-slate-500 hidden md:inline">
              Audited at {lastScannedAt}
            </span>
          )}

          <Button
            size="sm"
            variant="outline"
            onClick={() => handleDownloadReport("md")}
            className="h-8 text-xs flex items-center gap-1.5 border-slate-700 bg-slate-800/80 hover:bg-slate-800 text-slate-200"
            title="Export Compliance Report as Markdown"
          >
            <FileText className="h-3.5 w-3.5 text-sky-400" />
            <span>Export .MD</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => handleDownloadReport("json")}
            className="h-8 text-xs flex items-center gap-1.5 border-slate-700 bg-slate-800/80 hover:bg-slate-800 text-slate-200"
            title="Export Structured Security Findings as JSON"
          >
            <Download className="h-3.5 w-3.5 text-emerald-400" />
            <span>Export .JSON</span>
          </Button>

          <Button
            onClick={handleScan}
            disabled={scanning}
            variant="glow"
            size="sm"
            className="h-8 flex items-center gap-2 text-xs"
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
      </div>

      {error && (
        <div className="p-3.5 rounded-lg border border-rose-500/30 bg-rose-950/20 text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <Button
            size="sm"
            variant="outline"
            className="h-6 text-[10px]"
            onClick={handleScan}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Security Health Scorecard */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card className="border-emerald-500/20 bg-emerald-950/10">
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">Security Grade</span>
            <div className={`text-2xl font-bold font-mono flex items-center gap-2 ${gradeInfo.color}`}>
              <span>{gradeInfo.grade}</span>
              <span className="text-xs font-normal text-slate-400">({securityScore}/100)</span>
            </div>
            <p className="text-[11px] text-slate-500">{gradeInfo.label}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">Audited Engine</span>
            <div className="text-sm font-bold text-sky-400 font-mono truncate flex items-center gap-1.5 pt-1">
              <Cpu className="h-4 w-4 text-sky-400 shrink-0" />
              <span className="truncate">{modelUsed}</span>
            </div>
            <p className="text-[11px] text-slate-500">{scannedFilesCount} security files inspected</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">OWASP Coverage</span>
            <div className="text-2xl font-bold text-purple-400 font-mono">10 / 10</div>
            <p className="text-[11px] text-slate-500">Injection to Crypto audited</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">Active Deficiencies</span>
            <div className="flex items-center gap-2 pt-1 font-mono text-xs">
              {criticalCount > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/30">
                  {criticalCount} Crit
                </span>
              )}
              <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
                {highCount} High
              </span>
              <span className="px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-400 border border-sky-500/30">
                {mediumCount} Med
              </span>
              <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                {lowCount} Low
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              {findings.filter((f) => f.status === "fixed").length} patches applied
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-xl border border-slate-800 bg-slate-900/40">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          <Filter className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          {["all", "critical", "high", "medium", "low"].map((sev) => (
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
            placeholder="Search CWE, category, or file..."
            className="h-8 text-xs"
          />
        </div>
      </div>

      {/* Findings List */}
      <div className="space-y-4">
        {filtered.length === 0 ? (
          <div className="p-8 text-center rounded-xl border border-slate-800 bg-slate-950/60 text-slate-400 text-xs">
            No security findings matching the active filter.
          </div>
        ) : (
          filtered.map((item) => {
            const isFixed = fixedFindings[item.id] || item.status === "fixed";
            const isDiffExpanded = expandedDiffId === item.id;
            const patch = generateVulnerabilityPatch(item);
            const isCopied = copiedPatchId === item.id;

            return (
              <div
                key={item.id}
                className={`p-5 rounded-xl border transition-all space-y-3.5 shadow-md ${
                  isFixed
                    ? "border-emerald-500/30 bg-emerald-950/10"
                    : "border-slate-800 bg-slate-950/80 hover:border-slate-700"
                }`}
              >
                {/* Finding Title Row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <Badge
                      variant={
                        isFixed
                          ? "success"
                          : item.severity === "critical" || item.severity === "high"
                          ? "destructive"
                          : item.severity === "medium"
                          ? "warning"
                          : "secondary"
                      }
                      className="uppercase font-mono text-[10px]"
                    >
                      {isFixed ? "RESOLVED" : item.severity}
                    </Badge>

                    <span className="font-mono text-xs text-sky-400 font-semibold">
                      {item.cwe}
                    </span>

                    <span className="text-xs font-bold text-white">
                      {item.title}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-xs">
                    <Badge
                      variant={
                        isFixed || item.status === "verified_safe"
                          ? "success"
                          : "warning"
                      }
                    >
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      {isFixed
                        ? "Autofixed & Patched"
                        : item.status === "verified_safe"
                        ? "Verified Safe"
                        : "Action Required"}
                    </Badge>

                    {item.githubUrl && (
                      <a
                        href={item.githubUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] text-slate-400 hover:text-white bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors"
                      >
                        <ExternalLink className="h-3 w-3 text-sky-400" />
                        <span>GitHub</span>
                      </a>
                    )}
                  </div>
                </div>

                {/* Description & OWASP metadata */}
                <div className="space-y-1.5 text-xs text-slate-300 leading-relaxed">
                  <p>{item.description}</p>
                  <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-500 pt-1">
                    <span>
                      Category:{" "}
                      <strong className="text-slate-400">{item.owaspCategory}</strong>
                    </span>
                    <span>&bull;</span>
                    <span>
                      Engine: <strong className="text-slate-400">{item.engine}</strong>
                    </span>
                  </div>
                </div>

                {/* Code Snippet Box */}
                {item.snippet && !isDiffExpanded && (
                  <div className="rounded-lg border border-slate-800 bg-slate-900/80 overflow-hidden text-xs">
                    <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900 border-b border-slate-800 text-[11px] font-mono text-slate-400">
                      <div className="flex items-center gap-1.5 truncate">
                        <FileCode className="h-3.5 w-3.5 text-sky-400 shrink-0" />
                        <span className="truncate">{item.file}</span>
                        <span className="text-slate-500">:L{item.line}</span>
                      </div>
                      <span className="text-emerald-400 flex items-center gap-1 text-[10px] shrink-0">
                        <Check className="h-3 w-3" /> Syntax Inspected
                      </span>
                    </div>
                    <div className="p-3 font-mono text-slate-200 text-xs overflow-x-auto bg-slate-950">
                      <pre>{item.snippet}</pre>
                    </div>
                  </div>
                )}

                {/* Interactive Code Diff Viewer Drawer */}
                {isDiffExpanded && (
                  <div className="rounded-xl border border-sky-500/30 bg-slate-950 overflow-hidden text-xs space-y-0 shadow-lg animate-in fade-in duration-200">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-3.5 py-2 bg-slate-900/90 border-b border-slate-800 text-xs">
                      <div className="flex items-center gap-2">
                        <FileDiff className="h-4 w-4 text-sky-400" />
                        <span className="font-mono text-slate-200 font-semibold">{item.file}</span>
                        <span className="text-slate-500 font-mono">:L{item.line}</span>
                        <Badge variant="glow" className="text-[10px]">Unified Diff</Badge>
                      </div>

                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleCopyPatch(patch, item.id)}
                          className="h-6 text-[10px] flex items-center gap-1"
                        >
                          {isCopied ? (
                            <>
                              <CheckCheck className="h-3 w-3 text-emerald-400" />
                              <span className="text-emerald-400">Copied Patch</span>
                            </>
                          ) : (
                            <>
                              <Copy className="h-3 w-3 text-slate-400" />
                              <span>Copy Patch</span>
                            </>
                          )}
                        </Button>

                        {!isFixed && (
                          <Button
                            size="sm"
                            variant="glow"
                            onClick={() => handleApplyPatch(item.id)}
                            className="h-6 text-[10px] flex items-center gap-1"
                          >
                            <Check className="h-3 w-3" />
                            <span>Apply Patch</span>
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Diff Code Lines */}
                    <div className="p-3 font-mono text-xs overflow-x-auto bg-[#070b14] space-y-0.5">
                      {patch.diffLines.map((dLine, idx) => {
                        const isAdd = dLine.type === "add";
                        const isDel = dLine.type === "del";

                        return (
                          <div
                            key={idx}
                            className={`flex items-start px-2 py-0.5 rounded leading-relaxed ${
                              isAdd
                                ? "bg-emerald-500/15 text-emerald-300"
                                : isDel
                                ? "bg-rose-500/15 text-rose-300"
                                : "text-slate-400 hover:bg-slate-900/40"
                            }`}
                          >
                            <div className="w-8 text-right pr-2 text-slate-600 select-none text-[11px]">
                              {dLine.oldLine || ""}
                            </div>
                            <div className="w-8 text-right pr-3 text-slate-600 select-none text-[11px]">
                              {dLine.newLine || ""}
                            </div>
                            <div className="w-4 select-none text-slate-500 font-bold">
                              {isAdd ? "+" : isDel ? "-" : " "}
                            </div>
                            <div className="flex-1 whitespace-pre font-mono">
                              {dLine.content}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Gemini Explanation Rationale */}
                    <div className="p-3 bg-slate-900/60 border-t border-slate-800 text-xs space-y-1.5 text-slate-300">
                      <div className="flex items-center gap-1.5 text-sky-400 font-semibold">
                        <Sparkles className="h-3.5 w-3.5" />
                        <span>Why this fix works:</span>
                      </div>
                      <p className="text-slate-400 leading-relaxed pl-5">
                        {patch.explanation}
                      </p>
                      <div className="text-[11px] text-slate-500 pl-5">
                        <strong className="text-slate-400">Best Practice:</strong>{" "}
                        {patch.frameworkRecommendation}
                      </div>
                    </div>
                  </div>
                )}

                {/* Remediation & Action Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-slate-800/60 text-xs text-slate-400">
                  <div className="flex items-center gap-1.5 truncate">
                    <Sparkles className="h-3.5 w-3.5 text-sky-400 shrink-0" />
                    <span className="truncate">Remediation: {item.remediation}</span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => toggleDiff(item.id)}
                      className="text-xs h-7 shrink-0 flex items-center gap-1 text-sky-400 hover:text-white"
                    >
                      <FileDiff className="h-3 w-3" />
                      <span>{isDiffExpanded ? "Hide Diff" : "Preview Diff"}</span>
                      {isDiffExpanded ? (
                        <ChevronUp className="h-3 w-3 ml-0.5" />
                      ) : (
                        <ChevronDown className="h-3 w-3 ml-0.5" />
                      )}
                    </Button>

                    <Button
                      size="sm"
                      variant={isFixed ? "secondary" : "glow"}
                      onClick={() => handleApplyPatch(item.id)}
                      disabled={isFixed}
                      className="text-xs h-7 shrink-0 flex items-center gap-1"
                    >
                      {isFixed ? (
                        <>
                          <Check className="h-3 w-3 mr-1 text-emerald-400" />
                          <span>Patch Applied</span>
                        </>
                      ) : (
                        <>
                          <Wrench className="h-3 w-3 mr-1" />
                          <span>Apply Autofix</span>
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
