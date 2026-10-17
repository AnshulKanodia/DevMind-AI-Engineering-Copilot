/**
 * Google Gemini Streaming Client for DevMind AI Engineering Copilot.
 * Integrates natively with the Google Generative Language REST API.
 * Supports gemini-1.5-flash, gemini-2.0-flash, and dual-mode key resolution.
 */

export interface GeminiMessage {
  role: "user" | "model";
  parts: Array<{ text: string }>;
}

export interface GeminiStreamOptions {
  model?: string;
  systemInstruction?: string;
  temperature?: number;
  maxOutputTokens?: number;
  signal?: AbortSignal;
}

export interface ResolvedGeminiKey {
  key: string;
  source: "header" | "env";
}

/**
 * Resolves the Google Gemini API key from incoming request headers or environment variables.
 * Priority:
 * 1. Client header: `x-gemini-key` or `x-ai-key`
 * 2. Environment variable: `GEMINI_API_KEY` or `GOOGLE_API_KEY`
 */
export function resolveGeminiApiKey(headers?: Headers): ResolvedGeminiKey | null {
  if (headers) {
    const headerKey = headers.get("x-gemini-key") || headers.get("x-ai-key");
    if (headerKey && headerKey.trim().length > 10) {
      return { key: headerKey.trim(), source: "header" };
    }
  }

  const envKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  if (envKey && envKey.trim().length > 10) {
    return { key: envKey.trim(), source: "env" };
  }

  return null;
}

/**
 * Validates a Gemini API key by making a lightweight test ping to list models.
 */
export async function validateGeminiApiKey(apiKey: string): Promise<{ valid: boolean; error?: string }> {
  if (!apiKey || apiKey.trim().length < 10) {
    return { valid: false, error: "API key is empty or too short." };
  }

  try {
    const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey.trim()}`;
    const res = await fetch(url, { method: "GET" });
    if (res.ok) {
      return { valid: true };
    }
    const errData = await res.json().catch(() => ({}));
    const message = errData?.error?.message || `HTTP ${res.status}: ${res.statusText}`;
    return { valid: false, error: message };
  } catch (err: any) {
    return { valid: false, error: err.message || "Network connection failed." };
  }
}

/**
 * Streams tokens from Google Gemini via Server-Sent Events (SSE) chunks.
 * Yields individual text tokens as they arrive from the Google AI model.
 */
export async function* streamGeminiChat(
  apiKey: string,
  messages: GeminiMessage[],
  options: GeminiStreamOptions = {}
): AsyncGenerator<string, void, unknown> {
  const model = options.model || "gemini-2.5-flash";
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:streamGenerateContent?alt=sse&key=${apiKey.trim()}`;

  const payload: Record<string, any> = {
    contents: messages,
    generationConfig: {
      temperature: options.temperature ?? 0.2,
      maxOutputTokens: options.maxOutputTokens ?? 2048,
    },
  };

  if (options.systemInstruction) {
    payload.systemInstruction = {
      parts: [{ text: options.systemInstruction }],
    };
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "");
    let errorMessage = `Gemini API error (${response.status}): ${response.statusText}`;
    try {
      const parsed = JSON.parse(errorBody);
      if (parsed.error?.message) {
        errorMessage = parsed.error.message;
      }
    } catch {
      // Keep fallback message
    }
    throw new Error(errorMessage);
  }

  if (!response.body) {
    throw new Error("Gemini API response body is empty.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;

      const jsonStr = trimmed.replace(/^data:\s*/, "");
      if (!jsonStr || jsonStr === "[DONE]") continue;

      try {
        const parsed = JSON.parse(jsonStr);
        const candidates = parsed.candidates;
        if (candidates && candidates.length > 0) {
          const parts = candidates[0].content?.parts;
          if (parts && parts.length > 0) {
            for (const part of parts) {
              if (part.text) {
                yield part.text;
              }
            }
          }
        }
      } catch {
        // Partial chunk; ignore until next line completes
      }
    }
  }

  if (buffer.trim().startsWith("data:")) {
    try {
      const jsonStr = buffer.trim().replace(/^data:\s*/, "");
      const parsed = JSON.parse(jsonStr);
      const text = parsed.candidates?.[0]?.content?.parts?.[0]?.text;
      if (text) yield text;
    } catch {
      // End of stream
    }
  }
}
