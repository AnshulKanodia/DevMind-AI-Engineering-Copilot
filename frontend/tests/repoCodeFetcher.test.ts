import test from "node:test";
import assert from "node:assert/strict";
import {
  extractQueryKeywords,
  rankRelevantFiles,
  fetchRelevantSourceSnippets,
} from "../src/lib/repoCodeFetcher.ts";

test("RepoCodeFetcher - extractQueryKeywords strips stop words and derives domain stems", () => {
  const keywords = extractQueryKeywords("How does the user authentication and login work?");
  assert.ok(keywords.includes("authentication"));
  assert.ok(keywords.includes("auth"));
  assert.ok(keywords.includes("jwt"));
  assert.ok(keywords.includes("login"));
  // Stop words should be removed
  assert.equal(keywords.includes("how"), false);
  assert.equal(keywords.includes("does"), false);
  assert.equal(keywords.includes("the"), false);
});

test("RepoCodeFetcher - rankRelevantFiles ranks matching source code files highest", () => {
  const candidateFiles = [
    "README.md",
    "docs/architecture.png",
    "src/services/auth.ts",
    "src/components/Button.tsx",
    "backend/app/api/auth_router.py",
    "package-lock.json",
  ];

  const ranked = rankRelevantFiles("how does auth routing work", candidateFiles, 3);
  assert.equal(ranked.length, 3);
  // Both auth files should be in the top ranked results
  assert.ok(ranked.includes("src/services/auth.ts"));
  assert.ok(ranked.includes("backend/app/api/auth_router.py"));
  // Binary / Lock files should never be ranked above source code
  assert.equal(ranked[0].endsWith(".png"), false);
  assert.equal(ranked[0].endsWith(".json"), false);
});

test("RepoCodeFetcher - rankRelevantFiles gives entry points appropriate priority", () => {
  const candidateFiles = [
    "src/utils/math.ts",
    "src/index.ts",
    "backend/app/main.py",
    "assets/logo.svg",
  ];

  const ranked = rankRelevantFiles("overview of codebase", candidateFiles, 2);
  assert.ok(ranked.includes("src/index.ts") || ranked.includes("backend/app/main.py"));
});

test("RepoCodeFetcher - fetchRelevantSourceSnippets returns ground-truth snippets for internal repo", async () => {
  const snippets = await fetchRelevantSourceSnippets("devmind", "Explain AST parser");
  assert.ok(snippets.length >= 2);

  const astSnippet = snippets.find((s) => s.path.includes("ast_parser.py"));
  assert.ok(astSnippet);
  assert.ok(astSnippet.content.includes("ASTLanguageAwareChunker"));
  assert.equal(astSnippet.startLine, 42);
  assert.equal(astSnippet.endLine, 88);
});
