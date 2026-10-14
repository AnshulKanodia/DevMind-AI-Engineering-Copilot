"use client";

import React, { useState } from "react";
import {
  Settings,
  Key,
  Database,
  Github,
  CheckCircle2,
  Lock,
  ExternalLink,
  Save,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function SettingsView() {
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
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
            Environment & Integration Credentials
          </h2>
        </div>
        <p className="text-xs text-slate-400">
          Configure API credentials, GitHub OAuth tokens, and vector database connections.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-4">
        {/* OpenAI Credentials */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Key className="h-4 w-4 text-sky-400" />
                <CardTitle className="text-sm">OpenAI API Key</CardTitle>
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
