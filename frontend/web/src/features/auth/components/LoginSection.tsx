import { useState } from "react";
import { useStore } from "@/store/useStore";
import { Button } from "@/features/shared/components/ui/button";
import { login, signup } from "@/lib/messaging";

export function LoginSection() {
  const { isAuthenticated, setAuthenticated, setUserEmail } = useStore();
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

  if (isAuthenticated) {
    return null;
  }

  return (
    <div className="mx-auto flex h-full max-w-[340px] flex-col justify-center px-2 py-6">
      {/* Brand */}
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 flex size-11 items-center justify-center rounded-xl bg-primary text-lg font-bold text-primary-foreground">
          F
        </div>
        <h1 className="text-lg font-semibold">FormIQ</h1>
        <p className="mt-1 text-xs leading-snug text-muted-foreground">
          Upload inspection documents, scan any web form, review with
          confidence, fill in one click.
        </p>
      </div>

      {/* Card */}
      <div className="space-y-3 rounded-xl border bg-card p-4 shadow-sm">
        <div className="flex gap-1 rounded-lg bg-muted p-1">
          <button
            className={`flex-1 rounded-md py-1 text-xs font-medium transition-colors ${
              mode === "login"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setMode("login")}
          >
            Login
          </button>
          <button
            className={`flex-1 rounded-md py-1 text-xs font-medium transition-colors ${
              mode === "signup"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setMode("signup")}
          >
            Sign up
          </button>
        </div>
        {mode === "signup" && (
          <input
            className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:border-ring"
            placeholder="Name (optional)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        )}
        <input
          className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:border-ring"
          placeholder="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:border-ring"
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !busy && handleSubmit()}
        />
        {error && <p className="text-xs text-destructive">{error}</p>}
        <Button className="w-full" size="lg" disabled={busy} onClick={handleSubmit}>
          {busy
            ? "Please wait..."
            : mode === "login"
              ? "Log in"
              : "Create account"}
        </Button>
      </div>
    </div>
  );
}