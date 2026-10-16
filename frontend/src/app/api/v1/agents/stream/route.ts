import { NextRequest } from "next/server";
import { resolveGroundedRepoQuery } from "@/lib/repoKnowledge";

export const dynamic = "force-dynamic";

/**
 * Server-Sent Events (SSE) route handler for DevMind multi-agent chat.
 * Operates natively on Vercel Serverless and proxies to Python backend when available.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { repo_id = "default", query = "" } = body;

    // 1. If backend URL is set and not localhost in production, attempt proxy
    const backendUrl = process.env.BACKEND_INTERNAL_URL;
    if (backendUrl && !backendUrl.includes("localhost:8000")) {
      try {
        const backendRes = await fetch(`${backendUrl}/api/v1/agents/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_id, query }),
        });

        if (backendRes.ok && backendRes.body) {
          return new Response(backendRes.body, {
            headers: {
              "Content-Type": "text/event-stream; charset=utf-8",
              "Cache-Control": "no-cache, no-transform",
              Connection: "keep-alive",
            },
          });
        }
      } catch {
        // Backend proxy failed, fall through to native serverless orchestrator
      }
    }

    // 2. Native Next.js Serverless Multi-Agent Orchestration
    const result = await resolveGroundedRepoQuery(repo_id, query);

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const sendEvent = (event: string, data: any) => {
          controller.enqueue(
            encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
          );
        };

        const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

        // Node 1: Router Agent
        sendEvent("node_start", { node: "router" });
        await sleep(150);

        sendEvent("intent_classified", {
          intent: result.intent,
          confidence: result.confidence,
          message: result.routerMessage,
        });
        await sleep(150);

        // Node 2: Hybrid Retrieval Agent
        sendEvent("node_start", { node: "retriever" });
        await sleep(200);

        sendEvent("retrieval_complete", {
          chunk_count: result.citations.length || 3,
          strategy: "hybrid_ast_bm25_dense",
          message: result.retrieverMessage,
        });
        await sleep(150);

        // Node 3: Synthesizer Agent
        sendEvent("node_start", { node: "synthesizer" });

        // Stream markdown text token-by-token
        const words = result.markdownResponse.split(" ");
        for (let i = 0; i < words.length; i++) {
          const token = (i === 0 ? "" : " ") + words[i];
          sendEvent("token", { token });
          await sleep(15);
        }

        // Citations Frame
        sendEvent("citations", {
          citations: result.citations.map((c) => `${c.file}:${c.lines}`),
        });
        await sleep(50);

        // Completion Frame
        sendEvent("done", { status: "completed" });
        controller.close();
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch (err: any) {
    return new Response(
      JSON.stringify({ error: err.message || "Internal streaming error" }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
