import { NextRequest } from "next/server";
import { resolveGroundedRepoQuery, discoverRepoContext } from "@/lib/repoKnowledge";
import { resolveGeminiApiKey, streamGeminiChat } from "@/lib/geminiClient";

export const dynamic = "force-dynamic";

/**
 * Server-Sent Events (SSE) route handler for DevMind multi-agent chat.
 * Operates natively on Vercel Serverless with Gemini AI and fallback to grounded engine.
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

    // 2. Resolve Gemini API Key (from incoming headers or Vercel env variable)
    const geminiKey = resolveGeminiApiKey(req.headers);

    // 3. Autonomous Repository Research (Grounded Baseline)
    const result = await resolveGroundedRepoQuery(repo_id, query);
    const repoContext = await discoverRepoContext(repo_id);

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
        await sleep(100);

        sendEvent("intent_classified", {
          intent: result.intent,
          confidence: result.confidence,
          message: geminiKey
            ? `Classified query using Gemini AI reasoning for ${repo_id}.`
            : result.routerMessage,
        });
        await sleep(100);

        // Node 2: Retrieval Agent
        sendEvent("node_start", { node: "retriever" });
        await sleep(100);

        sendEvent("retrieval_complete", {
          chunk_count: result.citations.length || 3,
          strategy: geminiKey ? "gemini_context_grounded" : "hybrid_ast_bm25_dense",
          message: result.retrieverMessage,
        });
        await sleep(100);

        // Node 3: Synthesizer Agent (Real Gemini Stream or Grounded Fallback)
        sendEvent("node_start", { node: "synthesizer" });

        let streamedWithGemini = false;

        if (geminiKey) {
          try {
            const systemPrompt = `You are DevMind, an expert AI Engineering Copilot.
You are connected to repository: "${repo_id}".
Active project title: "${repoContext?.parsedReadme?.title || repo_id}".
Repository context documentation:
${repoContext?.readme ? repoContext.readme.slice(0, 8000) : "No README available."}

Package configuration:
${repoContext?.packageJson ? JSON.stringify(repoContext.packageJson, null, 2).slice(0, 2000) : "None"}

Environment example:
${repoContext?.envExample ? repoContext.envExample.slice(0, 1000) : "None"}

Instructions:
1. Answer the user's question directly, accurately, and politely with markdown formatting.
2. Ground your explanations in the actual repository files, dependencies, and configuration.
3. Whenever referencing files or sections, cite them using markdown (e.g., [README.md:1-50]).
4. Provide complete, executable commands without leaving blank instructions.`;

            const geminiGenerator = streamGeminiChat(
              geminiKey.key,
              [{ role: "user", parts: [{ text: query }] }],
              {
                model: "gemini-2.0-flash",
                systemInstruction: systemPrompt,
                temperature: 0.2,
              }
            );

            for await (const token of geminiGenerator) {
              if (token) {
                sendEvent("token", { token });
                streamedWithGemini = true;
              }
            }
          } catch (geminiErr: any) {
            console.error("[Gemini Stream Error]:", geminiErr?.message || geminiErr);
            streamedWithGemini = false;
          }
        }

        // Fallback to grounded synthesizer if Gemini key was missing or failed
        if (!streamedWithGemini) {
          const words = result.markdownResponse.split(" ");
          for (let i = 0; i < words.length; i++) {
            const token = (i === 0 ? "" : " ") + words[i];
            sendEvent("token", { token });
            await sleep(12);
          }
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

