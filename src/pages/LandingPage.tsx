import { useConvexAuth } from "convex/react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function LandingPage() {
  const { isAuthenticated } = useConvexAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background shard-grid relative overflow-hidden flex flex-col">
      {/* Ambient glow effects */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-shard-violet/5 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-shard-cyan/5 rounded-full blur-[100px] pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-6 py-4 border-b border-shard-violet/10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-shard-violet/20 border border-shard-violet/30 rounded-lg flex items-center justify-center">
            <span className="text-shard-violet font-mono text-sm font-bold">◈</span>
          </div>
          <span className="font-semibold text-shard-white tracking-tight">SOVEREIGN SHARDS</span>
        </div>
        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <Button
              onClick={() => navigate("/chat")}
              className="bg-shard-violet hover:bg-shard-violet/80 text-white font-mono text-sm"
            >
              ENTER COMMS →
            </Button>
          ) : (
            <>
              <Button
                variant="ghost"
                onClick={() => navigate("/login")}
                className="text-shard-gray hover:text-shard-white font-mono text-sm"
              >
                SIGN IN
              </Button>
              <Button
                onClick={() => navigate("/signup")}
                className="bg-shard-violet hover:bg-shard-violet/80 text-white font-mono text-sm"
              >
                REGISTER
              </Button>
            </>
          )}
        </div>
      </nav>

      {/* Hero */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 text-center">
        <div className="mb-4">
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-shard-cyan/20 bg-shard-cyan/5 text-shard-cyan text-xs font-mono tracking-wider">
            <span className="w-1.5 h-1.5 bg-shard-cyan rounded-full shard-pulse" />
            LIVE COMMS NETWORK
          </span>
        </div>

        <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold text-shard-white tracking-tight leading-[1.1] max-w-3xl mb-6">
          Developer
          <span className="text-shard-violet"> Comms</span>
          <br />
          <span className="text-shard-cyan">Channel</span>
        </h1>

        <p className="text-shard-gray text-base sm:text-lg max-w-xl mb-10 leading-relaxed">
          Real-time communication substrate for sovereign operators.
          Code, collaborate, coordinate. No surveillance. No gatekeeping.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4">
          <Button
            size="lg"
            onClick={() => navigate("/chat")}
            className="bg-shard-violet hover:bg-shard-violet/80 text-white font-mono text-sm px-8 h-12 shard-glow"
          >
            ENTER AS GUEST →
          </Button>
          {!isAuthenticated && (
            <Button
              size="lg"
              variant="outline"
              onClick={() => navigate("/signup")}
              className="border-shard-violet/30 text-shard-violet hover:bg-shard-violet/10 font-mono text-sm px-8 h-12"
            >
              CREATE ACCOUNT
            </Button>
          )}
        </div>

        {/* Feature chips */}
        <div className="flex flex-wrap items-center justify-center gap-3 mt-16 max-w-2xl">
          {[
            "Real-time messaging",
            "Code snippets",
            "Markdown",
            "Emoji reactions",
            "Anonymous access",
            "Zero tracking",
          ].map((feature) => (
            <span
              key={feature}
              className="px-3 py-1.5 rounded border border-shard-violet/10 bg-shard-elevated text-shard-gray text-xs font-mono"
            >
              {feature}
            </span>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-shard-violet/10 py-4 px-6 text-center">
        <p className="text-shard-gray/50 text-xs font-mono">
          SOVEREIGN SHARDS — Autonomous Systems. Sovereign Execution.
        </p>
      </footer>
    </div>
  );
}
