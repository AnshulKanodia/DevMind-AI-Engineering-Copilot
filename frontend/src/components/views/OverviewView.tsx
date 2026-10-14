"use client";

import React from "react";
import {
  Search,
  ShieldCheck,
  FileCode2,
  GitPullRequest,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  FolderGit2,
  Cpu,
  Layers,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { NavTabId } from "@/components/layout/Sidebar";

export interface OverviewViewProps {
  onNavigate: (tab: NavTabId) => void;
  onConnectRepo: () => void;
}

export function OverviewView({ onNavigate, onConnectRepo }: OverviewViewProps) {
  const stats = [
    {
      title: "AST Semantic Chunks",
      value: "684",
      subtext: "142 files indexed (Python, TS, Go)",
      icon: Layers,
      color: "text-sky-400",
      bg: "bg-sky-500/10 border-sky-500/20",
    },
    {
      title: "Security & SAST Audits",
      value: "0 Critical",
      subtext: "Bandit, Semgrep, AST rules active",
      icon: ShieldCheck,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10 border-emerald-500/20",
    },
    {
      title: "Test Suites Generated",
      value: "28 Tests",
      subtext: "pytest with mock isolation",
      icon: FileCode2,
      color: "text-purple-400",
      bg: "bg-purple-500/10 border-purple-500/20",
    },
    {
      title: "PR Reviews & Autofixes",
      value: "100% Gated",
      subtext: "HMAC cryptographic approval tokens",
      icon: GitPullRequest,
      color: "text-amber-400",
      bg: "bg-amber-500/10 border-amber-500/20",
    },
  ];

  const agentWorkflows = [
    {
      id: "chat" as NavTabId,
      title: "Code Q&A Copilot",
      desc: "Ask queries like 'How does OAuth authentication work?' with exact file:line citations.",
      icon: Search,
      badge: "Dense + BM25 Hybrid",
      cta: "Launch Copilot",
    },
    {
      id: "security" as NavTabId,
      title: "SAST & Security Auditor",
      desc: "Deep AST inspection detecting SQL injection, insecure deserialization, and weak cryptography.",
      icon: ShieldCheck,
      badge: "OWASP Top 10",
      cta: "Run Audit",
    },
    {
      id: "tests" as NavTabId,
      title: "Unit Test & Doc Synthesizer",
      desc: "Produce isolated test fixtures with unittest.mock alongside Mermaid architecture diagrams.",
      icon: FileCode2,
      badge: "pytest & Jest",
      cta: "Generate Tests",
    },
    {
      id: "pr_review" as NavTabId,
      title: "PR Reviewer & Safe Autofixer",
      desc: "Unified diff parser that scores changes, posts inline comments, and requires Human-in-the-Loop tokens.",
      icon: GitPullRequest,
      badge: "Human-in-the-Loop",
      cta: "Review PR",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Welcome Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900/90 to-sky-950/40 p-6 md:p-8">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-sky-500/10 border border-sky-500/20 px-3 py-1 text-xs text-sky-300 font-medium">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Multi-Agent LangGraph System Online</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
            DevMind Developer Intelligence Center
          </h1>
          <p className="text-sm md:text-base text-slate-300 leading-relaxed">
            Welcome to your AI Engineering Copilot. Connect your GitHub repository to index code into syntax-aware AST chunks, run grounded conversational Q&A, detect vulnerabilities, and automate pull requests.
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button onClick={() => onNavigate("chat")} variant="glow" size="sm">
              Open Code Chat <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
            </Button>
            <Button onClick={onConnectRepo} variant="outline" size="sm">
              <FolderGit2 className="h-3.5 w-3.5 mr-1.5 text-sky-400" /> Connect Another Repo
            </Button>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <Card key={i} className="hover:border-slate-700 transition-colors">
              <CardContent className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-medium text-slate-400">{stat.title}</span>
                  <div className={`p-2 rounded-lg border ${stat.bg}`}>
                    <Icon className={`h-4 w-4 ${stat.color}`} />
                  </div>
                </div>
                <div className="text-2xl font-bold tracking-tight text-white mb-1">
                  {stat.value}
                </div>
                <p className="text-xs text-slate-400">{stat.subtext}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Workspaces & Agent Workflows */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white tracking-tight">Autonomous Copilot Modules</h2>
          <span className="text-xs text-slate-400">Click any module to launch workspace</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agentWorkflows.map((agent) => {
            const Icon = agent.icon;
            return (
              <Card
                key={agent.id}
                className="hover:border-sky-500/40 hover:bg-slate-900/70 transition-all cursor-pointer group"
                onClick={() => onNavigate(agent.id)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="h-9 w-9 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 group-hover:scale-105 transition-transform">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div>
                        <CardTitle className="text-base text-white group-hover:text-sky-300 transition-colors">
                          {agent.title}
                        </CardTitle>
                        <Badge variant="outline" className="text-[10px] mt-1">
                          {agent.badge}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <CardDescription className="text-xs text-slate-400 leading-relaxed">
                    {agent.desc}
                  </CardDescription>
                  <div className="flex items-center text-xs font-medium text-sky-400 group-hover:translate-x-1 transition-transform">
                    {agent.cta} <ArrowRight className="h-3 w-3 ml-1" />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
