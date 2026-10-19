import test from "node:test";
import assert from "node:assert/strict";
import {
  getCitationData,
  getGithubCitationUrl,
  detectSymbolAndLanguage,
  fetchLiveCitationData,
  KNOWN_CITATIONS,
} from "../src/lib/citationSnippets.ts";

test("CitationSnippets - retrieves ground-truth data for ast_parser.py", () => {
  const citation = getCitationData("backend/app/services/ast_parser.py", "42-88");

  assert.equal(citation.file, "backend/app/services/ast_parser.py");
  assert.equal(citation.lines, "42-88");
  assert.equal(citation.language, "python");
  assert.equal(citation.symbolName, "ASTParserService");
  assert.equal(citation.nodeType, "ClassDef");
  assert.ok(citation.denseScore > 0.9);
  assert.ok(citation.bm25Score > 10.0);
  assert.ok(citation.combinedScore > 0.8);
  assert.ok(citation.code.includes("class ASTParserService"));
});

test("CitationSnippets - retrieves ground-truth data for hybrid_search.py", () => {
  const citation = getCitationData("backend/app/services/hybrid_search.py", "24-65");

  assert.equal(citation.file, "backend/app/services/hybrid_search.py");
  assert.equal(citation.symbolName, "hybrid_search");
  assert.ok(citation.code.includes("reciprocal_rank_fusion"));
  assert.ok(citation.code.includes("text-embedding-3-small"));
});

test("CitationSnippets - retrieves ground-truth data for approval_service.py", () => {
  const citation = getCitationData("backend/app/services/approval_service.py", "18-64");

  assert.equal(citation.symbolName, "verify_approval_token");
  assert.ok(citation.code.includes("devmind-appr-"));
  assert.ok(citation.code.includes("hmac.compare_digest"));
});

test("CitationSnippets - generates structured fallback for unknown source file", () => {
  const citation = getCitationData("frontend/src/utils/math.ts", "10-25");

  assert.equal(citation.file, "frontend/src/utils/math.ts");
  assert.equal(citation.lines, "10-25");
  assert.equal(citation.language, "typescript");
  assert.ok(citation.code.length > 0);
  assert.ok(citation.denseScore > 0.8);
});

test("CitationSnippets - getGithubCitationUrl builds verified GitHub permalinks with anchors", () => {
  const urlWithRange = getGithubCitationUrl(
    "facebook/react",
    "packages/react/src/React.js",
    "42-88",
    "main"
  );
  assert.equal(
    urlWithRange,
    "https://github.com/facebook/react/blob/main/packages/react/src/React.js#L42-L88"
  );

  const urlSingleLine = getGithubCitationUrl(
    "AnshulKanodia/DevMind-AI-Engineering-Copilot",
    "backend/app/main.py",
    "15",
    "main"
  );
  assert.equal(
    urlSingleLine,
    "https://github.com/AnshulKanodia/DevMind-AI-Engineering-Copilot/blob/main/backend/app/main.py#L15"
  );
});

test("CitationSnippets - detectSymbolAndLanguage extracts AST types and symbol names", () => {
  const pythonClass = detectSymbolAndLanguage(
    "models.py",
    "class UserProfile(BaseModel):\n    id: int"
  );
  assert.equal(pythonClass.language, "python");
  assert.equal(pythonClass.nodeType, "ClassDef");
  assert.equal(pythonClass.symbolName, "UserProfile");

  const tsFunction = detectSymbolAndLanguage(
    "auth.ts",
    "export async function verifyToken(req: Request) {\n    return true;\n}"
  );
  assert.equal(tsFunction.language, "typescript");
  assert.equal(tsFunction.nodeType, "FunctionDef");
  assert.equal(tsFunction.symbolName, "verifyToken");
});

test("CitationSnippets - fetchLiveCitationData returns cached static data for internal services", async () => {
  const citation = await fetchLiveCitationData(
    "devmind",
    "backend/app/services/ast_parser.py",
    "42-88"
  );
  assert.equal(citation.file, "backend/app/services/ast_parser.py");
  assert.equal(citation.symbolName, "ASTParserService");
  assert.ok(citation.code.includes("class ASTParserService"));
});

