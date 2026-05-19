import { useState } from "react";
import { useMutation, useAction } from "convex/react";
import { api } from "../../convex/_generated/api";
import {
  Cpu,
  HardDrive,
  Lock,
  WifiOff,
  Zap,
  Shield,
  Terminal,
  GitBranch,
  Wrench,
  Brain,
  ChevronDown,
  Check,
  ArrowRight,
  Sparkles,
  ExternalLink,
} from "lucide-react";

const TIERS = [
  {
    id: "standard",
    name: "Standard",
    price: 4999, // cents
    display: "$49.99",
    desc: "Pre-loaded USB — plug in and build",
    features: [
      "Pre-configured USB stick",
      "Qwen2.5-Coder-7B model included",
      "All 17 tools pre-installed",
      "Setup guide & quickstart",
    ],
  },
  {
    id: "dev",
    name: "Developer",
    price: 9999,
    display: "$99.99",
    desc: "Everything in Standard + priority support",
    popular: true,
    features: [
      "Everything in Standard",
      "Priority email support",
      "Early access to updates",
      "Custom tool forge templates",
      "Extended documentation pack",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 24999,
    display: "$249.99",
    desc: "Fleet deployment + custom integration",
    features: [
      "Everything in Developer",
      "10-pack USB deployment",
      "Custom model configuration",
      "Dedicated onboarding session",
      "Custom tool development",
      "SLA & priority fixes",
    ],
  },
];

const COMPARISON = [
  { cap: "Multi-step planning", j: "✓ DAG + parallel", copilot: "✗", claude: "✓", codex: "✓" },
  { cap: "Runs 100% offline", j: "✓", copilot: "✗", claude: "✗", codex: "✗" },
  { cap: "No API key required", j: "✓", copilot: "✗", claude: "✗", codex: "✗" },
  { cap: "Portable (USB stick)", j: "✓", copilot: "✗", claude: "✗", codex: "✗" },
  { cap: "Data stays local", j: "✓ Always", copilot: "✗ Cloud", claude: "✗ Cloud", codex: "✗ Cloud" },
  { cap: "Cross-session memory", j: "✓ 3-tier", copilot: "✗", claude: "✓", codex: "✓" },
  { cap: "Self-healing errors", j: "✓ Circuit breaker", copilot: "✗", claude: "✓", codex: "✓" },
  { cap: "Builds its own tools", j: "✓ Inference forge", copilot: "✗", claude: "✗", codex: "✗" },
  { cap: "Monthly cost", j: "$0", copilot: "$19+", claude: "$20+", codex: "$20+" },
];

const FAQ = [
  {
    q: "What hardware do I need?",
    a: "Any machine with 16 GB RAM and a USB port. J runs on CPU — no GPU required. Intel HD 530 is the tested minimum. Windows primary, Linux/macOS compatible.",
  },
  {
    q: "What model does J use?",
    a: "Qwen2.5-Coder-7B-Instruct (Q4_K_M GGUF) via llama.cpp. It runs entirely locally with a 4096-token context window — no cloud inference.",
  },
  {
    q: "Is it really air-gapped?",
    a: "Yes. Zero network calls, zero telemetry, zero cloud dependencies. J uses SHA-256 integrity monitoring, AST governance, and a 5-check pre-push sandbox. Your code never leaves the USB stick.",
  },
  {
    q: "What can J actually build?",
    a: "Full projects: plan → execute → verify. It reads/writes files, runs shell commands, manages git, builds tools at runtime, handles multi-step DAG task plans, and self-corrects on errors with circuit breakers.",
  },
  {
    q: "When will pre-orders ship?",
    a: "Pre-orders are currently reserving your spot. We'll announce shipping dates via email. You won't be charged until the product is ready to ship.",
  },
  {
    q: "Can I get a refund?",
    a: "Pre-orders can be cancelled at any time before shipping for a full refund. No questions asked.",
  },
];

export function LandingPage() {
  const [formState, setFormState] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [selectedTier, setSelectedTier] = useState("dev");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const createPreorder = useMutation(api.preorders.create);
  const sendNotification = useAction(api.preorders.sendNotification);

  const handlePreorder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email) return;
    setFormState("submitting");
    try {
      const tier = TIERS.find((t) => t.id === selectedTier)!;
      await createPreorder({
        name,
        email,
        tier: tier.name,
        amount: tier.price,
      });
      // Fire & forget notification
      sendNotification({
        name,
        email,
        tier: tier.name,
        amount: tier.price,
      }).catch(() => {});
      setFormState("success");
    } catch {
      setFormState("error");
    }
  };

  return (
    <div className="min-h-screen bg-[#06060F] text-[#e8e8f0] overflow-x-hidden">
      {/* ═══ NAV ═══ */}
      <nav className="fixed top-0 w-full z-50 bg-[#06060F]/85 backdrop-blur-xl border-b border-[#1a1a2e]">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <a href="#" className="font-extrabold text-lg tracking-wide">
            <span className="text-[#1E90FF]">Sovereign</span>
            <span className="text-[#FFD700]"> Shards</span>
          </a>
          <div className="hidden sm:flex items-center gap-6 text-sm text-[#8888a0]">
            <a href="#features" className="hover:text-white transition">Features</a>
            <a href="#compare" className="hover:text-white transition">Compare</a>
            <a href="#pricing" className="hover:text-white transition">Pricing</a>
            <a href="#faq" className="hover:text-white transition">FAQ</a>
            <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/blob/main/docs/USER_MANUAL.md" target="_blank" rel="noopener" className="hover:text-white transition">Docs</a>
          </div>
          <a
            href="#pricing"
            className="px-4 py-2 bg-gradient-to-r from-[#1E90FF] to-[#00d4aa] text-white text-sm font-semibold rounded-lg hover:opacity-90 transition"
          >
            Pre-Order
          </a>
        </div>
      </nav>

      {/* ═══ HERO ═══ */}
      <section className="relative pt-32 pb-20 px-6">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,rgba(30,144,255,0.08)_0%,transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_80%_20%,rgba(255,215,0,0.04)_0%,transparent_40%)]" />

        <div className="max-w-4xl mx-auto text-center relative">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#1a1a2e] border border-[#2a2a3a] text-xs font-medium text-[#FFD700] tracking-wider uppercase mb-6">
            <Sparkles className="size-3" />
            Now accepting pre-orders
          </div>

          <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold tracking-tight leading-[1.05] mb-6">
            Your AI dev agent.
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#1E90FF] via-[#00d4aa] to-[#FFD700]">
              On a USB stick.
            </span>
          </h1>

          <p className="text-lg md:text-xl text-[#8888a0] max-w-xl mx-auto mb-8 leading-relaxed">
            J is a fully autonomous AI developer that plans, codes, tests, and ships — 
            no cloud, no API keys, no internet. Plug in and build.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center mb-8">
            <a
              href="#pricing"
              className="inline-flex items-center justify-center gap-2 px-8 py-3.5 bg-gradient-to-r from-[#1E90FF] to-[#00d4aa] text-white font-bold text-lg rounded-xl hover:opacity-90 transition shadow-[0_4px_24px_rgba(30,144,255,0.3)]"
            >
              Reserve Yours
              <ArrowRight className="size-5" />
            </a>
            <a
              href="https://github.com/s4ndm4n33-spec/sovereign-shards"
              target="_blank"
              rel="noopener"
              className="inline-flex items-center justify-center gap-2 px-8 py-3.5 border border-[#2a2a3a] text-[#e8e8f0] font-semibold text-lg rounded-xl hover:bg-[#1a1a2e] transition"
            >
              <GitBranch className="size-5" />
              View on GitHub
            </a>
          </div>

          <div className="flex items-center justify-center gap-6 text-sm text-[#8888a0]">
            <span className="flex items-center gap-1.5"><Check className="size-4 text-[#00FF41]" /> 100% offline</span>
            <span className="flex items-center gap-1.5"><Check className="size-4 text-[#00FF41]" /> Zero dependencies</span>
            <span className="hidden sm:flex items-center gap-1.5"><Check className="size-4 text-[#00FF41]" /> $0/month forever</span>
          </div>
        </div>
      </section>

      {/* ═══ VIDEO DEMO ═══ */}
      <section className="py-16 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="relative rounded-2xl overflow-hidden border border-[#2a2a3a] shadow-[0_8px_40px_rgba(0,0,0,0.5)]">
            <video
              controls
              preload="metadata"
              poster=""
              className="w-full aspect-video bg-black"
            >
              <source
                src="https://raw.githubusercontent.com/s4ndm4n33-spec/sovereign-shards/main/assets/j-demo.mp4"
                type="video/mp4"
              />
            </video>
          </div>
          <p className="text-center text-sm text-[#8888a0] mt-4">
            80-second demo — see J plan, code, test, and ship autonomously
          </p>
        </div>
      </section>

      {/* ═══ STATS BAR ═══ */}
      <section className="py-12 px-6 border-y border-[#1a1a2e] bg-[#0a0a14]">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            { num: "17+", label: "Built-in tools" },
            { num: "147+", label: "Tests passing" },
            { num: "4096", label: "Token context" },
            { num: "2", label: "Dependencies" },
          ].map((s) => (
            <div key={s.label}>
              <div className="text-3xl md:text-4xl font-bold text-[#1E90FF]">{s.num}</div>
              <div className="text-sm text-[#8888a0] mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ FEATURES ═══ */}
      <section id="features" className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-sm font-medium text-[#FFD700] tracking-wider uppercase mb-3">Capabilities</p>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Everything a cloud agent does. Without the cloud.</h2>
            <p className="text-[#8888a0] max-w-xl mx-auto">
              17 tools, DAG task planning, 3-tier memory, circuit breaker self-healing, and a runtime tool forge — all from a USB stick.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { icon: Brain, title: "DAG Task Planning", desc: "Breaks complex jobs into dependency graphs with parallel tier execution. Plan → Execute → Verify.", color: "#1E90FF" },
              { icon: WifiOff, title: "100% Air-Gapped", desc: "Zero network calls. Zero telemetry. Zero cloud. Your code never leaves the USB stick.", color: "#DC143C" },
              { icon: Shield, title: "Defense Suite", desc: "SHA-256 integrity (SHIELD), host audit (SCAN), pre-push sandbox (BRIDGE), AST governance (Five Masters).", color: "#FFD700" },
              { icon: Terminal, title: "17+ Tools", desc: "File ops, shell exec, git, search, code analysis, streaming capture — all built in and sandboxed.", color: "#00FF41" },
              { icon: Wrench, title: "Inference Forge", desc: "J builds new tools at runtime. If a tool doesn't exist, it creates one mid-session.", color: "#00d4aa" },
              { icon: HardDrive, title: "3-Tier Memory", desc: "Active context → working memory → long-term BM25 retrieval. Cross-session persistence.", color: "#8b5cf6" },
              { icon: Zap, title: "Circuit Breaker", desc: "Self-healing error recovery. If something breaks, J detects, backs off, and retries with a different approach.", color: "#FF6B35" },
              { icon: Cpu, title: "CPU-Only Inference", desc: "Qwen2.5-Coder-7B via llama.cpp. No GPU needed. Intel HD 530 is the floor.", color: "#1E90FF" },
              { icon: Lock, title: "FAT32-Safe Atomic Ops", desc: "Designed for USB stick constraints. Atomic writes, bounded paths, portable across any filesystem.", color: "#DC143C" },
            ].map((f) => (
              <div
                key={f.title}
                className="group relative overflow-hidden rounded-xl bg-[#0d0d18] border border-[#1a1a2e] p-6 transition-all hover:border-[#2a2a3a] hover:shadow-lg"
              >
                <div
                  className="absolute top-0 right-0 -mt-4 -mr-4 size-24 rounded-full blur-2xl opacity-10 group-hover:opacity-20 transition"
                  style={{ background: f.color }}
                />
                <div className="relative">
                  <div
                    className="inline-flex size-10 items-center justify-center rounded-lg mb-4"
                    style={{ background: `${f.color}15` }}
                  >
                    <f.icon className="size-5" style={{ color: f.color }} />
                  </div>
                  <h3 className="font-semibold text-base mb-2">{f.title}</h3>
                  <p className="text-sm text-[#8888a0] leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section className="py-20 px-6 bg-[#0a0a14]">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Three steps. One USB.</h2>
            <p className="text-[#8888a0]">From pocket to production in under a minute.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              { num: "1", title: "Plug In & Launch", desc: "Insert the USB. Run python run.py. The local model boots automatically." },
              { num: "2", title: "Describe the Job", desc: "Tell J what to build in plain English. It breaks the task into a dependency graph." },
              { num: "3", title: "J Builds, Tests & Ships", desc: "Autonomous plan → execute → verify loop. Sandbox validates everything before code leaves the drive." },
            ].map((s) => (
              <div key={s.num} className="text-center">
                <div className="inline-flex size-14 items-center justify-center rounded-full bg-gradient-to-br from-[#1E90FF] to-[#00d4aa] text-white text-xl font-bold mb-4">
                  {s.num}
                </div>
                <h3 className="font-semibold text-lg mb-2">{s.title}</h3>
                <p className="text-sm text-[#8888a0] leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ COMPARISON TABLE ═══ */}
      <section id="compare" className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">How J compares</h2>
            <p className="text-[#8888a0]">Same architecture as cloud agents — without the cloud.</p>
          </div>

          <div className="overflow-x-auto rounded-xl border border-[#1a1a2e]">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#0d0d18] border-b border-[#1a1a2e]">
                  <th className="text-left p-4 font-medium text-[#8888a0]">Capability</th>
                  <th className="p-4 font-bold text-[#1E90FF] bg-[#1E90FF]/5">J</th>
                  <th className="p-4 font-medium text-[#8888a0]">Copilot</th>
                  <th className="p-4 font-medium text-[#8888a0]">Claude Code</th>
                  <th className="p-4 font-medium text-[#8888a0]">Codex</th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON.map((row, i) => (
                  <tr key={row.cap} className={i % 2 === 0 ? "bg-[#06060F]" : "bg-[#0a0a14]"}>
                    <td className="p-4 text-[#e8e8f0]">{row.cap}</td>
                    <td className="p-4 text-center font-semibold bg-[#1E90FF]/5">
                      <span className={row.j.startsWith("✓") ? "text-[#00FF41]" : row.j === "$0" ? "text-[#00d4aa] font-bold" : "text-[#e8e8f0]"}>
                        {row.j}
                      </span>
                    </td>
                    <td className="p-4 text-center">
                      <span className={row.copilot.startsWith("✓") ? "text-[#00FF41]" : row.copilot.startsWith("✗") ? "text-[#DC143C]/60" : "text-[#8888a0]"}>
                        {row.copilot}
                      </span>
                    </td>
                    <td className="p-4 text-center">
                      <span className={row.claude.startsWith("✓") ? "text-[#00FF41]" : row.claude.startsWith("✗") ? "text-[#DC143C]/60" : "text-[#8888a0]"}>
                        {row.claude}
                      </span>
                    </td>
                    <td className="p-4 text-center">
                      <span className={row.codex.startsWith("✓") ? "text-[#00FF41]" : row.codex.startsWith("✗") ? "text-[#DC143C]/60" : "text-[#8888a0]"}>
                        {row.codex}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ═══ PRICING / PRE-ORDER ═══ */}
      <section id="pricing" className="py-20 px-6 bg-[#0a0a14]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-sm font-medium text-[#FFD700] tracking-wider uppercase mb-3">Pre-Order</p>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Reserve your sovereign agent</h2>
            <p className="text-[#8888a0] max-w-lg mx-auto">
              No charge until we ship. Cancel anytime. Get priority access and early-bird pricing.
            </p>
          </div>

          {formState === "success" ? (
            <div className="max-w-lg mx-auto text-center py-16">
              <div className="inline-flex size-16 items-center justify-center rounded-full bg-[#00FF41]/10 mb-6">
                <Check className="size-8 text-[#00FF41]" />
              </div>
              <h3 className="text-2xl font-bold mb-3">You're in. 🔥</h3>
              <p className="text-[#8888a0] mb-2">
                Your pre-order has been reserved. We'll email you at <strong className="text-white">{email}</strong> when it's time to ship.
              </p>
              <p className="text-sm text-[#8888a0]">No charge until the product is ready.</p>
            </div>
          ) : (
            <>
              {/* Tier cards */}
              <div className="grid md:grid-cols-3 gap-4 mb-12">
                {TIERS.map((tier) => (
                  <button
                    key={tier.id}
                    type="button"
                    onClick={() => setSelectedTier(tier.id)}
                    className={`relative text-left rounded-xl p-6 border transition-all ${
                      selectedTier === tier.id
                        ? "border-[#1E90FF] bg-[#1E90FF]/5 shadow-[0_0_24px_rgba(30,144,255,0.15)]"
                        : "border-[#1a1a2e] bg-[#0d0d18] hover:border-[#2a2a3a]"
                    }`}
                  >
                    {tier.popular && (
                      <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-gradient-to-r from-[#1E90FF] to-[#00d4aa] text-white text-xs font-bold rounded-full">
                        Most Popular
                      </span>
                    )}
                    <h3 className="font-bold text-lg mb-1">{tier.name}</h3>
                    <div className="text-3xl font-bold text-[#1E90FF] mb-2">{tier.display}</div>
                    <p className="text-sm text-[#8888a0] mb-4">{tier.desc}</p>
                    <ul className="space-y-2">
                      {tier.features.map((f) => (
                        <li key={f} className="flex items-start gap-2 text-sm">
                          <Check className="size-4 text-[#00FF41] mt-0.5 shrink-0" />
                          <span className="text-[#c0c0d0]">{f}</span>
                        </li>
                      ))}
                    </ul>
                  </button>
                ))}
              </div>

              {/* Pre-order form */}
              <form onSubmit={handlePreorder} className="max-w-md mx-auto space-y-4">
                <div>
                  <label htmlFor="name" className="block text-sm font-medium mb-1.5">Name</label>
                  <input
                    id="name"
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                    className="w-full px-4 py-3 bg-[#0d0d18] border border-[#2a2a3a] rounded-lg text-white placeholder-[#555] focus:outline-none focus:border-[#1E90FF] transition"
                  />
                </div>
                <div>
                  <label htmlFor="email" className="block text-sm font-medium mb-1.5">Email</label>
                  <input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full px-4 py-3 bg-[#0d0d18] border border-[#2a2a3a] rounded-lg text-white placeholder-[#555] focus:outline-none focus:border-[#1E90FF] transition"
                  />
                </div>
                <button
                  type="submit"
                  disabled={formState === "submitting"}
                  className="w-full py-3.5 bg-gradient-to-r from-[#1E90FF] to-[#00d4aa] text-white font-bold text-lg rounded-xl hover:opacity-90 transition disabled:opacity-50 shadow-[0_4px_24px_rgba(30,144,255,0.3)]"
                >
                  {formState === "submitting" ? "Reserving..." : `Reserve — ${TIERS.find((t) => t.id === selectedTier)!.display}`}
                </button>
                {formState === "error" && (
                  <p className="text-center text-sm text-[#DC143C]">Something went wrong. Please try again.</p>
                )}
                <p className="text-center text-xs text-[#666]">
                  No charge today. You'll only be billed when the product ships.
                </p>
              </form>
            </>
          )}
        </div>
      </section>

      {/* ═══ FAQ ═══ */}
      <section id="faq" className="py-20 px-6">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">FAQ</h2>
          <div className="space-y-2">
            {FAQ.map((item, i) => (
              <div key={i} className="border border-[#1a1a2e] rounded-xl overflow-hidden">
                <button
                  type="button"
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-center justify-between p-5 text-left hover:bg-[#0a0a14] transition"
                >
                  <span className="font-medium">{item.q}</span>
                  <ChevronDown
                    className={`size-5 text-[#8888a0] transition-transform ${openFaq === i ? "rotate-180" : ""}`}
                  />
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-5 text-sm text-[#8888a0] leading-relaxed">
                    {item.a}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FINAL CTA ═══ */}
      <section className="py-20 px-6 bg-[#0a0a14] border-t border-[#1a1a2e]">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Your code. Your hardware.
            <br />
            Your <span className="text-[#00d4aa]">sovereign</span> agent.
          </h2>
          <p className="text-[#8888a0] max-w-lg mx-auto mb-8">
            No signup. No API keys. No strings. Plug in a USB stick and start building.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <a
              href="#pricing"
              className="inline-flex items-center justify-center gap-2 px-8 py-3.5 bg-gradient-to-r from-[#1E90FF] to-[#00d4aa] text-white font-bold text-lg rounded-xl hover:opacity-90 transition shadow-[0_4px_24px_rgba(30,144,255,0.3)]"
            >
              Reserve Yours
              <ArrowRight className="size-5" />
            </a>
            <a
              href="https://github.com/s4ndm4n33-spec/sovereign-shards"
              target="_blank"
              rel="noopener"
              className="inline-flex items-center justify-center gap-2 px-8 py-3.5 border border-[#2a2a3a] text-[#e8e8f0] font-semibold rounded-xl hover:bg-[#1a1a2e] transition"
            >
              View Source
            </a>
          </div>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="py-10 px-6 border-t border-[#1a1a2e]">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-8">
            <div>
              <h4 className="text-sm font-semibold text-[#e8e8f0] mb-3">Product</h4>
              <div className="flex flex-col gap-2 text-sm text-[#8888a0]">
                <a href="#features" className="hover:text-white transition">Features</a>
                <a href="#compare" className="hover:text-white transition">Compare</a>
                <a href="#pricing" className="hover:text-white transition">Pricing</a>
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/releases/tag/v1.0.0" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">Release v1.0.0 <ExternalLink className="size-3" /></a>
              </div>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-[#e8e8f0] mb-3">Documentation</h4>
              <div className="flex flex-col gap-2 text-sm text-[#8888a0]">
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/blob/main/docs/USER_MANUAL.md" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">User Manual <ExternalLink className="size-3" /></a>
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/blob/main/docs/ROADMAP.md" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">Roadmap <ExternalLink className="size-3" /></a>
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/blob/main/docs/TOOL_REFERENCE.md" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">Tool Reference <ExternalLink className="size-3" /></a>
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/blob/main/INSTALL.md" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">Install Guide <ExternalLink className="size-3" /></a>
              </div>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-[#e8e8f0] mb-3">Engineering</h4>
              <div className="flex flex-col gap-2 text-sm text-[#8888a0]">
                <a href="https://five-masters-b9b95dc3.viktor.space" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">The Five Masters <ExternalLink className="size-3" /></a>
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/blob/main/docs/REPO_ANALYSIS_REPORT.md" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">Repo Analysis (92/100) <ExternalLink className="size-3" /></a>
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/blob/main/docs/MIGRATION_LOG.md" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">Migration Log <ExternalLink className="size-3" /></a>
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/blob/main/CONTRIBUTING.md" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">Contributing <ExternalLink className="size-3" /></a>
              </div>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-[#e8e8f0] mb-3">Source</h4>
              <div className="flex flex-col gap-2 text-sm text-[#8888a0]">
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1"><GitBranch className="size-3" /> GitHub <ExternalLink className="size-3" /></a>
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/blob/main/docs/MARKET_RESEARCH.md" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">Market Research <ExternalLink className="size-3" /></a>
                <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/blob/main/docs/BUSINESS_MODEL.md" target="_blank" rel="noopener" className="hover:text-white transition inline-flex items-center gap-1">Business Model <ExternalLink className="size-3" /></a>
              </div>
            </div>
          </div>
          <div className="border-t border-[#1a1a2e] pt-6 text-center text-sm text-[#555]">
            <p>© 2026 Sovereign Shards. Built with zero cloud dependencies.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
