import { Link } from "react-router-dom";
import { SignUp } from "@/components/SignUp";
import { TestUserLoginSection } from "@/components/TestUserLoginSection";
import { Button } from "@/components/ui/button";

export function SignupPage() {
  return (
    <div className="flex-1 flex items-center justify-center p-4 relative">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute top-0 right-1/4 size-96 rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute bottom-0 left-1/4 size-96 rounded-full bg-primary/5 blur-3xl" />
      </div>

      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-2">
          <div className="mx-auto size-12 rounded-xl bg-primary flex items-center justify-center mb-4">
            <span className="text-primary-foreground font-bold text-lg">M</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">
            Create an account
          </h1>
          <p className="text-muted-foreground text-sm">
            Get started with your free account
          </p>
        </div>

        <TestUserLoginSection />
        <SignUp />

        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Button variant="link" className="p-0 h-auto font-medium" asChild>
            <Link to="/login">Sign in</Link>
          </Button>
        </p>
      </div>
    </div>
  );
}
