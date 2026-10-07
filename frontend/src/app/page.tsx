import React from "react";
import { 
  Terminal, 
  ShieldCheck, 
  FileCode2, 
  GitPullRequest, 
  Cpu, 
  Search, 
  Layers, 
  ArrowRight 
} from "lucide-react";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-6 md:p-12 max-w-7xl mx-auto">
      {/* Header */}
      <header className="w-full flex items-center justify-between py-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <Cpu className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">DevMind</h1>
            <p className="text-xs text-slate-400">AI Engineering Copilot</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Backend API Active
          </span>
          <button className="px-4 py-2 text-sm font-medium rounded-lg bg-sky-600 hover:bg-sky-500 text-white transition-colors">
            Connect GitHub
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="my-16 text-center max-w-3xl">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-300 text-xs font-medium mb-6">
          <Layers className="h-3.5 w-3.5" />
          AST Parsing + MongoDB Atlas Vector Search + LangGraph
        </div>
        <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-white mb-6 leading-tight">
          Intelligent Copilot for Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-sky-400 to-indigo-400">Entire Codebase</span>
        </h2>
        <p className="text-base md:text-lg text-slate-400 mb-8 leading-relaxed">
          DevMind ingests GitHub repositories, preserves semantic code structure using language-aware AST parsing, and orchestrates specialized multi-agent workflows to navigate, review, and refactor code.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4">
          <button className="px-6 py-3 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-medium text-sm flex items-center gap-2 transition-all shadow-lg shadow-sky-600/20">
            Get Started <ArrowRight className="h-4 w-4" />
          </button>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="px-6 py-3 rounded-lg border border-slate-700 hover:border-slate-600 text-slate-300 font-medium text-sm transition-colors"
          >
            Explore FastAPI Docs
          </a>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 w-full my-8">
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-colors">
          <div className="h-10 w-10 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 mb-4">
            <Search className="h-5 w-5" />
          </div>
          <h3 className="text-base font-semibold text-white mb-2">Code Q&A with Citations</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Ask natural language questions and get grounded answers citing exact file lines from your repository.
          </p>
        </div>

        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-colors">
          <div className="h-10 w-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <h3 className="text-base font-semibold text-white mb-2">Hybrid SAST Bug Scanning</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Combines Bandit and ESLint static analysis with LLM reasoning to pinpoint vulnerabilities and filter false positives.
          </p>
        </div>

        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-colors">
          <div className="h-10 w-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 mb-4">
            <FileCode2 className="h-5 w-5" />
          </div>
          <h3 className="text-base font-semibold text-white mb-2">Unit Test & Doc Synthesis</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Generate runnable pytest/Jest test scaffolds with mock fixtures and auto-produce module architecture diagrams.
          </p>
        </div>

        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-colors">
          <div className="h-10 w-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-4">
            <GitPullRequest className="h-5 w-5" />
          </div>
          <h3 className="text-base font-semibold text-white mb-2">PR Review & Automation</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Inspect pull request diffs, highlight breaking changes, and draft auto-fix branches gated by human approvals.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="w-full py-6 mt-12 border-t border-slate-800 flex flex-col md:flex-row items-center justify-between text-xs text-slate-500 gap-4">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-sky-400" />
          <span>DevMind Architecture &copy; 2026. All rights reserved.</span>
        </div>
        <div className="flex gap-6">
          <span>LangGraph Orchestration</span>
          <span>MongoDB Atlas Vector Search</span>
          <span>FastAPI</span>
          <span>Next.js 14</span>
        </div>
      </footer>
    </main>
  );
}
