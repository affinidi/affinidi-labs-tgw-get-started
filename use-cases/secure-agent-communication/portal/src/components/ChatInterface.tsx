"use client";

import { useState, useRef, useEffect } from "react";
import type { ChatMessage } from "@/lib/types";

interface Props {
  agentName: string;
  peerAgentName: string;
}

export default function ChatInterface({ agentName, peerAgentName }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const samplePrompts = [
    "Hi, how are you?",
    "What can you do?",
    `Tell ${peerAgentName}: Hello!`,
    `Ask ${peerAgentName} how they are`,
    `Ping ${peerAgentName}`,
    `Message ${peerAgentName}: Checking in from ${agentName}`,
  ];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: text.trim(),
      fromPeer: false,
      isError: false,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text.trim() }),
      });

      let data: Record<string, unknown>;
      try {
        data = await res.json();
      } catch {
        data = {
          isError: true,
          errorMessage: `Server returned HTTP ${res.status} with no JSON body. Check that the agent is reachable.`,
          raw: null,
        };
      }

      const agentMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "agent",
        text: data.isError
          ? String(data.errorMessage || "Unknown error")
          : String(data.text ?? ""),
        fromPeer: data.fromPeer === true,
        agentName: data.agentName as string | undefined,
        peerName: data.peerName as string | undefined,
        isError: !!data.isError,
        raw: data.raw,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "agent",
          text: String(err),
          fromPeer: false,
          isError: true,
          raw: err,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      {/* Sample prompts + clear */}
      <div className="shrink-0 flex flex-wrap items-center gap-2 px-4 pt-4 pb-3 border-b border-slate-800">
        {samplePrompts.map((prompt) => (
          <button
            key={prompt}
            onClick={() => sendMessage(prompt)}
            disabled={loading}
            className="text-xs px-3 py-1.5 rounded-full border border-slate-700 text-slate-400 hover:border-brand hover:text-brand transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {prompt}
          </button>
        ))}
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="ml-auto text-xs text-slate-600 hover:text-red-400 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto chat-scroll px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-slate-600 text-sm text-center">
              Start a conversation with {agentName}.
              <br />
              Try a sample prompt above.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            msg={msg}
            agentName={agentName}
            peerAgentName={peerAgentName}
          />
        ))}

        {loading && (
          <div className="flex items-start gap-3">
            <AgentAvatar />
            <div className="flex items-center gap-1.5 px-4 py-3 rounded-2xl rounded-tl-sm bg-slate-800 text-slate-400 text-sm">
              <span className="animate-pulse">●</span>
              <span className="animate-pulse delay-100">●</span>
              <span className="animate-pulse delay-200">●</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 px-4 py-3 border-t border-slate-800">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            placeholder={`Message ${agentName}…`}
            className="flex-1 px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 bg-brand hover:bg-brand-hover text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

function MessageBubble({
  msg,
  agentName,
  peerAgentName,
}: {
  msg: ChatMessage;
  agentName: string;
  peerAgentName: string;
}) {
  const isForwarded = msg.fromPeer;
  const sourceName = isForwarded
    ? (msg.peerName ?? peerAgentName)
    : (msg.agentName ?? agentName);

  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] space-y-1">
          <div className="px-4 py-2.5 rounded-2xl rounded-tr-sm bg-brand text-white text-sm whitespace-pre-wrap break-words">
            {msg.text}
          </div>
          <p className="text-xs text-slate-600 text-right">You</p>
        </div>
      </div>
    );
  }

  const bubbleBg = msg.isError
    ? "bg-red-950/60 border border-red-800"
    : isForwarded
      ? "border border-[var(--brand-700)] bg-[color-mix(in_srgb,var(--brand-700)_15%,transparent)]"
      : "bg-slate-800";

  return (
    <div className="flex items-start gap-3">
      <AgentAvatar isForwarded={isForwarded} isError={msg.isError} />
      <div className="max-w-[80%] space-y-1">
        <div
          className={`px-4 py-2.5 rounded-2xl rounded-tl-sm text-sm whitespace-pre-wrap break-words ${bubbleBg}`}
        >
          {msg.isError && (
            <p className="text-red-400 font-medium text-xs mb-1">Error</p>
          )}
          <span className={msg.isError ? "text-red-200" : "text-slate-100"}>
            {msg.text}
          </span>
        </div>

        {/* Source label */}
        <p className="text-xs text-slate-600">
          {isForwarded ? (
            <>
              <span
                style={{ color: "var(--brand-500)" }}
                className="font-medium"
              >
                {sourceName}
              </span>
              <span className="text-slate-600"> · via {agentName}</span>
            </>
          ) : (
            <span className={msg.isError ? "text-red-500" : "text-slate-500"}>
              {sourceName}
            </span>
          )}
        </p>

        {/* Raw response — collapsible, always shown for agent messages */}
        {msg.raw != null && (
          <details className="mt-1">
            <summary className="text-xs text-slate-600 hover:text-slate-400 cursor-pointer select-none">
              Raw response
            </summary>
            <pre className="mt-1 text-xs text-slate-400 bg-slate-950 rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap break-all">
              {JSON.stringify(msg.raw, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
function AgentAvatar({
  isForwarded = false,
  isError = false,
}: {
  isForwarded?: boolean;
  isError?: boolean;
}) {
  const bg = isError
    ? "bg-red-900/50 text-red-400"
    : isForwarded
      ? "text-white"
      : "bg-slate-700 text-slate-300";

  return (
    <div
      className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${bg}`}
      style={
        isForwarded && !isError
          ? { backgroundColor: "var(--brand-700)" }
          : undefined
      }
    >
      {isError ? "!" : isForwarded ? "P" : "A"}
    </div>
  );
}
