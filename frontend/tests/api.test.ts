import test from "node:test";
import assert from "node:assert/strict";
import { onboardRepository, type IndexingProgressStep } from "../src/lib/api.ts";

test("API Client - onboardRepository emits all 5 indexing steps", async () => {
  const recordedSteps: IndexingProgressStep[] = [];

  const result = await onboardRepository(
    {
      repo_url: "https://github.com/AnshulKanodia/DevMind-AI-Engineering-Copilot",
      branch: "main",
      shallow: true,
      depth: 1,
    },
    (step) => {
      recordedSteps.push({ ...step });
    }
  );

  assert.ok(result.repo_id.length > 0);
  assert.equal(typeof result.filesIndexed, "number");
  assert.ok(result.filesIndexed > 0);
  assert.equal(typeof result.chunksIndexed, "number");
  assert.ok(result.chunksIndexed > 0);
  assert.equal(typeof result.secretsRedacted, "number");

  // Verify all 5 steps were cycled through
  assert.ok(recordedSteps.length >= 5);
  const stepNumbers = recordedSteps.map((s) => s.step);
  assert.ok(stepNumbers.includes(1));
  assert.ok(stepNumbers.includes(2));
  assert.ok(stepNumbers.includes(3));
  assert.ok(stepNumbers.includes(4));
  assert.ok(stepNumbers.includes(5));

  // Final step reaches 100%
  const lastStep = recordedSteps[recordedSteps.length - 1];
  assert.equal(lastStep.progressPercent, 100);
  assert.equal(lastStep.status, "completed");
});
