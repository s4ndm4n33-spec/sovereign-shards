import { Link } from "react-router-dom";
import { SignUp } from "@/components/SignUp";
import { Button } from "@/components/ui/button";
import { Terminal } from "lucide-react";

export function SignupPage() {
  return (
    <div className="flex-1 flex items-center justify-center p-4 relative min-h-screen bg-[#06060F]">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute top-0 right-1/4 size-96 rounded-full bg-[#1E90FF]/5 blur-3xl" />
        <div className="absolute bottom-0 left-1/4 size-96 rounded-full bg-[#00d4aa]/3 blur-3xl" />
      </div>

      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-2">
          <div className="mx-auto size-12 rounded-xl bg-gradient-to-br from-[#1E90FF] to-[#00d4aa] flex items-center justify-center mb-4 j-glow">
            <Terminal className="size-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Create account</h1>
          <p className="text-[#8888a0] text-sm">
            Get access to J Cloud — your AI dev agent
          </p>
        </div>

        <SignUp />

        <p className="text-center text-sm text-[#8888a0]">
          Already have an account?{" "}
          <Button variant="link" className="p-0 h-auto font-medium text-[#1E90FF]" asChild>
            <Link to="/login">Sign in</Link>
          </Button>
        </p>
      </div>
    </div>
  );
}
