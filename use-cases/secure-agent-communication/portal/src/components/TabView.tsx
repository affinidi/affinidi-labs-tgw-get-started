"use client";

import { useState, useEffect } from "react";
import ChatInterface from "@/components/ChatInterface";
import IncomingPanel from "@/components/IncomingPanel";

interface Props {
  agentName: string;
  peerAgentName: string;
}

export default function TabView({ agentName, peerAgentName }: Props) {
  const [tab, setTab] = useState<"chat" | "incoming">("chat");
  const [incomingCount, setIncomingCount] = useState(0);
  const [unseenCount, setUnseenCount] = useState(0);
  const lastSeenRef = { current: 0 };

  useEffect(() => {
    async function poll() {
      try {
        const res = await fetch("/api/incoming");
        const data = await res.json();
        const count = Array.isArray(data.messages) ? data.messages.length : 0;
        setIncomingCount(count);
        if (tab !== "incoming") {
          setUnseenCount((prev) => Math.max(0, count - lastSeenRef.current));
        } else {
          lastSeenRef.current = count;
          setUnseenCount(0);
        }
      } catch {
        // silent
      }
    }
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, [tab]);

  function switchTab(t: "chat" | "incoming") {
    setTab(t);
    if (t === "incoming") {
      lastSeenRef.current = incomingCount;
      setUnseenCount(0);
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Tab bar */}
      <div className="shrink-0 flex border-b border-slate-800 bg-slate-900/50">
        <TabButton
          active={tab === "chat"}
          onClick={() => switchTab("chat")}
          label="Chat"
          icon="💬"
        />
        <TabButton
          active={tab === "incoming"}
          onClick={() => switchTab("incoming")}
          label="Agent Log"
          icon="📋"
          badge={unseenCount > 0 ? unseenCount : undefined}
        />
      </div>

      {/* Tab content */}
      <div className="flex-1 flex flex-col min-h-0 pt-4">
        {tab === "chat" ? (
          <ChatInterface agentName={agentName} peerAgentName={peerAgentName} />
        ) : (
          <IncomingPanel peerAgentName={peerAgentName} />
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  label,
  icon,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  icon: string;
  badge?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
        active
          ? "border-brand text-white"
          : "border-transparent text-slate-500 hover:text-slate-300 hover:border-slate-700"
      }`}
    >
      <span>{icon}</span>
      {label}
      {badge != null && badge > 0 && (
        <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-brand text-white leading-none">
          {badge}
        </span>
      )}
    </button>
  );
}
