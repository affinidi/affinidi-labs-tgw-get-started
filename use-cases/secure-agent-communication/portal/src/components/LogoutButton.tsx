"use client";

export default function LogoutButton() {
  return (
    <button
      onClick={async () => {
        await fetch("/api/auth/logout", { method: "POST" });
        window.location.href = "/";
      }}
      className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 rounded"
    >
      Sign out
    </button>
  );
}
