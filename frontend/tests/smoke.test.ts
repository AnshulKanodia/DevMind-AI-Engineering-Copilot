import test from "node:test";
import assert from "node:assert/strict";
import { cn } from "../src/lib/utils.ts";
import { KNOWN_CITATIONS } from "../src/lib/citationSnippets.ts";

test("SmokeTest - utility cn combines tailwind classes correctly", () => {
  const result = cn("p-4", "text-sm", false && "hidden", "text-white");
  assert.equal(result, "p-4 text-sm text-white");

  const conflict = cn("px-2 py-1", "p-4");
  assert.equal(conflict, "p-4");
});

test("SmokeTest - AST citation registry contains expected core services", () => {
  const keys = Object.keys(KNOWN_CITATIONS);
  assert.ok(keys.includes("backend/app/services/ast_parser.py"));
  assert.ok(keys.includes("backend/app/services/hybrid_search.py"));
  assert.ok(keys.includes("backend/app/agents/graph.py"));
  assert.ok(keys.includes("backend/app/services/secrets_sanitizer.py"));
  assert.ok(keys.includes("backend/app/services/approval_service.py"));
  assert.ok(keys.includes("backend/app/services/pr_review_agent.py"));
});
