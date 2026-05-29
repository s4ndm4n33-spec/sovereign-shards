import { useAuthActions } from "@convex-dev/auth/react";
import { useMutation, useQuery } from "convex/react";
import { ChevronRight, Loader2, Moon, Palette, Sun, User } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useTheme } from "@/contexts/ThemeContext";
import { api } from "../../convex/_generated/api";

export function SettingsPage() {
  const user = useQuery(api.auth.currentUser);
  const { theme, toggleTheme, switchable } = useTheme();
  const { signIn, signOut } = useAuthActions();
  const deleteAccount = useMutation(api.users.deleteAccount);
  const navigate = useNavigate();

  const [changePasswordOpen, setChangePasswordOpen] = useState(false);
  const [deleteAccountOpen, setDeleteAccountOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [passwordStep, setPasswordStep] = useState<"request" | "verify">(
    "request",
  );

  const handleRequestPasswordReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData();
    formData.append("email", user?.email || "");
    formData.append("flow", "reset");

    try {
      await signIn("password", formData);
      setPasswordStep("verify");
    } catch {
      setError("Could not send reset code. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(e.currentTarget);
    formData.append("email", user?.email || "");
    formData.append("flow", "reset-verification");

    try {
      await signIn("password", formData);
      setSuccess("Password changed successfully!");
      setTimeout(() => {
        setChangePasswordOpen(false);
        setPasswordStep("request");
        setSuccess("");
      }, 1500);
    } catch {
      setError("Invalid code or password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAccount = async () => {
    setLoading(true);
    setError("");

    try {
      await deleteAccount();
      await signOut();
      navigate("/");
    } catch {
      setError("Could not delete account. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 max-w-2xl mx-auto">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
          Settings
        </h1>
        <p className="text-muted-foreground mt-1">Page subtitle goes here</p>
      </div>

      <Card className="overflow-hidden">
        <div className="h-20 bg-gradient-to-r from-primary/20 via-primary/10 to-transparent" />
        <CardContent className="-mt-10 pb-6">
          <div className="flex items-end gap-4">
            <Avatar className="size-16 border-4 border-background shadow-lg">
              <AvatarFallback className="text-xl bg-primary text-primary-foreground">
                {user?.name?.charAt(0).toUpperCase() || (
                  <User className="size-6" />
                )}
              </AvatarFallback>
            </Avatar>
            <div className="pb-1">
              <p className="font-semibold">{user?.name || "User"}</p>
              <p className="text-sm text-muted-foreground">{user?.email}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <Palette className="size-4 text-muted-foreground" />
            Appearance
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {switchable ? (
            <div className="flex items-center justify-between rounded-lg border p-4 transition-colors hover:bg-muted/50">
              <div className="flex items-center gap-4">
                <div className="size-10 rounded-full bg-secondary flex items-center justify-center">
                  {theme === "light" ? (
                    <Moon className="size-5 text-foreground" />
                  ) : (
                    <Sun className="size-5 text-foreground" />
                  )}
                </div>
                <div>
                  <Label htmlFor="dark-mode" className="font-medium">
                    Dark mode
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Toggle description goes here
                  </p>
                </div>
              </div>
              <Switch
                id="dark-mode"
                checked={theme === "dark"}
                onCheckedChange={toggleTheme}
              />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground px-4 py-2">
              Theme follows your system preference
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <User className="size-4 text-muted-foreground" />
            Account
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <button
            onClick={() => setChangePasswordOpen(true)}
            className="w-full flex items-center justify-between rounded-lg border p-4 transition-colors hover:bg-muted/50 text-left"
          >
            <div>
              <p className="font-medium text-sm">Change password</p>
              <p className="text-sm text-muted-foreground">
                Update your password
              </p>
            </div>
            <ChevronRight className="size-4 text-muted-foreground" />
          </button>
          <button
            onClick={() => setDeleteAccountOpen(true)}
            className="w-full flex items-center justify-between rounded-lg border border-destructive/20 p-4 transition-colors hover:bg-destructive/5 text-left"
          >
            <div>
              <p className="font-medium text-sm text-destructive">
                Delete account
              </p>
              <p className="text-sm text-muted-foreground">
                Permanently delete your account
              </p>
            </div>
            <ChevronRight className="size-4 text-destructive" />
          </button>
        </CardContent>
      </Card>

      <Dialog open={changePasswordOpen} onOpenChange={setChangePasswordOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Password</DialogTitle>
            <DialogDescription>
              {passwordStep === "request"
                ? "We'll send a verification code to your email."
                : "Enter the code from your email and your new password."}
            </DialogDescription>
          </DialogHeader>

          {passwordStep === "request" ? (
            <form onSubmit={handleRequestPasswordReset}>
              <div className="py-4">
                <p className="text-sm text-muted-foreground">
                  A reset code will be sent to:{" "}
                  <span className="font-medium text-foreground">
                    {user?.email}
                  </span>
                </p>
              </div>
              {error && (
                <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2 mb-4">
                  {error}
                </p>
              )}
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setChangePasswordOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={loading}>
                  {loading && <Loader2 className="size-4 animate-spin" />}
                  Send Code
                </Button>
              </DialogFooter>
            </form>
          ) : (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="code">Verification Code</Label>
                <Input
                  id="code"
                  name="code"
                  type="text"
                  placeholder="Enter code from email"
                  autoComplete="one-time-code"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="newPassword">New Password</Label>
                <Input
                  id="newPassword"
                  name="newPassword"
                  type="password"
                  placeholder="••••••••"
                  minLength={6}
                  autoComplete="new-password"
                  required
                />
              </div>
              {error && (
                <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}
              {success && (
                <p className="text-sm text-success bg-success/10 rounded-lg px-3 py-2">
                  {success}
                </p>
              )}
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setPasswordStep("request");
                    setError("");
                  }}
                >
                  Back
                </Button>
                <Button type="submit" disabled={loading}>
                  {loading && <Loader2 className="size-4 animate-spin" />}
                  Change Password
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={deleteAccountOpen} onOpenChange={setDeleteAccountOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Account</DialogTitle>
            <DialogDescription>
              This action cannot be undone. This will permanently delete your
              account and remove all your data.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-muted-foreground">
              Are you sure you want to delete your account?
            </p>
          </div>
          {error && (
            <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteAccountOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteAccount}
              disabled={loading}
            >
              {loading && <Loader2 className="size-4 animate-spin" />}
              Delete Account
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
