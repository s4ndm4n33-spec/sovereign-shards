import { Link } from "react-router-dom";
import {
  MessageSquare,
  GitBranch,
  Code2,
  Link2,
  Shield,
  Zap,
  Terminal,
  ArrowRight,
  Bot,
  Cpu,
} from "lucide-react";

const FEATURES = [
  {
    icon: MessageSquare,
    title: "Chat with J",
    desc: "Full conversational interface. J plans, codes, and ships — right from your browser.",
    color: "#1E90FF",
  },
  {
    icon: Code2,
    title: "Code Editor",
    desc: "Browse and view files from your GitHub repo. Syntax highlighting, line numbers, instant loading.",
    color: "#00d4aa",
  },
  {
    icon: GitBranch,
    title: "GitHub Integration",
    desc: "Connect any public repo. Browse the file tree, view code, and let J work on your codebase.",
    color: "#FFD700",
  },
  {
    icon: Link2,
    title: "Chain Logs",
    desc: "J's multi-step execution chains with checkpoint/resume. Full visibility into PLAN → EXECUTE → VERIFY.",
    color: "#1E90FF",
  },
  {
    icon: Shield,
    title: "Admin Panel",
    desc: "Configure models, API keys, system prompts. Full control over J's brain and behavior.",
    color: "#00FF41",
  },
  {
    icon: Zap,
    title: "Free Forever",
    desc: "Powered by Groq's free API tier. No cloud bills, no subscriptions. J's brain is on the house.",
    color: "#FFD700",
  },
];

export function LandingPage() {
  return (
    <div className="min-h-screen bg-[#06060F] text-[#e8e8f0] overflow-x-hidden">
      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 bg-[#06060F]/85 backdrop-blur-xl border-b border-[#1a1a2e]">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="size-8 rounded-lg bg-gradient-to-br from-[#1E90FF] to-[#00d4aa] flex items-center justify-center">
              <Terminal className="size-4 text-white" />
            </div>
            <span className="font-extrabold text-lg tracking-wide">
              <span className="text-[#1E90FF]">J</span>
              <span className="text-[#8888a0]"> Cloud</span>
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="text-sm text-[#8888a0] hover:text-white transition"
            >
              Sign In
            </Link>
            <Link
              to="/signup"
              className="px-4 py-2 bg-gradient-to-r from-[#1E90FF] to-[#00d4aa] text-white text-sm font-semibold rounded-lg hover:opacity-90 transition"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative pt-32 pb-20 px-6">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,rgba(30,144,255,0.08)_0%,transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_80%_20%,rgba(255,215,0,0.04)_0%,transparent_40%)]" />

        <div className="max-w-3xl mx-auto text-center relative">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#1a1a2e] border border-[#2a2a3a] text-xs font-medium text-[#FFD700] tracking-wider uppercase mb-6">
            <Bot className="size-3" />
            Sovereign Shards • J Agent
          </div>

          <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold tracking-tight leading-[1.05] mb-6">
            J lives in
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#1E90FF] via-[#00d4aa] to-[#FFD700]">
              the cloud now.
            </span>
          </h1>

          <p className="text-lg md:text-xl text-[#8888a0] max-w-xl mx-auto mb-8 leading-relaxed">
            Your autonomous AI dev agent — chat, code, and ship from any device.
            No USB required. Free to run.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center mb-8">
            <Link
              to="/signup"
              className="inline-flex items-center justify-center gap-2 px-8 py-3.5 bg-gradient-to-r from-[#1E90FF] to-[#00d4aa] text-white font-bold text-lg rounded-xl hover:opacity-90 transition shadow-[0_4px_24px_rgba(30,144,255,0.3)]"
            >
              Launch J Cloud
              <ArrowRight className="size-5" />
            </Link>
            <a
              href="https://github.com/s4ndm4n33-spec/sovereign-shards"
              target="_blank"
              rel="noopener"
              className="inline-flex items-center justify-center gap-2 px-8 py-3.5 border border-[#2a2a3a] text-[#e8e8f0] font-semibold text-lg rounded-xl hover:bg-[#1a1a2e] transition"
            >
              <GitBranch className="size-5" />
              Source Code
            </a>
          </div>

          <div className="flex items-center justify-center gap-6 text-sm text-[#8888a0]">
            <span className="flex items-center gap-1.5"><Cpu className="size-4 text-[#00FF41]" /> Free Groq LLM</span>
            <span className="flex items-center gap-1.5"><Zap className="size-4 text-[#00FF41]" /> 4096 token cap</span>
            <span className="hidden sm:flex items-center gap-1.5"><Shield className="size-4 text-[#00FF41]" /> Your data, your control</span>
          </div>
        </div>
      </section>

      {/* Terminal mockup */}
      <section className="py-16 px-6">
        <div className="max-w-3xl mx-auto">
          <div className="rounded-2xl overflow-hidden border border-[#2a2a3a] shadow-[0_8px_40px_rgba(0,0,0,0.5)] j-glow">
            <div className="bg-[#0a0a14] px-4 py-3 flex items-center gap-2 border-b border-[#1a1a2e]">
              <div className="flex gap-1.5">
                <div className="size-3 rounded-full bg-[#ff5f57]" />
                <div className="size-3 rounded-full bg-[#febc2e]" />
                <div className="size-3 rounded-full bg-[#28c840]" />
              </div>
              <span className="text-xs text-[#8888a0] ml-2">j-cloud</span>
            </div>
            <div className="bg-[#06060F] p-6 font-mono text-sm leading-relaxed">
              <div className="text-[#8888a0]">
                <span className="text-[#FFD700]">architect</span>
                <span className="text-[#8888a0]">@</span>
                <span className="text-[#1E90FF]">j-cloud</span>
                <span className="text-[#8888a0]"> $ </span>
                <span className="text-white">hey J, refactor the auth module</span>
              </div>
              <div className="mt-3 text-[#00d4aa]">
                J → Planning refactor for auth module...
              </div>
              <div className="text-[#8888a0] text-xs mt-2 ml-4">
                ├─ PLAN: Analyze current auth.py (847 lines)<br />
                ├─ PLAN: Extract OAuth handler → auth/oauth.py<br />
                ├─ PLAN: Extract session mgr → auth/sessions.py<br />
                ├─ EXECUTE: Writing 3 new modules...<br />
                ├─ VERIFY: Running 42 tests... ✓ all pass<br />
                └─ DONE: Created PR #47 — "Decompose auth module"
              </div>
              <div className="mt-3 text-[#00d4aa]">
                J → Done. PR ready for review.
                <span className="text-[#1E90FF] j-cursor" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">
            Everything J needs.{" "}
            <span className="text-[#8888a0]">Nothing more.</span>
          </h2>
          <div className="grid md:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="p-6 rounded-xl border border-[#1a1a2e] bg-[#0a0a14] hover:border-[#2a2a3a] transition"
              >
                <div
                  className="size-10 rounded-lg flex items-center justify-center mb-4"
                  style={{ backgroundColor: `${f.color}15` }}
                >
                  <f.icon className="size-5" style={{ color: f.color }} />
                </div>
                <h3 className="text-sm font-bold text-white mb-2">{f.title}</h3>
                <p className="text-xs text-[#8888a0] leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#1a1a2e] py-8 px-6">
        <div className="max-w-5xl mx-auto flex items-center justify-between text-xs text-[#8888a0]">
          <span>
            <span className="text-[#1E90FF]">Sovereign</span>{" "}
            <span className="text-[#FFD700]">Shards</span> • J Cloud
          </span>
          <a
            href="https://github.com/s4ndm4n33-spec/sovereign-shards"
            target="_blank"
            rel="noopener"
            className="hover:text-white transition"
          >
            GitHub
          </a>
        </div>
      </footer>
    </div>
  );
}
