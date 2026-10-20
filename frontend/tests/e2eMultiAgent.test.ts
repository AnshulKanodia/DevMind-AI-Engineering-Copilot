import test from "node:test";
import assert from "node:assert/strict";
import { streamAgentChat, type AgentThought } from "../src/lib/chatStream.ts";
import { streamGeminiWithFailover } from "../src/lib/geminiClient.ts";
import { getGithubCitationUrl, fetchLiveCitationData } from "../src/lib/citationSnippets.ts";
import { extractQueryKeywords, rankRelevantFiles } from "../src/lib/repoCodeFetcher.ts";

test("E2E MultiAgent - End-to-end multi-agent query lifecycle (Router -> Retriever -> Synthesizer)", async () => {
  let accumulatedText = "";
  const capturedThoughts: AgentThought[] = [];
  let emittedCitations: Array<{ file: string; lines: string; type: string }> = [];
  let streamFinished = false;

  await streamAgentChat(
    "Explain the architecture and database setup for Personal-Finance-Management",
    "https://github.com/AnshulKanodia/Personal-Finance-Management",
    {
      onToken: (t) => {
        accumulatedText += t;
      },
      onThought: (th) => {
        capturedThoughts.push(th);
      },
      onCitations: (c) => {
        emittedCitations = c;
      },
      onDone: () => {
        streamFinished = true;
      },
      onError: (err) => {
        assert.fail(`Unexpected stream error: ${err}`);
      },
    }
  );

  assert.ok(streamFinished, "Stream should mark as finished");
  assert.ok(accumulatedText.length > 50, "Synthesizer output must not be empty");

  // Verify node transitions
  const nodeNames = capturedThoughts.map((t) => t.node);
  assert.ok(nodeNames.includes("router"), "Router agent must execute in multi-agent pipeline");
  assert.ok(nodeNames.includes("retriever"), "Retriever agent must execute in multi-agent pipeline");
  assert.ok(nodeNames.includes("synthesizer"), "Synthesizer agent must execute in multi-agent pipeline");

  // Verify citations emitted
  assert.ok(emittedCitations.length > 0, "Citations must be emitted for grounded repository query");
  for (const c of emittedCitations) {
    assert.ok(c.file.length > 0, "Citation file cannot be blank");
    assert.ok(c.lines.length > 0, "Citation line range must be defined");
    // Verify direct GitHub anchor generation
    const ghUrl = getGithubCitationUrl("AnshulKanodia/Personal-Finance-Management", c.file, c.lines);
    assert.ok(ghUrl.includes("github.com/AnshulKanodia/Personal-Finance-Management"), "URL must target correct repository");
    assert.ok(ghUrl.includes("#L"), "URL must contain line anchor");
  }
});

test("E2E MultiAgent - Multi-model failover orchestrator switches when primary model hits quota", async () => {
  const switchEvents: Array<{ modelUsed: string; switched: boolean; failoverReason?: string }> = [];

  try {
    const generator = streamGeminiWithFailover(
      "AIzaSyFakeKeyForE2EFailoverTestingOnly123456",
      [{ role: "user", parts: [{ text: "Hello Gemini test" }] }],
      {
        modelConfig: {
          primaryModel: "gemini-2.5-flash",
          failoverModel: "gemini-3.5-flash-lite",
          tertiaryModel: "gemini-2.5-flash-lite",
        },
        onModelChange: (ev) => {
          switchEvents.push(ev);
        },
      }
    );

    for await (const _token of generator) {
      // Consume tokens if any
    }
  } catch (err: any) {
    // Upstream API error should be preserved and caught
    assert.ok(err.message.includes("API key not valid") || err.message.length > 0);
  }

  // Verify that failover transitions were recorded
  assert.ok(switchEvents.length >= 2, "Failover should trigger transitions across model fallbacks");
  assert.equal(switchEvents[0].modelUsed, "gemini-3.5-flash-lite");
  assert.equal(switchEvents[0].switched, true);
  assert.equal(switchEvents[1].modelUsed, "gemini-2.5-flash-lite");
  assert.equal(switchEvents[1].switched, true);
});

test("E2E MultiAgent - Repository code fetcher extracts keywords and ranks source files", async () => {
  const keywords = extractQueryKeywords("Where is the authentication JWT token verified and parsed in routes?");
  assert.ok(keywords.includes("auth"), "Keywords should capture auth stem");
  assert.ok(keywords.includes("jwt"), "Keywords should capture jwt stem");
  assert.ok(keywords.includes("token"), "Keywords should capture token stem");

  const candidates = [
    "README.md",
    "backend/routes/auth.js",
    "backend/models/User.js",
    "frontend/package.json",
  ];

  const ranked = rankRelevantFiles("Where is authentication JWT token verified?", candidates);
  assert.ok(ranked.length > 0);
  assert.equal(ranked[0], "backend/routes/auth.js", "auth.js should be ranked #1 for authentication query");
});

test("E2E MultiAgent - Live citation metadata resolver gracefully falls back to static cache", async () => {
  const data = await fetchLiveCitationData(
    "https://github.com/AnshulKanodia/DevMind-AI-Engineering-Copilot",
    "backend/app/services/ast_parser.py",
    "10-35"
  );

  assert.equal(data.file, "backend/app/services/ast_parser.py");
  assert.equal(data.language, "python");
  assert.ok(data.code.includes("class ASTParser"), "Should resolve ASTParser ground truth code");
  assert.ok(data.combinedScore > 0.8, "Hybrid score should be high");
});

test("E2E MultiAgent - Stream abort controller terminates cleanly without hanging", async () => {
  const abortController = new AbortController();
  let receivedTokens = 0;

  const streamPromise = streamAgentChat(
    "Tell me everything about the codebase in 10000 words",
    "devmind-test-repo",
    {
      onToken: () => {
        receivedTokens++;
        if (receivedTokens >= 3) {
          abortController.abort();
        }
      },
      onThought: () => {},
      onCitations: () => {},
      onDone: () => {},
      onError: () => {},
    },
    abortController.signal
  );

  await streamPromise;
  assert.ok(receivedTokens >= 1, "Should have received initial tokens before abort");
});
