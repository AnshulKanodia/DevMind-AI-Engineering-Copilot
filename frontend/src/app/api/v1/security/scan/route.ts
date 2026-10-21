import { NextRequest } from "next/server";
import { resolveGeminiApiKey } from "@/lib/geminiClient";
import { performSecurityAudit } from "@/lib/geminiSecurityScanner";

export const dynamic = "force-dynamic";

/**
 * Serverless API route handler for DevMind Autonomous Security & SAST Auditing.
 * Runs deterministic code heuristics combined with Gemini AI multi-model reasoning.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const repo_id = body.repo_id || body.repo_url || "AnshulKanodia/DevMind-AI-Engineering-Copilot";
    const branch = body.branch || "main";

    // 1. Resolve Gemini API Key (headers or serverless env)
    const geminiKey = resolveGeminiApiKey(req.headers);

    // 2. Read custom model preferences if supplied
    const clientPrimary = req.headers.get("x-gemini-primary-model") || undefined;
    const clientFailover = req.headers.get("x-gemini-failover-model") || undefined;

    // 3. Execute comprehensive security audit
    const scanResult = await performSecurityAudit(repo_id, branch, geminiKey?.key, {
      primaryModel: clientPrimary,
      failoverModel: clientFailover,
    });

    return new Response(JSON.stringify(scanResult), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (err: any) {
    console.error("[Security Scan API Error]:", err?.message || err);
    return new Response(
      JSON.stringify({
        error: err?.message || "Internal error during security audit scan",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
