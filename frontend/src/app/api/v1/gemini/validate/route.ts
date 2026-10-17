import { NextRequest, NextResponse } from "next/server";
import {
  validateGeminiApiKey,
  resolveGeminiApiKey,
  DEFAULT_MODEL_CONFIG,
} from "@/lib/geminiClient";

export const dynamic = "force-dynamic";

/**
 * Validates a Gemini API Key against Google's Generative Language API.
 * Supports keys passed in body, headers (x-gemini-key), or server environment.
 */
export async function POST(req: NextRequest) {
  try {
    let keyToValidate: string | null = null;
    let keySource: "body" | "header" | "env" = "env";

    // 1. Check body
    try {
      const body = await req.json();
      if (body?.apiKey && typeof body.apiKey === "string" && body.apiKey.trim().length > 10) {
        keyToValidate = body.apiKey.trim();
        keySource = "body";
      }
    } catch {
      // Body may be empty if testing server-configured key
    }

    // 2. Check headers or environment if not in body
    if (!keyToValidate) {
      const resolved = resolveGeminiApiKey(req.headers);
      if (resolved) {
        keyToValidate = resolved.key;
        keySource = resolved.source;
      }
    }

    if (!keyToValidate) {
      return NextResponse.json(
        {
          valid: false,
          error: "No Gemini API key provided in request or configured on server.",
        },
        { status: 400 }
      );
    }

    const result = await validateGeminiApiKey(keyToValidate);

    if (result.valid) {
      return NextResponse.json({
        valid: true,
        primaryModel: process.env.GEMINI_PRIMARY_MODEL || DEFAULT_MODEL_CONFIG.primaryModel,
        failoverModel: process.env.GEMINI_FAILOVER_MODEL || DEFAULT_MODEL_CONFIG.failoverModel,
        keySource,
        message: "Key successfully validated with Google AI Studio.",
      });
    }

    return NextResponse.json(
      {
        valid: false,
        error: result.error || "Failed to authenticate with Google AI Studio.",
      },
      { status: 200 }
    );
  } catch (err: any) {
    return NextResponse.json(
      {
        valid: false,
        error: err.message || "Internal validation error",
      },
      { status: 500 }
    );
  }
}
