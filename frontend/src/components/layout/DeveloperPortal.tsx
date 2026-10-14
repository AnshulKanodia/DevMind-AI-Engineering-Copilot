"use client";

import React, { useState } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar, NavTabId } from "@/components/layout/Sidebar";
import { OverviewView } from "@/components/views/OverviewView";
import { ChatView } from "@/components/views/ChatView";
import { SecurityView } from "@/components/views/SecurityView";
import { TestsView } from "@/components/views/TestsView";
import { PRReviewView } from "@/components/views/PRReviewView";
import { RepoView } from "@/components/views/RepoView";
import { SettingsView } from "@/components/views/SettingsView";
import { ConnectRepoModal } from "@/components/modals/ConnectRepoModal";

export function DeveloperPortal() {
  const [activeTab, setActiveTab] = useState<NavTabId | "overview">("overview");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [connectModalOpen, setConnectModalOpen] = useState(false);
  const [currentRepo, setCurrentRepo] = useState(
    "AnshulKanodia/DevMind-AI-Engineering-Copilot"
  );
  const [currentBranch, setCurrentBranch] = useState("main");
  const [availableBranches, setAvailableBranches] = useState<string[]>([
    "main",
    "dev",
    "feat/phase8-ui-repo-onboarding",
  ]);
  const [repoStats, setRepoStats] = useState({
    files: 142,
    chunks: 684,
  });

  const handleRepoConnected = (
    repoUrl: string,
    branch: string,
    stats?: { files: number; chunks: number }
  ) => {
    try {
      const parsed = new URL(repoUrl).pathname.replace(/^\//, "");
      if (parsed) setCurrentRepo(parsed);
    } catch {
      setCurrentRepo(repoUrl);
    }

    setCurrentBranch(branch);
    if (!availableBranches.includes(branch)) {
      setAvailableBranches((prev) => [...prev, branch]);
    }

    if (stats) {
      setRepoStats({
        files: stats.files,
        chunks: stats.chunks,
      });
    }

    // After connecting a repo, automatically route to the Code Q&A Copilot tab
    setActiveTab("chat");
  };

  return (
    <div className="flex h-screen w-full flex-col bg-[#070b14] text-slate-100 overflow-hidden font-sans">
      {/* Top Navbar */}
      <Navbar
        currentRepo={currentRepo}
        currentBranch={currentBranch}
        availableBranches={availableBranches}
        onBranchChange={setCurrentBranch}
        onConnectRepoClick={() => setConnectModalOpen(true)}
      />

      {/* Main Body with Sidebar + Viewport */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          activeTab={activeTab === "overview" ? "chat" : activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
          collapsed={sidebarCollapsed}
          onToggleCollapsed={() => setSidebarCollapsed((prev) => !prev)}
        />

        {/* Viewport Content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 bg-gradient-to-b from-[#070b14] via-[#090e1c] to-[#070b14]">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Quick Breadcrumb bar */}
            <div className="flex items-center justify-between pb-2 border-b border-slate-800/60">
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <button
                  onClick={() => setActiveTab("overview")}
                  className={`hover:text-white transition-colors ${
                    activeTab === "overview" ? "text-sky-400 font-semibold" : ""
                  }`}
                >
                  Overview
                </button>
                {activeTab !== "overview" && (
                  <>
                    <span>/</span>
                    <span className="text-white font-medium capitalize">
                      {activeTab.replace("_", " ")}
                    </span>
                  </>
                )}
              </div>

              {activeTab !== "overview" && (
                <button
                  onClick={() => setActiveTab("overview")}
                  className="text-xs text-slate-400 hover:text-sky-400 transition-colors"
                >
                  &larr; Back to Dashboard
                </button>
              )}
            </div>

            {/* Active View Rendering */}
            {activeTab === "overview" && (
              <OverviewView
                onNavigate={(tab) => setActiveTab(tab)}
                onConnectRepo={() => setConnectModalOpen(true)}
              />
            )}
            {activeTab === "chat" && <ChatView />}
            {activeTab === "security" && <SecurityView />}
            {activeTab === "tests" && <TestsView />}
            {activeTab === "pr_review" && <PRReviewView />}
            {activeTab === "repo" && (
              <RepoView
                currentRepo={currentRepo}
                currentBranch={currentBranch}
                filesCount={repoStats.files}
                chunksCount={repoStats.chunks}
                onOpenConnectModal={() => setConnectModalOpen(true)}
              />
            )}
            {activeTab === "settings" && <SettingsView />}
          </div>
        </main>
      </div>

      {/* Repository Onboarding Modal */}
      <ConnectRepoModal
        open={connectModalOpen}
        onOpenChange={setConnectModalOpen}
        onRepoConnected={handleRepoConnected}
      />
    </div>
  );
}
