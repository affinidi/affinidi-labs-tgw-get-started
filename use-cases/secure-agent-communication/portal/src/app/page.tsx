"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const ORG_NAME = process.env.NEXT_PUBLIC_ORG_NAME || "Org";
const AGENT_NAME = process.env.NEXT_PUBLIC_AGENT_NAME || "Agent";

const OAUTH_ERRORS: Record<string, string> = {
  auth_cancelled: "Sign-in was cancelled.",
  token_exchange_failed: "Authentication failed. Please try again.",
  oauth_not_configured: "Microsoft login is not configured on this server.",
  no_email: "Could not retrieve your email from Microsoft.",
};

export default function LoginPage() {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState<"microsoft" | "guest" | null>(null);
  const router = useRouter();

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const e = p.get("error");
    if (e) setError(OAUTH_ERRORS[e] ?? `Login error: ${e}`);
  }, []);

  async function handleGuestLogin() {
    setLoading("guest");
    setError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ guest: true }),
      });
      if (res.ok) {
        router.push("/dashboard");
      } else {
        const data = await res.json();
        setError(data.error || "Login failed");
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 lg:flex">
      {/* Left: branding panel */}
      <div
        className="relative lg:w-2/5 flex flex-col justify-between p-12 overflow-hidden min-h-[40vh] lg:min-h-screen"
        style={{
          background:
            "linear-gradient(135deg, var(--brand-700) 0%, var(--brand-500) 55%, var(--brand-100) 100%)",
        }}
      >
        <div className="relative z-10">
          <p className="text-white/70 text-sm font-medium uppercase tracking-widest">
            {ORG_NAME}
          </p>
          <p className="text-white text-lg font-semibold mt-1">{AGENT_NAME}</p>
        </div>

        <div className="relative z-10 max-w-xs">
          <h1 className="text-3xl font-bold text-white leading-snug">
            Cross-org agent communication,{" "}
            <span className="text-white/80">secured by trust.</span>
          </h1>
          <p className="mt-4 text-white/60 text-sm">
            Powered by Affinidi Agent Gateway
          </p>
        </div>

        <div className="relative z-10 text-white/40 text-xs">
          {AGENT_NAME} · {ORG_NAME}
        </div>
      </div>

      {/* Right: login */}
      <div className="flex-1 flex items-center justify-center p-8 bg-slate-950">
        <div className="w-full max-w-md space-y-4">
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-white">Sign in</h2>
            <p className="mt-2 text-slate-400 text-sm">
              Access {AGENT_NAME} on behalf of {ORG_NAME}
            </p>
          </div>

          <a
            href="/api/auth/microsoft"
            onClick={() => setLoading("microsoft")}
            className="flex items-center justify-center gap-3 w-full py-3 px-4 bg-white text-slate-900 rounded-lg font-medium hover:bg-slate-100 transition-colors"
          >
            <MicrosoftLogo />
            {loading === "microsoft"
              ? "Redirecting…"
              : "Sign in with Microsoft"}
          </a>

          <button
            onClick={handleGuestLogin}
            disabled={loading !== null}
            className="flex items-center justify-center w-full py-3 px-4 border border-slate-700 text-slate-300 rounded-lg font-medium hover:border-slate-500 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading === "guest" ? "Signing in…" : "Sign in as Guest"}
          </button>

          {error && (
            <div className="p-3 bg-red-950/60 border border-red-800 rounded-lg text-red-300 text-sm">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MicrosoftLogo() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 21 21"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M10 1H1v9h9V1Z" fill="#F25022" />
      <path d="M20 1h-9v9h9V1Z" fill="#7FBA00" />
      <path d="M10 11H1v9h9v-9Z" fill="#00A4EF" />
      <path d="M20 11h-9v9h9v-9Z" fill="#FFB900" />
    </svg>
  );
}
