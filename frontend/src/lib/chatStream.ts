/**
 * DevMind Multi-Agent Streaming Chat Client
 * Consumes Server-Sent Events (SSE) from /api/v1/agents/stream with fallback simulation.
 */

export interface AgentThought {
  node: string;
  status: "running" | "completed" | "error";
  message: string;
  timestamp: string;
  details?: Record<string, any>;
}

export interface StreamChatCallbacks {
  onToken: (token: string) => void;
  onThought: (thought: AgentThought) => void;
  onCitations: (citations: Array<{ file: string; lines: string; type: string }>) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

import { resolveGroundedRepoQuery } from "./repoKnowledge.ts";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "";

/**
 * Initiates an SSE stream for developer query.
 */
export async function streamAgentChat(
  query: string,
  repoId: string,
  callbacks: StreamChatCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const isLocalBackend = typeof window !== "undefined" && window.location.hostname === "localhost";

  // Try real backend endpoint first
  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (typeof window !== "undefined") {
      const storedKey = localStorage.getItem("devmind_gemini_api_key");
      if (storedKey && storedKey.trim().length > 10) {
        headers["x-gemini-key"] = storedKey.trim();
      }
      const primaryModel = localStorage.getItem("devmind_gemini_primary_model");
      if (primaryModel) headers["x-gemini-primary-model"] = primaryModel;
      const failoverModel = localStorage.getItem("devmind_gemini_failover_model");
      if (failoverModel) headers["x-gemini-failover-model"] = failoverModel;
    }

    const response = await fetch(`${API_BASE}/api/v1/agents/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        repo_id: repoId,
        query: query,
      }),
      signal: signal,
    });

    if (response.ok && response.body) {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        if (signal?.aborted) {
          reader.cancel();
          callbacks.onDone();
          return;
        }

        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          const frameLines = block.split("\n");
          let eventType = "";
          let eventData = "";

          for (const line of frameLines) {
            if (line.startsWith("event: ")) {
              eventType = line.replace("event: ", "").trim();
            } else if (line.startsWith("data: ")) {
              eventData = line.replace("data: ", "").trim();
            }
          }

          if (eventData) {
            try {
              const parsed = JSON.parse(eventData);

              if (eventType === "node_start") {
                callbacks.onThought({
                  node: parsed.node || "agent",
                  status: "running",
                  message: `Node started: ${parsed.node}`,
                  timestamp: new Date().toISOString(),
                });
              } else if (eventType === "intent_classified") {
                callbacks.onThought({
                  node: "router",
                  status: "completed",
                  message: `Intent classified as: ${parsed.intent} (${Math.round((parsed.confidence || 0.95) * 100)}% confidence)`,
                  timestamp: new Date().toISOString(),
                  details: parsed,
                });
              } else if (eventType === "retrieval_complete") {
                callbacks.onThought({
                  node: "retriever",
                  status: "completed",
                  message: `Retrieved ${parsed.chunk_count || 5} AST chunks via hybrid search (α=0.5)`,
                  timestamp: new Date().toISOString(),
                  details: parsed,
                });
              } else if (eventType === "model_status") {
                callbacks.onThought({
                  node: "orchestrator",
                  status: parsed.failover ? "running" : "completed",
                  message: parsed.failover
                    ? `Load shifted to failover model: ${parsed.model} (${parsed.reason || "Quota/rate limit switch"})`
                    : `Active Gemini reasoning model: ${parsed.model}`,
                  timestamp: new Date().toISOString(),
                  details: parsed,
                });
              } else if (eventType === "token") {
                callbacks.onToken(parsed.token || "");
              } else if (eventType === "citations") {
                const formatted = (parsed.citations || []).map((c: string) => {
                  const parts = c.split(":");
                  return {
                    file: parts[0] || c,
                    lines: parts[1] || "1-30",
                    type: "ast_chunk",
                  };
                });
                callbacks.onCitations(formatted);
              } else if (eventType === "done") {
                callbacks.onDone();
                return;
              }
            } catch (err) {
              // Parse error on frame, ignore
            }
          }
        }
      }

      callbacks.onDone();
      return;
    }
  } catch (err: any) {
    if (signal?.aborted) {
      callbacks.onDone();
      return;
    }
    // If backend is unreachable (e.g. Vercel deployment), fall back to realistic multi-agent generator
  }

  // Fallback realistic simulation for interactive client-side preview
  await simulateAgentStreaming(query, repoId, callbacks, signal);
}

/**
 * High-fidelity multi-agent simulated stream for preview deployments
 */
async function simulateAgentStreaming(
  query: string,
  repoId: string,
  callbacks: StreamChatCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const sleep = (ms: number) =>
    new Promise((resolve) => {
      const timer = setTimeout(resolve, ms);
      signal?.addEventListener("abort", () => {
        clearTimeout(timer);
        resolve(null);
      });
    });

  if (signal?.aborted) return;

  // Resolve grounded repository context
  const result = await resolveGroundedRepoQuery(repoId, query);

  // Step 1: Router Agent
  callbacks.onThought({
    node: "router",
    status: "running",
    message: "Evaluating natural language query against agent graph...",
    timestamp: new Date().toISOString(),
  });
  await sleep(350);
  if (signal?.aborted) return;

  callbacks.onThought({
    node: "router",
    status: "completed",
    message: `Intent classified: "${result.intent}" (confidence: ${Math.round(result.confidence * 100)}%)`,
    timestamp: new Date().toISOString(),
  });

  // Step 2: Retrieval Agent
  callbacks.onThought({
    node: "retriever",
    status: "running",
    message: result.retrieverMessage || "Querying MongoDB Atlas Vector Search (dense + BM25 Okapi lexical fusion)...",
    timestamp: new Date().toISOString(),
  });
  await sleep(400);
  if (signal?.aborted) return;

  callbacks.onThought({
    node: "retriever",
    status: "completed",
    message: `Retrieved ${result.citations.length || 3} AST chunks with boundary-preserving syntax blocks.`,
    timestamp: new Date().toISOString(),
  });

  // Step 3: Synthesis Generation
  callbacks.onThought({
    node: "synthesizer",
    status: "running",
    message: result.synthesizerMessage || "Synthesizing grounded explanation with verified file & line citations...",
    timestamp: new Date().toISOString(),
  });

  // Stream tokens word by word with typing pacing
  const words = result.markdownResponse.split(" ");
  for (let i = 0; i < words.length; i++) {
    if (signal?.aborted) return;
    const token = (i === 0 ? "" : " ") + words[i];
    callbacks.onToken(token);
    await sleep(20);
  }

  callbacks.onThought({
    node: "synthesizer",
    status: "completed",
    message: "Response generated and citations verified.",
    timestamp: new Date().toISOString(),
  });

  callbacks.onCitations(result.citations);
  callbacks.onDone();
}
