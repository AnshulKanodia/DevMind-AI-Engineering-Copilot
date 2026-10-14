import test from "node:test";
import assert from "node:assert/strict";
import { streamAgentChat, type AgentThought } from "../src/lib/chatStream.ts";

test("ChatStream - streams tokens, thoughts, and citations for general query", async () => {
  let fullText = "";
  const thoughts: AgentThought[] = [];
  let citationsList: Array<{ file: string; lines: string; type: string }> = [];
  let isDone = false;

  await streamAgentChat(
    "How does the AST parser work?",
    "devmind-test-repo",
    {
      onToken: (tok) => {
        fullText += tok;
      },
      onThought: (t) => {
        thoughts.push(t);
      },
      onCitations: (c) => {
        citationsList = c;
      },
      onDone: () => {
        isDone = true;
      },
      onError: (err) => {
        assert.fail(`Stream returned error: ${err}`);
      },
    }
  );

  assert.ok(isDone, "Stream should mark as done");
  assert.ok(fullText.length > 50, "Full response should have meaningful content");
  assert.ok(thoughts.length >= 3, "Multi-agent chain should emit thoughts");
  assert.ok(citationsList.length > 0, "Citations should be emitted");

  const thoughtNodes = thoughts.map((t) => t.node);
  assert.ok(thoughtNodes.includes("router"));
  assert.ok(thoughtNodes.includes("retriever"));
  assert.ok(thoughtNodes.includes("synthesizer"));
});

test("ChatStream - supports AbortController cancellation", async () => {
  const controller = new AbortController();
  let tokenCount = 0;

  // Abort immediately
  controller.abort();

  await streamAgentChat(
    "Cancel this request",
    "devmind-test-repo",
    {
      onToken: () => {
        tokenCount++;
      },
      onThought: () => {},
      onCitations: () => {},
      onDone: () => {},
      onError: () => {},
    },
    controller.signal
  );

  assert.equal(tokenCount, 0, "No tokens should be streamed when pre-aborted");
});
