import { useConvexAuth } from "convex/react";
import { Navigate, useNavigate } from "react-router-dom";
import { SignUp } from "@/components/SignUp";
import { TestUserLoginSection } from "@/components/TestUserLoginSection";

export function SignupPage() {
  const { isAuthenticated } = useConvexAuth();
  const navigate = useNavigate();

  if (isAuthenticated) {
    return <Navigate to="/chat" replace />;
  }

  return (
    <div className="min-h-screen bg-background shard-grid flex flex-col">
      {/* Ambient glow */}
      <div className="absolute bottom-0 left-1/3 w-80 h-80 bg-shard-cyan/5 rounded-full blur-[100px] pointer-events-none" />

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-shard-violet/10 relative z-10">
        <button onClick={() => navigate("/")} className="flex items-center gap-2">
          <div className="w-7 h-7 bg-shard-violet/20 border border-shard-violet/30 rounded-md flex items-center justify-center">
            <span className="text-shard-violet font-mono text-xs font-bold">◈</span>
          </div>
          <span className="font-semibold text-shard-white tracking-tight text-sm">SOVEREIGN SHARDS</span>
        </button>
      </nav>

      <main className="flex-1 flex items-center justify-center px-4 relative z-10">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-shard-white mb-2">Create Account</h1>
            <p className="text-sm text-shard-gray font-mono">Initialize your operator profile</p>
          </div>
          <SignUp />
          <TestUserLoginSection />
          <div className="text-center mt-6">
            <span className="text-sm text-shard-gray">Already registered? </span>
            <button
              onClick={() => navigate("/login")}
              className="text-sm text-shard-violet hover:text-shard-violet/80 font-medium"
            >
              Sign In
            </button>
            <span className="text-shard-gray mx-3">|</span>
            <button
              onClick={() => navigate("/chat")}
              className="text-sm text-shard-cyan hover:text-shard-cyan/80 font-medium"
            >
              Enter as Guest
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
