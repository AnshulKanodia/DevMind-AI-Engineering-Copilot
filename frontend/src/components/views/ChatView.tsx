"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Sparkles,
  Bot,
  User,
  Code2,
  FileText,
  Copy,
  Check,
  StopCircle,
  RotateCcw,
  Zap,
  ShieldAlert,
  FileCode2,
  GitPullRequestDraft,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";
import { AgentThoughtTimeline } from "@/components/chat/AgentThoughtTimeline";
import {
  streamAgentChat,
  AgentThought,
} from "@/lib/chatStream";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  thoughts?: AgentThought[];
  citations?: Array<{ file: string; lines: string; type: string }>;
  isStreaming?: boolean;
}

export interface ChatViewProps {
  currentRepo?: string;
  currentBranch?: string;
  onOpenCitation?: (file: string, lines: string) => void;
}

function getInitialWelcomeMessage(repo: string): ChatMessage {
  return {
    id: "msg-welcome",
    role: "assistant",
    content: `### Welcome to DevMind Copilot 👋\n\nI am your **AI Engineering Copilot**, grounded directly on **${repo}**.\n\nAsk me about required environment configuration, architecture, dependencies, security posture, or test generation. I inspect connected repositories in real-time to provide verified, grounded answers!`,
    citations: [],
  };
}

export function ChatView({
  currentRepo = "AnshulKanodia/DevMind-AI-Engineering-Copilot",
  currentBranch = "main",
  onOpenCitation,
}: ChatViewProps) {
  const [copiedCitation, setCopiedCitation] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([
    getInitialWelcomeMessage(currentRepo),
  ]);

  useEffect(() => {
    // When connected repo changes, reset greeting if only welcome message is present
    setMessages((prev) => {
      if (prev.length <= 1) {
        return [getInitialWelcomeMessage(currentRepo)];
      }
      return prev;
    });
  }, [currentRepo]);

  const promptCategories = [
    {
      category: "Environment",
      icon: Search,
      prompt: "What environment variables do I need?",
    },
    {
      category: "Architecture",
      icon: Search,
      prompt: "How is the project structured and what are the core dependencies?",
    },
    {
      category: "Database",
      icon: FileCode2,
      prompt: "What database, ORM, or data models does this project use?",
    },
    {
      category: "Security",
      icon: ShieldAlert,
      prompt: "How does this project handle authentication, sessions, and security?",
    },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || input;
    if (!textToSend.trim() || isStreaming) return;

    setInput("");
    setIsStreaming(true);

    const userMessageId = "user-" + Date.now();
    const assistantMessageId = "asst-" + Date.now();

    // Append user message and blank assistant message
    setMessages((prev) => [
      ...prev,
      {
        id: userMessageId,
        role: "user",
        content: textToSend,
      },
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        thoughts: [],
        citations: [],
        isStreaming: true,
      },
    ]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await streamAgentChat(
        textToSend,
        currentRepo,
        {
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: m.content + token }
                  : m
              )
            );
          },
          onThought: (thought) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? {
                      ...m,
                      thoughts: [
                        ...(m.thoughts || []).filter((t) => t.node !== thought.node),
                        thought,
                      ],
                    }
                  : m
              )
            );
          },
          onCitations: (citations) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, citations: citations }
                  : m
              )
            );
          },
          onDone: () => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, isStreaming: false }
                  : m
              )
            );
            setIsStreaming(false);
          },
          onError: (err) => {
            console.error("Stream error:", err);
            setIsStreaming(false);
          },
        },
        controller.signal
      );
    } catch (err) {
      console.error("Failed to run streaming chat:", err);
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
    }
  };

  const handleClear = () => {
    if (isStreaming) handleStop();
    setMessages([
      {
        id: "msg-welcome-new",
        role: "assistant",
        content: `Conversation reset. I am ready to explore **${currentRepo}** on branch **${currentBranch}**. What would you like to examine?`,
        citations: [],
      },
    ]);
  };

  const copyCitation = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCitation(text);
    setTimeout(() => setCopiedCitation(null), 2000);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] rounded-xl border border-slate-800 bg-slate-950/70 overflow-hidden shadow-2xl">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <span className="text-xs font-bold text-white block">
              Multi-Agent Code Q&A Console
            </span>
            <span className="text-[10px] text-slate-400 font-mono">
              Repo: {currentRepo} &bull; {currentBranch}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="glow" className="text-[10px] hidden sm:inline-flex">
            <Zap className="h-3 w-3 mr-1 text-sky-400" /> SSE Streaming
          </Badge>

          <Button
            size="sm"
            variant="ghost"
            onClick={handleClear}
            className="text-xs h-7 text-slate-400 hover:text-white"
            title="Clear conversation"
          >
            <RotateCcw className="h-3.5 w-3.5 mr-1" />
            <span className="hidden sm:inline">Clear</span>
          </Button>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 max-w-4xl ${
              msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
            }`}
          >
            {/* Avatar */}
            <div
              className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 shadow-sm ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white"
                  : "bg-sky-500/10 border border-sky-500/30 text-sky-400"
              }`}
            >
              {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>

            {/* Bubble Content */}
            <div
              className={`space-y-3 rounded-2xl p-4 md:p-5 max-w-[85vw] md:max-w-3xl leading-relaxed shadow-sm ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white rounded-tr-none text-xs md:text-sm"
                  : "bg-slate-900/80 border border-slate-800 text-slate-200 rounded-tl-none"
              }`}
            >
              {/* Agent Thought Timeline (if assistant message has thoughts) */}
              {msg.role === "assistant" && msg.thoughts && msg.thoughts.length > 0 && (
                <AgentThoughtTimeline
                  thoughts={msg.thoughts}
                  isStreaming={msg.isStreaming}
                />
              )}

              {/* Message Markdown Body */}
              {msg.role === "assistant" ? (
                <MarkdownRenderer
                  content={msg.content || (msg.isStreaming ? "Thinking..." : "")}
                  isStreaming={msg.isStreaming}
                  onOpenCitation={onOpenCitation}
                />
              ) : (
                <div className="whitespace-pre-wrap">{msg.content}</div>
              )}

              {/* Verified Code Citations Drawer Pills */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="pt-3 border-t border-slate-800/80 space-y-2 mt-2">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400">
                    <FileText className="h-3.5 w-3.5 text-sky-400" />
                    <span>Verified AST Code Citations:</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {msg.citations.map((cite, cIdx) => {
                      const fullRef = `${cite.file}:${cite.lines}`;
                      return (
                        <div
                          key={cIdx}
                          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 hover:border-sky-500/50 transition-colors group cursor-pointer"
                          onClick={() => onOpenCitation?.(cite.file, cite.lines)}
                          title="Click to preview citation"
                        >
                          <Code2 className="h-3 w-3 text-sky-400" />
                          <span className="truncate max-w-[220px]">{cite.file}</span>
                          <span className="text-sky-400 font-semibold">:{cite.lines}</span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              copyCitation(fullRef);
                            }}
                            className="ml-1 text-slate-500 hover:text-white"
                            title="Copy reference"
                          >
                            {copiedCitation === fullRef ? (
                              <Check className="h-3 w-3 text-emerald-400" />
                            ) : (
                              <Copy className="h-3 w-3" />
                            )}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompts Shelf */}
      <div className="px-4 py-2 border-t border-slate-800/60 bg-slate-950/60 flex items-center gap-2 overflow-x-auto">
        <span className="text-[10px] text-slate-500 uppercase font-semibold whitespace-nowrap">
          Suggestions:
        </span>
        {promptCategories.map((item, i) => {
          const Icon = item.icon;
          return (
            <button
              key={i}
              type="button"
              disabled={isStreaming}
              onClick={() => handleSend(item.prompt)}
              className="inline-flex items-center gap-1.5 text-[11px] text-slate-300 hover:text-sky-300 whitespace-nowrap px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors disabled:opacity-50"
            >
              <Icon className="h-3 w-3 text-sky-400" />
              <span>{item.category}: {item.prompt}</span>
            </button>
          );
        })}
      </div>

      {/* Input Bar */}
      <div className="p-3.5 border-t border-slate-800 bg-slate-900/70">
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
            disabled={isStreaming}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              isStreaming
                ? "DevMind multi-agent is streaming response..."
                : `Ask a question about ${currentRepo} (or test refactorings, security reviews, unit tests)...`
            }
            className="flex-1 h-10 px-4 rounded-lg border border-slate-700 bg-slate-950 text-slate-100 placeholder:text-slate-500 text-xs md:text-sm focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 disabled:opacity-50"
          />

          {isStreaming ? (
            <Button
              type="button"
              variant="destructive"
              size="default"
              onClick={handleStop}
              className="flex items-center gap-1.5 text-xs font-semibold"
            >
              <StopCircle className="h-4 w-4" />
              <span>Stop</span>
            </Button>
          ) : (
            <Button
              type="submit"
              size="default"
              variant="glow"
              disabled={!input.trim()}
              className="flex items-center gap-1.5 text-xs font-semibold"
            >
              <Send className="h-3.5 w-3.5" />
              <span>Send</span>
            </Button>
          )}
        </form>
      </div>
    </div>
  );
}
