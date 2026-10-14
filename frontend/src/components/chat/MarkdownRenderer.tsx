"use client";

import React, { useState } from "react";
import { Copy, Check, Terminal, FileCode } from "lucide-react";

export interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
  onOpenCitation?: (file: string, lines: string) => void;
}

export function MarkdownRenderer({
  content,
  isStreaming,
  onOpenCitation,
}: MarkdownRendererProps) {
  // Split content by code blocks (```lang ... ```)
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    const textBefore = content.substring(lastIndex, match.index);
    if (textBefore) {
      parts.push(
        <TextSection
          key={`text-${lastIndex}`}
          text={textBefore}
          onOpenCitation={onOpenCitation}
        />
      );
    }

    const language = match[1] || "text";
    const code = match[2];
    parts.push(
      <CodeBlock
        key={`code-${match.index}`}
        language={language}
        code={code}
      />
    );

    lastIndex = codeBlockRegex.lastIndex;
  }

  const remainingText = content.substring(lastIndex);
  if (remainingText) {
    if (remainingText.startsWith("```")) {
      const firstLineBreak = remainingText.indexOf("\n");
      const language = firstLineBreak !== -1 ? remainingText.substring(3, firstLineBreak) : "code";
      const code = firstLineBreak !== -1 ? remainingText.substring(firstLineBreak + 1) : "";
      parts.push(
        <CodeBlock
          key={`code-partial`}
          language={language}
          code={code}
          isPartial={true}
        />
      );
    } else {
      parts.push(
        <TextSection
          key={`text-remaining`}
          text={remainingText}
          onOpenCitation={onOpenCitation}
        />
      );
    }
  }

  return (
    <div className="space-y-3 leading-relaxed text-slate-200 text-xs md:text-sm">
      {parts}
      {isStreaming && (
        <span className="inline-block w-2 h-4 ml-1 bg-sky-400 animate-pulse align-middle" />
      )}
    </div>
  );
}

function TextSection({
  text,
  onOpenCitation,
}: {
  text: string;
  onOpenCitation?: (file: string, lines: string) => void;
}) {
  const lines = text.split("\n");

  return (
    <div className="space-y-2">
      {lines.map((line, idx) => {
        if (!line.trim()) {
          return <div key={idx} className="h-1.5" />;
        }

        if (line.startsWith("### ")) {
          return (
            <h4 key={idx} className="text-sm md:text-base font-bold text-white mt-3 mb-1">
              {formatInline(line.replace(/^###\s+/, ""), onOpenCitation)}
            </h4>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h3 key={idx} className="text-base md:text-lg font-bold text-white mt-4 mb-2 border-b border-slate-800 pb-1">
              {formatInline(line.replace(/^##\s+/, ""), onOpenCitation)}
            </h3>
          );
        }
        if (line.startsWith("# ")) {
          return (
            <h2 key={idx} className="text-lg md:text-xl font-extrabold text-white mt-4 mb-2">
              {formatInline(line.replace(/^#\s+/, ""), onOpenCitation)}
            </h2>
          );
        }

        if (line.match(/^[-*]\s+/)) {
          return (
            <div key={idx} className="flex items-start gap-2 pl-2">
              <span className="text-sky-400 mt-1">&bull;</span>
              <span className="flex-1">
                {formatInline(line.replace(/^[-*]\s+/, ""), onOpenCitation)}
              </span>
            </div>
          );
        }

        if (line.match(/^\d+\.\s+/)) {
          const numMatch = line.match(/^(\d+)\.\s+/);
          const num = numMatch ? numMatch[1] : "1";
          return (
            <div key={idx} className="flex items-start gap-2 pl-2">
              <span className="font-mono text-sky-400 font-semibold">{num}.</span>
              <span className="flex-1">
                {formatInline(line.replace(/^\d+\.\s+/, ""), onOpenCitation)}
              </span>
            </div>
          );
        }

        if (line.startsWith("> ")) {
          return (
            <div
              key={idx}
              className="border-l-2 border-sky-500 pl-3 py-1 my-1.5 italic text-slate-400 bg-sky-950/10 rounded-r"
            >
              {formatInline(line.replace(/^>\s+/, ""), onOpenCitation)}
            </div>
          );
        }

        return <p key={idx}>{formatInline(line, onOpenCitation)}</p>;
      })}
    </div>
  );
}

function CodeBlock({
  language,
  code,
  isPartial = false,
}: {
  language: string;
  code: string;
  isPartial?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const codeLines = code.trimEnd().split("\n");

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden my-3 shadow-lg">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-900/90 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-sky-400" />
          <span className="font-mono font-medium text-slate-300 text-[11px] uppercase tracking-wider">
            {language || "code"}
          </span>
          {isPartial && (
            <span className="text-[10px] text-amber-400 animate-pulse font-mono">
              (generating...)
            </span>
          )}
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Copy code snippet"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span className="text-emerald-400">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      <div className="p-3 overflow-x-auto text-xs font-mono bg-slate-950/90 leading-relaxed">
        <table className="w-full border-collapse">
          <tbody>
            {codeLines.map((line, i) => (
              <tr key={i} className="hover:bg-slate-900/40">
                <td className="pr-4 text-right text-slate-600 select-none w-8 text-[11px] align-top">
                  {i + 1}
                </td>
                <td className="text-slate-200 whitespace-pre">
                  {highlightSyntax(line, language)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function highlightSyntax(codeLine: string, language: string): React.ReactNode {
  if (!codeLine) return " ";

  if (codeLine.trim().startsWith("#")) {
    return <span className="text-slate-500 italic">{codeLine}</span>;
  }
  if (codeLine.trim().startsWith("//")) {
    return <span className="text-slate-500 italic">{codeLine}</span>;
  }

  return <span>{codeLine}</span>;
}

function formatInline(
  text: string,
  onOpenCitation?: (file: string, lines: string) => void
): React.ReactNode[] {
  const inlineRegex = /(\*\*.*?\*\*|`.*?`|\b(?:[a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+:\d+(?:-\d+)?)\b)/g;
  const elements: React.ReactNode[] = [];
  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = inlineRegex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      elements.push(text.substring(lastIdx, match.index));
    }

    const token = match[0];
    if (token.startsWith("**") && token.endsWith("**")) {
      elements.push(
        <strong key={match.index} className="text-white font-semibold">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith("`") && token.endsWith("`")) {
      elements.push(
        <code
          key={match.index}
          className="rounded bg-slate-800/80 px-1.5 py-0.5 font-mono text-[11px] text-sky-300 border border-slate-700/60"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.includes(":") && token.includes(".")) {
      const parts = token.split(":");
      const file = parts[0];
      const lines = parts[1] || "1-30";
      elements.push(
        <span
          key={match.index}
          onClick={() => onOpenCitation?.(file, lines)}
          className="inline-flex items-center gap-1 rounded bg-sky-500/10 hover:bg-sky-500/20 px-1.5 py-0.5 font-mono text-[11px] text-sky-400 border border-sky-500/20 cursor-pointer transition-colors"
          title={`Click to preview citation ${token}`}
        >
          <FileCode className="h-3 w-3" />
          {token}
        </span>
      );
    }

    lastIdx = inlineRegex.lastIndex;
  }

  if (lastIdx < text.length) {
    elements.push(text.substring(lastIdx));
  }

  return elements.length > 0 ? elements : [text];
}
