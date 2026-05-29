import { Link } from "react-router-dom";
import { SignIn } from "@/components/SignIn";
import { TestUserLoginSection } from "@/components/TestUserLoginSection";
import { Button } from "@/components/ui/button";
import { Terminal } from "lucide-react";

export function LoginPage() {
  return (
    <div className="flex-1 flex items-center justify-center p-4 relative min-h-screen bg-[#06060F]">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute top-0 left-1/4 size-96 rounded-full bg-[#1E90FF]/5 blur-3xl" />
        <div className="absolute bottom-0 right-1/4 size-96 rounded-full bg-[#FFD700]/3 blur-3xl" />
      </div>

      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-2">
          <div className="mx-auto size-12 rounded-xl bg-gradient-to-br from-[#1E90FF] to-[#00d4aa] flex items-center justify-center mb-4 j-glow">
            <Terminal className="size-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Welcome back</h1>
          <p className="text-[#8888a0] text-sm">
            Sign in to continue to J Cloud
          </p>
        </div>

        <TestUserLoginSection />
        <SignIn />

        <p className="text-center text-sm text-[#8888a0]">
          Don't have an account?{" "}
          <Button variant="link" className="p-0 h-auto font-medium text-[#1E90FF]" asChild>
            <Link to="/signup">Sign up</Link>
          </Button>
        </p>
      </div>
    </div>
  );
}
