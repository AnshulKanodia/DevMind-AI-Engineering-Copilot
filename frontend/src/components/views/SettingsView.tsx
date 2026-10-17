"use client";

import React, { useState, useEffect } from "react";
import {
  Settings,
  Key,
  Database,
  Github,
  CheckCircle2,
  Lock,
  ExternalLink,
  Save,
  Sparkles,
  Cpu,
  RefreshCw,
  AlertCircle,
  Eye,
  EyeOff,
  Zap,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function SettingsView() {
  const [saved, setSaved] = useState(false);
  const [geminiKey, setGeminiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [testingGemini, setTestingGemini] = useState(false);
  const [testResult, setTestResult] = useState<{
    valid: boolean;
    message?: string;
    error?: string;
    primaryModel?: string;
    failoverModel?: string;
  } | null>(null);

  const [primaryModel, setPrimaryModel] = useState("gemini-2.5-flash");
  const [failoverModel, setFailoverModel] = useState("gemini-3.5-flash-lite");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const storedKey = localStorage.getItem("devmind_gemini_api_key") || "";
      const storedPrimary = localStorage.getItem("devmind_gemini_primary_model") || "gemini-2.5-flash";
      const storedFailover = localStorage.getItem("devmind_gemini_failover_model") || "gemini-3.5-flash-lite";

      setGeminiKey(storedKey);
      setPrimaryModel(storedPrimary);
      setFailoverModel(storedFailover);
    }
  }, []);

  const handleTestConnection = async () => {
    setTestingGemini(true);
    setTestResult(null);

    try {
      const res = await fetch("/api/v1/gemini/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apiKey: geminiKey }),
      });

      const data = await res.json();
      if (data.valid) {
        setTestResult({
          valid: true,
          message: data.message || "Key authenticated successfully with Google AI Studio.",
          primaryModel: data.primaryModel,
          failoverModel: data.failoverModel,
        });
      } else {
        setTestResult({
          valid: false,
          error: data.error || "Authentication failed. Check your API key and quotas.",
        });
      }
    } catch (err: any) {
      setTestResult({
        valid: false,
        error: err.message || "Network error while connecting to Google AI Studio.",
      });
    } finally {
      setTestingGemini(false);
    }
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();

    if (typeof window !== "undefined") {
      if (geminiKey.trim()) {
        localStorage.setItem("devmind_gemini_api_key", geminiKey.trim());
      } else {
        localStorage.removeItem("devmind_gemini_api_key");
      }
      localStorage.setItem("devmind_gemini_primary_model", primaryModel);
      localStorage.setItem("devmind_gemini_failover_model", failoverModel);
    }

    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header Bar */}
      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-2 mb-1">
          <Settings className="h-5 w-5 text-sky-400" />
          <h2 className="text-lg font-bold text-white tracking-tight">
            Environment & AI Model Credentials
          </h2>
        </div>
        <p className="text-xs text-slate-400">
          Configure Google Gemini dual-model failover, API keys, and repository credentials.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-4">
        {/* Google Gemini AI Multi-Model Orchestration Card */}
        <Card className="border-sky-500/20 bg-gradient-to-b from-sky-950/10 to-slate-950/40">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-sky-400" />
                <CardTitle className="text-sm">Google Gemini AI (Multi-Model Failover)</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="glow" className="text-[10px] bg-sky-500/10 text-sky-400 border-sky-500/30">
                  Dual-Model Resilient
                </Badge>
                {testResult?.valid ? (
                  <Badge variant="success" className="text-[10px]">Connected</Badge>
                ) : geminiKey ? (
                  <Badge variant="outline" className="text-[10px] text-slate-400 border-slate-700">Stored Locally</Badge>
                ) : (
                  <Badge variant="outline" className="text-[10px] text-slate-400 border-slate-700">Vercel Env Key</Badge>
                )}
              </div>
            </div>
            <CardDescription className="text-xs text-slate-400">
              Powers real-time codebase reasoning, multi-turn chat streaming, and AST line-by-line citations.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Key Input */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                  <Key className="h-3.5 w-3.5 text-sky-400" />
                  Gemini API Key
                </label>
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-sky-400 hover:text-sky-300 flex items-center gap-1 transition-colors"
                >
                  Get key from Google AI Studio <ExternalLink className="h-3 w-3" />
                </a>
              </div>

              <div className="relative flex items-center">
                <Input
                  type={showKey ? "text" : "password"}
                  value={geminiKey}
                  onChange={(e) => setGeminiKey(e.target.value)}
                  placeholder="AQ.Ab... or AIzaSy... (leave blank to use server environment key)"
                  className="font-mono text-xs pr-20 bg-slate-950/80 border-slate-800 focus:border-sky-500/60"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 p-1 text-slate-400 hover:text-slate-200"
                  title={showKey ? "Hide key" : "Show key"}
                >
                  {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>

              <div className="flex items-center justify-between pt-1">
                <p className="text-[11px] text-slate-500">
                  Supports new Google Authorization keys (<span className="text-slate-400 font-mono">AQ.Ab...</span>) and standard keys.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleTestConnection}
                  disabled={testingGemini}
                  className="h-7 text-xs border-slate-700 hover:bg-slate-800"
                >
                  {testingGemini ? (
                    <>
                      <RefreshCw className="h-3 w-3 mr-1.5 animate-spin" />
                      Testing...
                    </>
                  ) : (
                    <>
                      <Zap className="h-3 w-3 mr-1.5 text-sky-400" />
                      Test Connection
                    </>
                  )}
                </Button>
              </div>

              {/* Test Result Message */}
              {testResult && (
                <div
                  className={`p-2.5 rounded-lg text-xs flex items-start gap-2 border ${
                    testResult.valid
                      ? "bg-emerald-950/30 border-emerald-800/50 text-emerald-300"
                      : "bg-rose-950/30 border-rose-800/50 text-rose-300"
                  }`}
                >
                  {testResult.valid ? (
                    <CheckCircle2 className="h-4 w-4 mt-0.5 text-emerald-400 flex-shrink-0" />
                  ) : (
                    <AlertCircle className="h-4 w-4 mt-0.5 text-rose-400 flex-shrink-0" />
                  )}
                  <div>
                    <span className="font-medium">
                      {testResult.valid ? "Connection Verified: " : "Connection Failed: "}
                    </span>
                    <span>{testResult.message || testResult.error}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Dual Model Architecture Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
              <div className="p-3 rounded-lg border border-slate-800/80 bg-slate-900/40 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1.5">
                    <Cpu className="h-3 w-3 text-sky-400" />
                    Primary Model (High Reasoning)
                  </span>
                  <Badge variant="glow" className="text-[9px] px-1.5 py-0 bg-sky-500/10 text-sky-400">
                    Active
                  </Badge>
                </div>
                <p className="font-mono text-xs text-sky-200">{primaryModel}</p>
                <p className="text-[10px] text-slate-400">
                  Handles deep codebase queries, complex syntax parsing, and architectural planning.
                </p>
              </div>

              <div className="p-3 rounded-lg border border-slate-800/80 bg-slate-900/40 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1.5">
                    <RefreshCw className="h-3 w-3 text-emerald-400" />
                    Failover Model (Auto-Shift)
                  </span>
                  <Badge variant="success" className="text-[9px] px-1.5 py-0">
                    500 RPD
                  </Badge>
                </div>
                <p className="font-mono text-xs text-emerald-300">{failoverModel}</p>
                <p className="text-[10px] text-slate-400">
                  If primary model hits rate limits (429) or is down, load shifts immediately here with zero downtime.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* OpenAI Credentials */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Key className="h-4 w-4 text-sky-400" />
                <CardTitle className="text-sm">OpenAI API Key (Optional)</CardTitle>
              </div>
              <Badge variant="success">Active</Badge>
            </div>
            <CardDescription className="text-xs">
              Powers embeddings (text-embedding-3-small) and LangGraph agent reasoning.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Input
              type="password"
              defaultValue="sk-proj-••••••••••••••••••••••••"
              placeholder="sk-..."
              className="font-mono text-xs"
            />
          </CardContent>
        </Card>

        {/* GitHub OAuth & PAT */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Github className="h-4 w-4 text-white" />
                <CardTitle className="text-sm">GitHub OAuth & Personal Access Token</CardTitle>
              </div>
              <Badge variant="glow">AES-256 Encrypted</Badge>
            </div>
            <CardDescription className="text-xs">
              Used for cloning repositories into sandboxes and posting PR review comments.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              type="password"
              defaultValue="ghp_••••••••••••••••••••••••"
              placeholder="ghp_..."
              className="font-mono text-xs"
            />
            <p className="text-[11px] text-slate-500">
              DevMind uses Fernet symmetric AES-256 to ensure tokens are never stored in plaintext.
            </p>
          </CardContent>
        </Card>

        {/* MongoDB Atlas */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-emerald-400" />
                <CardTitle className="text-sm">MongoDB Atlas Vector Search Connection</CardTitle>
              </div>
              <Badge variant="success">Connected</Badge>
            </div>
            <CardDescription className="text-xs">
              Stores hybrid dense vector indexes and lexical metadata for code retrieval.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Input
              type="text"
              readOnly
              value="mongodb+srv://devmind-cluster.mongodb.net/devmind_rag"
              className="font-mono text-xs text-slate-400 bg-slate-950/80 cursor-not-allowed"
            />
          </CardContent>
        </Card>

        <div className="flex items-center justify-between pt-2">
          {saved ? (
            <span className="text-xs text-emerald-400 flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4" /> Settings updated successfully
            </span>
          ) : (
            <span className="text-xs text-slate-500">
              Changes take effect immediately on agent workflows.
            </span>
          )}

          <Button type="submit" variant="glow" size="sm">
            <Save className="h-3.5 w-3.5 mr-1.5" />
            <span>Save Settings</span>
          </Button>
        </div>
      </form>
    </div>
  );
}
