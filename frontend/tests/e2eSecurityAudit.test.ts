import test from "node:test";
import assert from "node:assert/strict";
import {
  performSecurityAudit,
  calculateSecurityScore,
  generateVulnerabilityPatch,
  exportSecurityReportAsMarkdown,
  exportSecurityReportAsJSON,
  runLocalSecurityHeuristics,
  type SecurityFinding,
  type SecurityScanResult,
} from "../src/lib/geminiSecurityScanner.ts";
import type { CodeSnippet } from "../src/lib/repoCodeFetcher.ts";

test("E2E SecurityAudit - Full repository security audit lifecycle with real manifest & posture scoring", async () => {
  const result = await performSecurityAudit(
    "AnshulKanodia/Personal-Finance-Management",
    "main"
  );

  assert.ok(result, "Audit result must be returned");
  assert.equal(result.repo_id, "AnshulKanodia/Personal-Finance-Management");
  assert.equal(result.branch, "main");
  assert.ok(result.scanned_files_count > 0, "Must inspect sensitive files");
  assert.ok(result.security_score >= 0 && result.security_score <= 100, "Score must be bounded 0-100");
  assert.ok(Array.isArray(result.findings), "Findings must be an array");
  assert.ok(result.findings.length > 0, "Must emit security findings or verified safe posture");

  for (const finding of result.findings) {
    assert.ok(finding.id.startsWith("DEV-SEC-"), "Finding ID must follow DEV-SEC- convention");
    assert.ok(finding.cwe.startsWith("CWE-"), "Must have standard CWE classification");
    assert.ok(["critical", "high", "medium", "low"].includes(finding.severity), "Severity must be normalized");
    assert.ok(finding.file.length > 0, "Finding must identify file path");
    assert.ok(finding.line >= 1, "Line number must be positive");
    if (finding.githubUrl) {
      assert.ok(
        finding.githubUrl.includes("github.com/AnshulKanodia/Personal-Finance-Management"),
        "Permalink must link to repository"
      );
      assert.ok(finding.githubUrl.includes("#L"), "Permalink must contain line anchor");
    }
  }
});

test("E2E SecurityAudit - Graceful fallback to heuristic engine when Gemini API key fails", async () => {
  // Test with intentionally invalid API key to verify zero-crash resilience
  const result = await performSecurityAudit(
    "AnshulKanodia/DevMind-AI-Engineering-Copilot",
    "main",
    "TEST_FAILOVER_INVALID_GEMINI_KEY_NONCE_99999",
    {
      primaryModel: "gemini-2.5-flash",
      failoverModel: "gemini-3.5-flash-lite",
    }
  );

  assert.ok(result, "Audit must complete despite API key failure");
  assert.ok(result.findings.length > 0, "Must fall back to static heuristic findings");
  assert.ok(result.security_score >= 0, "Security score must be calculated");
  // Model used should record fallback
  assert.equal(result.model_used, "local-heuristic-engine");
});

test("E2E SecurityAudit - Multi-vulnerability OWASP detection across heterogeneous snippets", () => {
  const snippets: CodeSnippet[] = [
    {
      path: "backend/routes/auth.js",
      startLine: 10,
      endLine: 15,
      content: [
        "10: const router = express.Router();",
        "11: router.post('/login', async (req, res) => {",
        "12:   const query = `SELECT * FROM users WHERE email = '${req.body.email}'`;",
        "13:   await db.execute(query);",
        "14: });",
      ].join("\n"),
    },
    {
      path: "backend/utils/executor.py",
      startLine: 20,
      endLine: 25,
      content: [
        "20: import os, sys",
        "21: def execute_script(user_script):",
        "22:     eval(user_script)",
        "23:     return True",
      ].join("\n"),
    },
    {
      path: "backend/services/hasher.py",
      startLine: 1,
      endLine: 5,
      content: [
        "1: import hashlib",
        "2: def insecure_hash(val):",
        "3:     return hashlib.md5(val.encode()).hexdigest()",
      ].join("\n"),
    },
  ];

  const findings = runLocalSecurityHeuristics(
    snippets,
    "AnshulKanodia/DevMind-AI-Engineering-Copilot",
    "main"
  );

  assert.equal(findings.length, 3, "Should accurately detect all 3 OWASP vulnerabilities");

  const sqli = findings.find((f) => f.cwe === "CWE-89");
  assert.ok(sqli, "Must detect SQL injection");
  assert.equal(sqli?.line, 12);
  assert.ok(sqli?.githubUrl?.includes("#L12"));

  const rce = findings.find((f) => f.cwe === "CWE-78");
  assert.ok(rce, "Must detect command injection");
  assert.equal(rce?.line, 22);
  assert.ok(rce?.githubUrl?.includes("#L22"));

  const crypto = findings.find((f) => f.cwe === "CWE-328");
  assert.ok(crypto, "Must detect weak crypto");
  assert.equal(crypto?.line, 3);
  assert.ok(crypto?.githubUrl?.includes("#L3"));
});

test("E2E SecurityAudit - Interactive patch application and dynamic score recovery", () => {
  const initialFindings: SecurityFinding[] = [
    {
      id: "DEV-SEC-01",
      severity: "critical",
      cwe: "CWE-78",
      title: "Remote Code Execution",
      file: "backend/runner.py",
      line: 10,
      status: "flagged",
      engine: "DevMind SAST",
      owaspCategory: "A03:2021 - Injection",
      description: "Arbitrary eval execution",
      remediation: "Replace with json.loads",
      snippet: "eval(payload)",
    },
    {
      id: "DEV-SEC-02",
      severity: "high",
      cwe: "CWE-89",
      title: "SQL Injection",
      file: "backend/db.py",
      line: 25,
      status: "flagged",
      engine: "DevMind SAST",
      owaspCategory: "A03:2021 - Injection",
      description: "Dynamic string interpolation",
      remediation: "Use parameterized queries",
      snippet: "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
    },
  ];

  // Baseline score: 100 - 25 (critical) - 15 (high) = 60
  const initialScore = calculateSecurityScore(initialFindings);
  assert.equal(initialScore, 60);

  // Generate patch for SQLi finding
  const patch = generateVulnerabilityPatch(initialFindings[1]);
  assert.ok(patch.diffLines.some((l) => l.type === "add" && l.content.includes("Parameterized query")));

  // Simulate applying patch to the critical finding
  initialFindings[0].status = "fixed";
  const scoreAfterCritFix = calculateSecurityScore(initialFindings);
  assert.equal(scoreAfterCritFix, 85, "Fixing critical vulnerability recovers 25 points");

  // Simulate applying patch to high finding
  initialFindings[1].status = "fixed";
  const finalScore = calculateSecurityScore(initialFindings);
  assert.equal(finalScore, 100, "Fixing all vulnerabilities recovers posture score to 100");
});

test("E2E SecurityAudit - Compliance export formats (Markdown & JSON) serialize correctly", () => {
  const scanResult: SecurityScanResult = {
    repo_id: "AnshulKanodia/DevMind-AI-Engineering-Copilot",
    branch: "main",
    scanned_files_count: 6,
    security_score: 92,
    critical_count: 0,
    high_count: 1,
    medium_count: 0,
    low_count: 0,
    scanned_at: "2026-10-24T12:00:00.000Z",
    model_used: "Gemini AI (gemini-2.5-flash)",
    findings: [
      {
        id: "DEV-SEC-01",
        severity: "high",
        cwe: "CWE-89",
        title: "SQL Injection Prevention",
        file: "backend/app/services/query_engine.py",
        line: 78,
        status: "fixed",
        engine: "Gemini AI",
        owaspCategory: "A03:2021 - Injection",
        description: "Dynamic query parameter binding verified",
        remediation: "Parameterized queries enforced",
        snippet: "cursor.execute(query, (repo_id,))",
        githubUrl: "https://github.com/AnshulKanodia/DevMind-AI-Engineering-Copilot/blob/main/backend/app/services/query_engine.py#L78",
      },
    ],
  };

  // Test Markdown export
  const md = exportSecurityReportAsMarkdown(scanResult);
  assert.ok(md.includes("# DevMind AppSec Security Audit Report"));
  assert.ok(md.includes("92 / 100"));
  assert.ok(md.includes("Gemini AI (gemini-2.5-flash)"));
  assert.ok(md.includes("[RESOLVED / PATCHED]"));
  assert.ok(md.includes("https://github.com/AnshulKanodia/DevMind-AI-Engineering-Copilot/blob/main/backend/app/services/query_engine.py#L78"));
  assert.ok(md.includes("Compliance Sign-Off"));

  // Test JSON export
  const jsonStr = exportSecurityReportAsJSON(scanResult);
  const parsed = JSON.parse(jsonStr);
  assert.equal(parsed.report_version, "1.0.0");
  assert.equal(parsed.repository, "AnshulKanodia/DevMind-AI-Engineering-Copilot");
  assert.equal(parsed.score, 92);
  assert.equal(parsed.metrics.resolved, 1);
  assert.equal(parsed.findings[0].status, "fixed");
});
