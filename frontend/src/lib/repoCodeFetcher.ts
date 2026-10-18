/**
 * DevMind GitHub Recursive Code Tree Manifest & Semantic Source Reader
 * Autonomously inspects real repository code trees, ranks source files matching
 * the developer's query, and extracts grounded line-numbered code snippets for Gemini.
 */

import { parseGithubRepo, isDevMindRepo } from "./repoKnowledge.ts";

export interface CodeSnippet {
  path: string;
  content: string;
  startLine: number;
  endLine: number;
  score?: number;
}

const IGNORED_DIRECTORIES = [
  "node_modules/",
  ".git/",
  "dist/",
  "build/",
  ".next/",
  "vendor/",
  "coverage/",
  "target/",
  "out/",
  "bin/",
  "obj/",
  "__pycache__/",
  ".pytest_cache/",
  ".venv/",
  "venv/",
];

const IGNORED_EXTENSIONS = [
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".svg",
  ".ico",
  ".woff",
  ".woff2",
  ".ttf",
  ".eot",
  ".mp4",
  ".mp3",
  ".pdf",
  ".zip",
  ".tar",
  ".gz",
  ".lock",
  "package-lock.json",
  "yarn.lock",
  "pnpm-lock.yaml",
  ".min.js",
  ".min.css",
  ".map",
];

const CODE_EXTENSIONS = new Set([
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".py",
  ".go",
  ".rs",
  ".java",
  ".cpp",
  ".c",
  ".h",
  ".hpp",
  ".cs",
  ".rb",
  ".php",
  ".swift",
  ".kt",
  ".scala",
  ".sql",
  ".prisma",
  ".json",
  ".yaml",
  ".yml",
  ".toml",
  ".sh",
]);

/**
 * Fetches the recursive git tree manifest of a GitHub repository.
 * Returns an array of clean relative source file paths.
 */
export async function fetchRepoTreeManifest(
  owner: string,
  repo: string,
  options: { branch?: string; maxFiles?: number } = {}
): Promise<string[]> {
  const branches = options.branch ? [options.branch] : ["main", "master", "dev"];
  const headers: Record<string, string> = {
    "User-Agent": "DevMind-Copilot",
    Accept: "application/vnd.github.v3+json",
  };

  const ghToken = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (ghToken) {
    headers["Authorization"] = `Bearer ${ghToken.trim()}`;
  }

  for (const branch of branches) {
    try {
      const url = `https://api.github.com/repos/${owner}/${repo}/git/trees/${branch}?recursive=1`;
      const res = await fetch(url, { headers });

      if (res.ok) {
        const data = await res.json();
        if (data && Array.isArray(data.tree)) {
          const files: string[] = [];

          for (const item of data.tree) {
            if (item.type !== "blob" || !item.path) continue;
            const path: string = item.path;

            // Skip ignored directories
            if (IGNORED_DIRECTORIES.some((dir) => path.includes(dir))) continue;

            // Skip ignored extensions
            if (IGNORED_EXTENSIONS.some((ext) => path.toLowerCase().endsWith(ext))) continue;

            files.push(path);
            if (options.maxFiles && files.length >= options.maxFiles) break;
          }

          if (files.length > 0) {
            return files;
          }
        }
      }
    } catch {
      // Continue searching next branch
    }
  }

  return [];
}

/**
 * Extracts meaningful keyword tokens from developer queries for code retrieval.
 */
export function extractQueryKeywords(query: string): string[] {
  if (!query) return [];

  // Stop words to remove
  const stopWords = new Set([
    "a", "an", "the", "in", "on", "of", "to", "for", "with", "at", "by", "from",
    "is", "are", "was", "were", "what", "how", "where", "which", "why", "who",
    "can", "could", "should", "would", "does", "do", "did", "please", "tell",
    "me", "about", "show", "explain", "code", "repo", "project", "this", "that",
  ]);

  const tokens = query
    .toLowerCase()
    .replace(/[^\w\s-]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 1 && !stopWords.has(t));

  const stems: string[] = [];
  for (const token of tokens) {
    stems.push(token);
    // Add common software stems/synonyms
    if (token.startsWith("auth")) stems.push("auth", "login", "jwt", "user", "session");
    if (token.startsWith("rout")) stems.push("api", "endpoint", "controller");
    if (token.startsWith("db") || token.includes("database")) stems.push("model", "schema", "prisma", "sql");
    if (token.includes("stream")) stems.push("sse", "event", "chunk");
    if (token.includes("test")) stems.push("spec", "mock");
    if (token.includes("config")) stems.push("setting", "env");
  }

  return Array.from(new Set(stems));
}

/**
 * Ranks repository file paths based on relevance to developer query tokens.
 */
export function rankRelevantFiles(
  query: string,
  filePaths: string[],
  limit: number = 4
): string[] {
  if (!filePaths || filePaths.length === 0) return [];
  const keywords = extractQueryKeywords(query);

  const scored = filePaths.map((path) => {
    let score = 0;
    const lowerPath = path.toLowerCase();
    const parts = lowerPath.split("/");
    const filename = parts[parts.length - 1];
    const ext = filename.slice(filename.lastIndexOf("."));

    // Code extension bonus
    if (CODE_EXTENSIONS.has(ext)) {
      score += 2;
    }

    // Direct entry point bonus
    if (
      filename.startsWith("main.") ||
      filename.startsWith("index.") ||
      filename.startsWith("app.") ||
      filename.startsWith("server.")
    ) {
      score += 3;
    }

    // Keyword matches
    for (const kw of keywords) {
      if (filename.includes(kw)) {
        score += 8; // High weight for exact filename match
      } else if (lowerPath.includes(kw)) {
        score += 4; // Moderate weight for path match
      }
    }

    return { path, score };
  });

  // Sort by score descending, secondary sort by depth (prefer src/ or app/ roots)
  scored.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.path.length - b.path.length;
  });

  return scored.slice(0, limit).map((s) => s.path);
}

/**
 * Fetches the raw content of a source file from GitHub across default branches.
 * Automatically bounds output to `maxLines` to preserve context budget.
 */
export async function fetchSourceFileContent(
  owner: string,
  repo: string,
  filePath: string,
  options: { maxLines?: number; branch?: string } = {}
): Promise<CodeSnippet | null> {
  const maxLines = options.maxLines || 200;
  const branches = options.branch ? [options.branch] : ["main", "master", "dev"];

  for (const branch of branches) {
    try {
      const url = `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${filePath}`;
      const res = await fetch(url, { headers: { "User-Agent": "DevMind-Copilot" } });

      if (res.ok) {
        const text = await res.text();
        const allLines = text.split("\n");
        const boundedLines = allLines.slice(0, maxLines);
        const endLine = boundedLines.length;

        // Number each line for precise citations
        const numberedCode = boundedLines
          .map((line, idx) => `${idx + 1}: ${line}`)
          .join("\n");

        return {
          path: filePath,
          content: numberedCode,
          startLine: 1,
          endLine: endLine,
        };
      }
    } catch {
      // Continue
    }
  }

  return null;
}

/**
 * Autonomous Source Code Retriever:
 * Fetches the repository manifest, ranks relevant source files matching the query,
 * and downloads grounded line-numbered code snippets.
 */
export async function fetchRelevantSourceSnippets(
  repoId: string,
  query: string,
  options: { maxSnippets?: number; maxLines?: number } = {}
): Promise<CodeSnippet[]> {
  const maxSnippets = options.maxSnippets || 3;
  const maxLines = options.maxLines || 150;

  // Handle DevMind internal codebase directly
  if (isDevMindRepo(repoId)) {
    return [
      {
        path: "backend/app/services/ast_parser.py",
        startLine: 42,
        endLine: 88,
        content:
          "42: class ASTLanguageAwareChunker:\n43:     def parse_and_chunk(self, source_code: str, language: str) -> List[CodeChunk]:\n44:         \"\"\"Extracts syntactically complete functions, classes, and types.\"\"\"",
      },
      {
        path: "backend/app/services/hybrid_retriever.py",
        startLine: 24,
        endLine: 65,
        content:
          "24: class HybridRetriever:\n25:     def search(self, query: str, alpha: float = 0.5) -> List[ScoredChunk]:\n26:         \"\"\"Calculates CombinedScore = alpha * DenseScore + (1 - alpha) * BM25Score.\"\"\"",
      },
    ];
  }

  const parsed = parseGithubRepo(repoId);
  if (!parsed) return [];

  const { owner, repo } = parsed;

  try {
    // 1. Fetch file tree manifest
    const manifest = await fetchRepoTreeManifest(owner, repo, { maxFiles: 500 });
    if (!manifest || manifest.length === 0) return [];

    // 2. Rank most relevant files
    const targetPaths = rankRelevantFiles(query, manifest, maxSnippets);
    if (targetPaths.length === 0) return [];

    // 3. Parallel fetch of actual source code
    const snippetPromises = targetPaths.map((filePath) =>
      fetchSourceFileContent(owner, repo, filePath, { maxLines })
    );

    const results = await Promise.all(snippetPromises);
    return results.filter((s): s is CodeSnippet => s !== null);
  } catch (err) {
    console.warn(`[DevMind Code Fetcher] Failed to retrieve snippets for ${repoId}:`, err);
    return [];
  }
}
