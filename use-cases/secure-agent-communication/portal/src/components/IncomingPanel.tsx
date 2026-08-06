"use client";

import { useState, useEffect, useRef } from "react";

interface IncomingMessage {
  from: string;
  to?: string;
  vp?: string;
  text: string;
  source: "agent" | "portal" | "forwarded";
  headers?: Record<string, string>;
  at: string;
}

export default function IncomingPanel({
  peerAgentName,
}: {
  peerAgentName: string;
}) {
  const [messages, setMessages] = useState<IncomingMessage[]>([]);
  const prevCountRef = useRef(0);

  async function clearLogs() {
    await fetch("/api/incoming", { method: "DELETE" });
    setMessages([]);
  }

  useEffect(() => {
    async function poll() {
      try {
        const res = await fetch("/api/incoming");
        const data = await res.json();
        if (Array.isArray(data.messages)) {
          setMessages(data.messages);
          prevCountRef.current = data.messages.length;
        }
      } catch {
        // silent — agent may not be reachable
      }
    }
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex-1 flex flex-col min-h-0 rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-xs text-slate-500">
            <span
              className="w-2 h-2 rounded-full inline-block"
              style={{ backgroundColor: "var(--brand-500)" }}
            />
            Peer agent
          </span>
          <span className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className="w-2 h-2 rounded-full bg-slate-600 inline-block" />
            Portal user
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-slate-600">live</span>
          {messages.length > 0 && (
            <button
              onClick={clearLogs}
              className="text-xs text-slate-600 hover:text-red-400 transition-colors ml-1"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto chat-scroll min-h-0">
        {messages.length === 0 ? (
          <p className="text-sm text-slate-600 px-4 py-3">
            No messages yet. Messages received by this agent will appear here.
          </p>
        ) : (
          <ul className="divide-y divide-slate-800/50">
            {[...messages].reverse().map((msg, i) => {
              const isForwarded = msg.source === "forwarded";
              const isAgent = msg.source === "agent";
              const initial = (msg.from || "?")[0].toUpperCase();

              // Outbound forwarded message — same layout as inbound, orange avatar
              if (isForwarded) {
                return (
                  <li key={i} className="px-4 py-3 flex items-start gap-3">
                    <div
                      className="shrink-0 mt-0.5 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white bg-orange-900"
                      title="Forwarded to peer"
                    >
                      ↗
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-slate-600 w-12 shrink-0">
                          To
                        </span>
                        <span className="text-xs font-medium text-slate-300">
                          {msg.to}
                        </span>
                        <span className="text-xs px-1.5 py-0.5 rounded-full text-orange-400 bg-orange-950 border border-orange-800">
                          forwarded
                        </span>
                      </div>
                      <div className="flex items-start gap-2 mb-1">
                        <span className="text-xs text-slate-600 w-12 shrink-0 mt-0.5">
                          Message
                        </span>
                        <p className="text-sm text-slate-200 break-words flex-1">
                          {msg.text}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-600 w-12 shrink-0">
                          Time
                        </span>
                        <span className="text-xs text-slate-500">
                          {new Date(msg.at).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  </li>
                );
              }

              return (
                <li key={i} className="px-4 py-3 flex items-start gap-3">
                  <div
                    className="shrink-0 mt-0.5 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white"
                    style={{
                      backgroundColor: isAgent ? "var(--brand-600)" : "#475569",
                    }}
                    title={isAgent ? "Peer agent" : "Portal user"}
                  >
                    {initial}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs text-slate-600 w-12 shrink-0">
                        From
                      </span>
                      <span className="text-xs font-medium text-slate-300">
                        {msg.from}
                      </span>
                      {msg.vp && <VpButton vp={msg.vp} />}
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded-full ${isAgent ? "text-brand bg-brand-faint" : "text-slate-500 bg-slate-800"}`}
                      >
                        {isAgent ? "agent" : "portal"}
                      </span>
                    </div>
                    <div className="flex items-start gap-2 mb-1">
                      <span className="text-xs text-slate-600 w-12 shrink-0 mt-0.5">
                        Message
                      </span>
                      <p className="text-sm text-slate-200 break-words flex-1">
                        {msg.text}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-600 w-12 shrink-0">
                        Time
                      </span>
                      <span className="text-xs text-slate-500">
                        {new Date(msg.at).toLocaleTimeString()}
                      </span>
                    </div>
                    {msg.headers && Object.keys(msg.headers).length > 0 && (
                      <details className="mt-1.5">
                        <summary className="text-xs text-slate-600 hover:text-slate-400 cursor-pointer select-none">
                          Headers ({Object.keys(msg.headers).length})
                        </summary>
                        <ul className="mt-1.5 space-y-1.5">
                          {Object.entries(msg.headers).map(([k, v]) => (
                            <li key={k} className="flex items-center gap-2">
                              <span
                                className="text-xs text-slate-500 shrink-0 font-mono w-32 truncate"
                                title={k}
                              >
                                {k}
                              </span>
                              <span
                                className="text-xs text-slate-300 font-mono truncate flex-1"
                                title={v}
                              >
                                {v}
                              </span>
                              <CopyButton value={v} />
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function VpButton({ vp }: { vp: string }) {
  const [open, setOpen] = useState(false);

  let pretty = vp;
  try {
    pretty = JSON.stringify(JSON.parse(vp), null, 2);
  } catch {
    // keep raw
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-xs px-1.5 py-0.5 rounded-full bg-green-950 text-green-400 border border-green-800 hover:bg-green-900 transition-colors"
      >
        Agent Identity ✓
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800">
              <span className="text-sm font-medium text-white">
                Verifiable Presentation
              </span>
              <button
                onClick={() => setOpen(false)}
                className="text-slate-500 hover:text-white text-lg leading-none"
              >
                ×
              </button>
            </div>
            <pre className="flex-1 overflow-auto p-5 text-xs text-slate-300 font-mono whitespace-pre-wrap break-all">
              {pretty}
            </pre>
          </div>
        </div>
      )}
    </>
  );
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <button
      onClick={copy}
      title="Copy value"
      className="shrink-0 text-xs px-1.5 py-0.5 rounded border border-slate-700 text-slate-500 hover:border-brand hover:text-brand transition-colors"
    >
      {copied ? "✓" : "Copy"}
    </button>
  );
}
