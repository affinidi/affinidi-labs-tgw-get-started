"use client";

import { useState } from "react";
import FlowDiagram from "@/components/FlowDiagram";

interface Props {
  agentName: string;
  agentDescription: string;
  orgName: string;
  peerAgentName: string;
  agentCardUrl: string;
  agentUrl: string;
}

export default function AgentInfoCard({
  agentName,
  agentDescription,
  orgName,
  peerAgentName,
  agentCardUrl,
  agentUrl,
}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="shrink-0 rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      {/* Always-visible header — click to expand/collapse details */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-800/40 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <span
            className="w-3 h-3 rounded-full shrink-0"
            style={{ backgroundColor: "var(--brand-500)" }}
          />
          <div>
            <h2 className="text-base font-semibold text-white">{agentName}</h2>
            {agentDescription && (
              <p className="text-xs text-slate-400 mt-0.5 text-left">
                {agentDescription}
              </p>
            )}
          </div>
        </div>
        <span className="text-slate-500 text-sm ml-4">{open ? "▾" : "▸"}</span>
      </button>

      {/* Collapsible details */}
      {open && (
        <div className="px-5 pb-4 border-t border-slate-800">
          <div className="flex flex-wrap items-center gap-4 pt-3">
            {agentCardUrl && (
              <a
                href={agentCardUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-brand hover:text-brand-hover transition-colors"
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 16 16"
                  fill="currentColor"
                >
                  <path d="M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 0 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5z" />
                  <path d="M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0v-5z" />
                </svg>
                Agent Card
              </a>
            )}
            {agentUrl && (
              <span className="text-xs text-slate-600 font-mono select-all">
                {agentUrl}
              </span>
            )}
            <span className="text-xs text-slate-500">
              Communicates with{" "}
              <span className="text-slate-300 font-medium">
                {peerAgentName}
              </span>
            </span>
          </div>
          <FlowDiagram
            orgName={orgName}
            agentName={agentName}
            peerAgentName={peerAgentName}
          />
        </div>
      )}
    </div>
  );
}
