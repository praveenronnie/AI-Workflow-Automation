import { useState } from "react";
import { LogIn, UserPlus } from "lucide-react";
import { useStore } from "@/store/useStore";
import { Button } from "@/features/shared/components/ui/button";
import { login, signup, logout } from "@/lib/messaging";

export function LoginSection() {
  const {
    isAuthenticated,
    userEmail,
    setAuthenticated,
    setUserEmail,
    setReportId,
  } = useStore();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async () => {
    setError("");
    setBusy(true);
    try {
      const res =
        mode === "login"
          ? await login(email, password)
          : await signup(email, password, name);
      if (res.success) {
        setAuthenticated(true);
        setUserEmail(email);
      } else {
        setError(res.error || "Authentication failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      // Optimistically update state; background will send UPDATE_UI_STATE to confirm.
      setAuthenticated(false);
      setUserEmail("");
      setReportId(null);
    } catch (err) {
      console.error("Logout failed:", err);
      // Optionally show error to user
    }
  };

  if (isAuthenticated) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
        <span className="truncate text-muted-foreground">{userEmail || "Logged in"}</span>
        <Button variant="outline" size="xs" onClick={handleLogout}>
          Log out
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="flex gap-2">
        <Button
          variant={mode === "login" ? "default" : "outline"}
          size="xs"
          className="flex-1"
          onClick={() => setMode("login")}
        >
          <LogIn className="size-3.5" /> Login
        </Button>
        <Button
          variant={mode === "signup" ? "default" : "outline"}
          size="xs"
          className="flex-1"
          onClick={() => setMode("signup")}
        >
          <UserPlus className="size-3.5" /> Sign up
        </Button>
      </div>
      {mode === "signup" && (
        <input
          className="w-full rounded-md border px-3 py-1.5 text-sm"
          placeholder="Name (optional)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      )}
      <input
        className="w-full rounded-md border px-3 py-1.5 text-sm"
        placeholder="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <input
        className="w-full rounded-md border px-3 py-1.5 text-sm"
        placeholder="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
      <Button className="w-full" size="sm" disabled={busy} onClick={handleSubmit}>
        {busy ? "Please wait..." : mode === "login" ? "Login" : "Create account"}
      </Button>
    </div>
  );
}