import test from "node:test";
import assert from "node:assert/strict";
import {
  identifySecuritySensitiveFiles,
  runLocalSecurityHeuristics,
  calculateSecurityScore,
  performSecurityAudit,
  type SecurityFinding,
} from "../src/lib/geminiSecurityScanner.ts";
import type { CodeSnippet } from "../src/lib/repoCodeFetcher.ts";

test("SecurityScanner - identifySecuritySensitiveFiles ranks auth, db, and config modules highest", () => {
  const filePaths = [
    "frontend/public/logo.png",
    "backend/routes/auth.js",
    "frontend/components/Navbar.tsx",
    "backend/models/User.js",
    "backend/core/security.py",
    "docs/README.md",
    "backend/services/query_engine.py",
  ];

  const sensitive = identifySecuritySensitiveFiles(filePaths, 4);
  assert.ok(sensitive.length > 0);
  assert.ok(sensitive.includes("backend/routes/auth.js"));
  assert.ok(sensitive.includes("backend/models/User.js"));
  assert.ok(sensitive.includes("backend/core/security.py"));
  assert.ok(!sensitive.includes("frontend/public/logo.png"));
});

test("SecurityScanner - runLocalSecurityHeuristics detects SQL injection and command execution", () => {
  const snippets: CodeSnippet[] = [
    {
      path: "backend/routes/users.js",
      startLine: 1,
      endLine: 4,
      content: [
        "1: const express = require('express');",
        "2: router.get('/search', (req, res) => {",
        "3:   const query = `SELECT * FROM users WHERE name = '${req.query.name}'`;",
        "4:   db.execute(query);",
      ].join("\n"),
    },
    {
      path: "backend/utils/runner.py",
      startLine: 1,
      endLine: 3,
      content: [
        "1: import os",
        "2: def run_cmd(user_input):",
        "3:     eval(user_input)",
      ].join("\n"),
    },
  ];

  const findings = runLocalSecurityHeuristics(
    snippets,
    "AnshulKanodia/Personal-Finance-Management",
    "main"
  );

  assert.ok(findings.length >= 2, "Should detect at least 2 vulnerabilities");

  // Check SQL injection
  const sqli = findings.find((f) => f.cwe === "CWE-89");
  assert.ok(sqli, "Must detect CWE-89 SQL injection");
  assert.equal(sqli?.severity, "high");
  assert.ok(sqli?.githubUrl?.includes("#L3"));

  // Check command execution
  const cmd = findings.find((f) => f.cwe === "CWE-78");
  assert.ok(cmd, "Must detect CWE-78 Arbitrary Code Execution");
  assert.equal(cmd?.severity, "critical");
  assert.ok(cmd?.githubUrl?.includes("#L3"));
});

test("SecurityScanner - runLocalSecurityHeuristics detects weak crypto and hardcoded secrets", () => {
  const snippets: CodeSnippet[] = [
    {
      path: "backend/crypto.py",
      startLine: 1,
      endLine: 3,
      content: [
        "1: import hashlib",
        "2: def hash_token(tok):",
        "3:     return hashlib.md5(tok.encode()).hexdigest()",
      ].join("\n"),
    },
    {
      path: "config/secrets.js",
      startLine: 1,
      endLine: 2,
      content: [
        "1: // Configuration",
        "2: const api_key = 'FAKE_EX_TOKEN_DEV_ONLY_1234567890abcdef';",
      ].join("\n"),
    },
  ];

  const findings = runLocalSecurityHeuristics(
    snippets,
    "AnshulKanodia/DevMind-AI-Engineering-Copilot",
    "main"
  );

  const cryptoFinding = findings.find((f) => f.cwe === "CWE-328");
  assert.ok(cryptoFinding, "Should detect weak MD5 hash");
  assert.equal(cryptoFinding?.severity, "medium");

  const secretFinding = findings.find((f) => f.cwe === "CWE-798");
  assert.ok(secretFinding, "Should detect hardcoded API key");
  assert.equal(secretFinding?.severity, "high");
});

test("SecurityScanner - calculateSecurityScore bounds deductions between 0 and 100", () => {
  const perfectScore = calculateSecurityScore([]);
  assert.equal(perfectScore, 100);

  const mockFindings: SecurityFinding[] = [
    {
      id: "1",
      severity: "critical",
      cwe: "CWE-78",
      title: "RCE",
      file: "app.py",
      line: 1,
      status: "flagged",
      engine: "test",
      owaspCategory: "A03",
      description: "test",
      remediation: "test",
      snippet: "eval()",
    },
    {
      id: "2",
      severity: "high",
      cwe: "CWE-89",
      title: "SQLi",
      file: "db.py",
      line: 1,
      status: "flagged",
      engine: "test",
      owaspCategory: "A03",
      description: "test",
      remediation: "test",
      snippet: "SELECT",
    },
  ];

  // 100 - 25 (critical) - 15 (high) = 60
  const score = calculateSecurityScore(mockFindings);
  assert.equal(score, 60);

  // Verified safe findings should not deduct
  mockFindings[0].status = "verified_safe";
  const safeScore = calculateSecurityScore(mockFindings);
  assert.equal(safeScore, 85); // 100 - 15
});

test("SecurityScanner - performSecurityAudit produces complete scan result for internal repository", async () => {
  const result = await performSecurityAudit(
    "https://github.com/AnshulKanodia/DevMind-AI-Engineering-Copilot",
    "main"
  );

  assert.ok(result);
  assert.equal(result.branch, "main");
  assert.equal(typeof result.security_score, "number");
  assert.ok(result.security_score >= 0 && result.security_score <= 100);
  assert.ok(result.findings.length > 0);
  assert.ok(result.findings[0].id.startsWith("DEV-SEC-"));
  assert.ok(result.findings[0].githubUrl?.startsWith("https://github.com/"));
});
