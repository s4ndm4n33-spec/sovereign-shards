import { useAuthActions } from "@convex-dev/auth/react";
import { ArrowLeft, Loader2, Mail } from "lucide-react";
import { useState } from "react";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

function isTestEmail(email: string): boolean {
  return email.endsWith("@test.local");
}

type Step = "signUp" | { email: string };

export function SignUp() {
  const { signIn } = useAuthActions();
  const [step, setStep] = useState<Step>("signUp");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (step === "signUp") {
    return (
      <Card variant="elevated">
        <CardContent className="pt-6">
          <form
            onSubmit={async e => {
              e.preventDefault();
              setError("");
              setLoading(true);

              const formData = new FormData(e.currentTarget);
              const email = formData.get("email") as string;
              const provider = isTestEmail(email) ? "test" : "password";
              try {
                await signIn(provider, formData);
                if (!isTestEmail(email)) {
                  setStep({ email });
                }
              } catch {
                setError("Could not create account. Please try again.");
              } finally {
                setLoading(false);
              }
            }}
            className="space-y-4"
          >
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                name="name"
                type="text"
                placeholder="Your name"
                autoComplete="name"
                className="h-11"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="you@example.com"
                autoComplete="email"
                className="h-11"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="••••••••"
                minLength={6}
                autoComplete="new-password"
                className="h-11"
                required
              />
              <p className="text-xs text-muted-foreground">
                Must be at least 6 characters
              </p>
            </div>
            <input name="flow" value="signUp" type="hidden" />
            {error && (
              <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full h-11" disabled={loading}>
              {loading && <Loader2 className="size-4 animate-spin" />}
              {loading ? "Creating account..." : "Create Account"}
            </Button>
          </form>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card variant="elevated">
      <CardContent className="pt-6">
        <div className="text-center mb-6">
          <div className="mx-auto size-12 rounded-full bg-primary flex items-center justify-center mb-4">
            <Mail className="size-6 text-primary-foreground" />
          </div>
          <h2 className="font-semibold text-lg">Check your email</h2>
          <p className="text-sm text-muted-foreground">
            We sent a verification code to {step.email}
          </p>
        </div>
        <form
          onSubmit={async e => {
            e.preventDefault();
            setError("");
            setLoading(true);

            const formData = new FormData(e.currentTarget);
            try {
              await signIn("password", formData);
            } catch {
              setError("Invalid or expired code. Please try again.");
            } finally {
              setLoading(false);
            }
          }}
          className="space-y-4"
        >
          <div className="space-y-2">
            <Label htmlFor="code">Verification Code</Label>
            <Input
              id="code"
              name="code"
              type="text"
              placeholder="Enter code"
              autoComplete="one-time-code"
              className="h-11 text-center tracking-[0.5em] font-mono"
              required
            />
          </div>
          <input name="flow" value="email-verification" type="hidden" />
          <input name="email" value={step.email} type="hidden" />
          {error && (
            <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full h-11" disabled={loading}>
            {loading && <Loader2 className="size-4 animate-spin" />}
            {loading ? "Verifying..." : "Verify Email"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="w-full"
            onClick={() => setStep("signUp")}
          >
            <ArrowLeft className="size-4" />
            Back to sign up
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
