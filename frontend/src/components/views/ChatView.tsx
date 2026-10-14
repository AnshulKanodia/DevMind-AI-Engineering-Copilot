"use client";

import React, { useState } from "react";
import {
  Send,
  Sparkles,
  Bot,
  User,
  Code2,
  FileText,
  Copy,
  Check,
  ExternalLink,
  CornerDownLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function ChatView() {
  const [copied, setCopied] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I am **DevMind**, your AI Engineering Copilot. I have indexed your repository AST into MongoDB Atlas Vector Search. You can ask me how specific modules work, request refactorings, or debug runtime logic with exact source citations.",
      citations: [
        { file: "backend/app/services/ast_parser.py", lines: "42-88", type: "class" },
        { file: "backend/app/agents/graph.py", lines: "115-160", type: "router" },
      ],
    },
  ]);

  const sampleQuestions = [
    "How does the hybrid BM25 + dense vector search work?",
    "Where is the GitHub AES-256 OAuth token decrypted?",
    "Explain the Human-in-the-Loop approval token generation logic.",
    "Show me how secrets are redacted before AST vector indexing.",
  ];

  const handleSend = () => {
    if (!input.trim()) return;
    const userText = input;
    setInput("");

    setMessages((prev) => [
      ...prev,
      { role: "user", content: userText, citations: [] },
      {
        role: "assistant",
        content: `I've analyzed the codebase for: "${userText}". In DevMind, this workflow routes via the LangGraph state graph to evaluate AST chunks retrieved through hybrid dense vector search and BM25 Okapi lexical scoring.`,
        citations: [
          { file: "backend/app/services/hybrid_search.py", lines: "24-65", type: "method" },
          { file: "backend/app/schemas/agent_state.py", lines: "12-40", type: "schema" },
        ],
      },
    ]);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(text);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] rounded-xl border border-slate-800 bg-slate-950/60 overflow-hidden">
      {/* Chat Header Bar */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/40">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-sky-400" />
          <span className="text-xs font-semibold text-white">Interactive Copilot Console</span>
          <Badge variant="glow" className="text-[10px]">
            Server-Sent Events Active
          </Badge>
        </div>
        <div className="text-[11px] text-slate-400">
          Model: <span className="text-sky-300 font-mono">gpt-4o-mini</span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-5">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex gap-3 max-w-4xl ${
              msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
            }`}
          >
            <div
              className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white"
                  : "bg-sky-500/10 border border-sky-500/20 text-sky-400"
              }`}
            >
              {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>

            <div
              className={`space-y-3 rounded-xl p-4 text-xs md:text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-indigo-600/20 border border-indigo-500/30 text-white"
                  : "bg-slate-900/70 border border-slate-800 text-slate-200"
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>

              {/* Citations Box */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="pt-2 border-t border-slate-800/80 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400">
                    <FileText className="h-3.5 w-3.5 text-sky-400" />
                    <span>Verified AST Code Citations:</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {msg.citations.map((cite, cIdx) => (
                      <div
                        key={cIdx}
                        className="flex items-center gap-1 px-2 py-1 rounded bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 hover:border-sky-500/40 transition-colors"
                      >
                        <Code2 className="h-3 w-3 text-sky-400" />
                        <span>{cite.file}</span>
                        <span className="text-sky-400">:{cite.lines}</span>
                        <button
                          onClick={() => copyToClipboard(`${cite.file}:${cite.lines}`)}
                          className="ml-1 text-slate-500 hover:text-slate-200"
                          title="Copy citation reference"
                        >
                          {copied === `${cite.file}:${cite.lines}` ? (
                            <Check className="h-2.5 w-2.5 text-emerald-400" />
                          ) : (
                            <Copy className="h-2.5 w-2.5" />
                          )}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Suggested Queries */}
      <div className="px-4 py-2 border-t border-slate-800/60 bg-slate-950/40 flex items-center gap-2 overflow-x-auto">
        <span className="text-[10px] text-slate-500 uppercase font-semibold whitespace-nowrap">
          Suggestions:
        </span>
        {sampleQuestions.map((q, i) => (
          <button
            key={i}
            onClick={() => setInput(q)}
            className="text-[11px] text-slate-300 hover:text-sky-300 whitespace-nowrap px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Input Bar */}
      <div className="p-4 border-t border-slate-800 bg-slate-900/60">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about the repository or requested refactoring..."
            className="flex-1 h-10 px-4 rounded-lg border border-slate-700 bg-slate-950 text-slate-100 placeholder:text-slate-500 text-xs md:text-sm focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500"
          />
          <Button type="submit" size="default" variant="glow" disabled={!input.trim()}>
            <Send className="h-4 w-4 mr-1.5" />
            <span>Send</span>
          </Button>
        </form>
      </div>
    </div>
  );
}
