import test from "node:test";
import assert from "node:assert/strict";
import {
  resolveGeminiApiKey,
  validateGeminiApiKey,
  DEFAULT_MODEL_CONFIG,
  streamGeminiWithFailover,
  type GeminiMessage,
} from "../src/lib/geminiClient.ts";

test("GeminiClient - resolves API key from request headers with highest priority", () => {
  const originalEnv = process.env.GEMINI_API_KEY;
  process.env.GEMINI_API_KEY = "env-dummy-key-123456789";

  const headers = new Headers();
  headers.set("x-gemini-key", "header-test-key-987654321");

  const resolved = resolveGeminiApiKey(headers);
  assert.ok(resolved);
  assert.equal(resolved.key, "header-test-key-987654321");
  assert.equal(resolved.source, "header");

  process.env.GEMINI_API_KEY = originalEnv;
});

test("GeminiClient - resolves API key from x-ai-key header alias", () => {
  const headers = new Headers();
  headers.set("x-ai-key", "alias-test-key-abcdef123456");

  const resolved = resolveGeminiApiKey(headers);
  assert.ok(resolved);
  assert.equal(resolved.key, "alias-test-key-abcdef123456");
  assert.equal(resolved.source, "header");
});

test("GeminiClient - falls back to environment variable when header is absent", () => {
  const originalEnv = process.env.GEMINI_API_KEY;
  process.env.GEMINI_API_KEY = "env-fallback-key-1234567890";

  const resolved = resolveGeminiApiKey();
  assert.ok(resolved);
  assert.equal(resolved.key, "env-fallback-key-1234567890");
  assert.equal(resolved.source, "env");

  process.env.GEMINI_API_KEY = originalEnv;
});

test("GeminiClient - returns null when neither header nor env var is provided", () => {
  const originalEnv1 = process.env.GEMINI_API_KEY;
  const originalEnv2 = process.env.GOOGLE_API_KEY;
  delete process.env.GEMINI_API_KEY;
  delete process.env.GOOGLE_API_KEY;

  const resolved = resolveGeminiApiKey();
  assert.equal(resolved, null);

  process.env.GEMINI_API_KEY = originalEnv1;
  process.env.GOOGLE_API_KEY = originalEnv2;
});

test("GeminiClient - rejects invalid or empty API key format in validator", async () => {
  const resultEmpty = await validateGeminiApiKey("");
  assert.equal(resultEmpty.valid, false);

  const resultShort = await validateGeminiApiKey("short");
  assert.equal(resultShort.valid, false);
});

test("GeminiClient - DEFAULT_MODEL_CONFIG defines gemini-2.5-flash as primary and gemini-3.5-flash-lite as failover", () => {
  assert.equal(DEFAULT_MODEL_CONFIG.primaryModel, "gemini-2.5-flash");
  assert.equal(DEFAULT_MODEL_CONFIG.failoverModel, "gemini-3.5-flash-lite");
  assert.equal(DEFAULT_MODEL_CONFIG.tertiaryModel, "gemini-2.5-flash-lite");
});

test("GeminiClient - streamGeminiWithFailover cascades to next model on initial failure", async () => {
  const events: any[] = [];
  try {
    const generator = streamGeminiWithFailover(
      "invalid-test-api-key-12345",
      [{ role: "user", parts: [{ text: "ping" }] }],
      {
        modelConfig: {
          primaryModel: "gemini-2.5-flash",
          failoverModel: "gemini-3.5-flash-lite",
        },
        onModelChange: (ev) => {
          events.push(ev);
        },
      }
    );

    // Consume generator to trigger execution
    for await (const _token of generator) {
      // Won't yield with invalid test key
    }
  } catch (err: any) {
    // Both models should fail with invalid key, proving it attempted failover
    assert.ok(err);
  }

  // At least one failover attempt was recorded
  assert.ok(events.length >= 1);
  assert.equal(events[0].modelUsed, "gemini-3.5-flash-lite");
  assert.equal(events[0].switched, true);
});

