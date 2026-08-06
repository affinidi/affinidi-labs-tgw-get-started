import { getUser } from "@/lib/auth";
import { redirect } from "next/navigation";
import TabView from "@/components/TabView";
import LogoutButton from "@/components/LogoutButton";
import AgentInfoCard from "@/components/AgentInfoCard";

const ORG_NAME = process.env.NEXT_PUBLIC_ORG_NAME || "Org";
const AGENT_NAME = process.env.NEXT_PUBLIC_AGENT_NAME || "Agent";
const AGENT_DESCRIPTION = process.env.NEXT_PUBLIC_AGENT_DESCRIPTION || "";
const PEER_AGENT_NAME = process.env.NEXT_PUBLIC_PEER_AGENT_NAME || "Peer Agent";
const AGENT_CARD_URL = process.env.NEXT_PUBLIC_AGENT_URL
  ? `${process.env.NEXT_PUBLIC_AGENT_URL.replace(/\/$/, "")}/.well-known/agent-card.json`
  : "";
const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL || "";

export default async function DashboardPage() {
  const user = await getUser();
  if (!user) redirect("/");

  return (
    <div className="h-screen flex flex-col bg-slate-950 overflow-hidden">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-slate-900 shrink-0">
        <div className="flex items-center gap-3">
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: "var(--brand-500)" }}
          />
          <span className="text-sm font-semibold text-slate-100">
            {ORG_NAME}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-400">{user.name}</span>
          <LogoutButton />
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden max-w-4xl w-full mx-auto px-4 py-4 gap-4">
        {/* Agent info card — click name to expand details */}
        <AgentInfoCard
          agentName={AGENT_NAME}
          agentDescription={AGENT_DESCRIPTION}
          orgName={ORG_NAME}
          peerAgentName={PEER_AGENT_NAME}
          agentCardUrl={AGENT_CARD_URL}
          agentUrl={AGENT_URL}
        />

        {/* Tabbed: Chat / Incoming */}
        <TabView agentName={AGENT_NAME} peerAgentName={PEER_AGENT_NAME} />
      </main>
    </div>
  );
}
