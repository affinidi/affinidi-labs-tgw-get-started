interface Props {
  orgName: string;
  agentName: string;
  peerAgentName: string;
}

export default function FlowDiagram({
  orgName,
  agentName,
  peerAgentName,
}: Props) {
  const peerOrg = peerAgentName.replace(" Agent", "");

  return (
    <div className="mt-4 pt-4 border-t border-slate-800">
      <p className="text-xs text-slate-600 mb-3 uppercase tracking-wider">
        Communication flow
      </p>
      <div className="flex items-end gap-2 flex-wrap">
        {/* Org A boundary */}
        <div className="flex flex-col gap-1">
          <span
            className="text-xs font-medium px-1"
            style={{ color: "var(--brand-500)" }}
          >
            {orgName}
          </span>
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed"
            style={{ borderColor: "var(--brand-700)" }}
          >
            <Node label="User" sub="browser" />
            <Arrow label="OAuth" />
            <Node label="Portal" sub="web app" highlighted />
            <Arrow label="A2A" />
            <Node label={agentName} sub="this agent" branded />
          </div>
        </div>

        {/* Cross-org arrow */}
        <div className="flex items-center pb-2">
          <Arrow label="A2A" bidirectional />
        </div>

        {/* Org B boundary */}
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-slate-500 px-1">
            Cross Org
          </span>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-slate-700">
            <Node label={peerAgentName} sub="peer agent" />
          </div>
        </div>
      </div>
    </div>
  );
}

function Node({
  label,
  sub,
  highlighted,
  branded,
}: {
  label: string;
  sub: string;
  highlighted?: boolean;
  branded?: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className="px-2.5 py-1.5 rounded-lg border text-xs font-medium whitespace-nowrap"
        style={
          branded
            ? {
                borderColor: "var(--brand-600)",
                backgroundColor:
                  "color-mix(in srgb, var(--brand-700) 20%, transparent)",
                color: "var(--brand-100)",
              }
            : highlighted
              ? {
                  borderColor: "#475569",
                  backgroundColor: "#1e293b",
                  color: "#cbd5e1",
                }
              : {
                  borderColor: "#334155",
                  backgroundColor: "#0f172a",
                  color: "#94a3b8",
                }
        }
      >
        {label}
      </div>
      <span className="text-xs text-slate-600">{sub}</span>
    </div>
  );
}

function Arrow({
  label,
  bidirectional = false,
}: {
  label: string;
  bidirectional?: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className="flex items-center gap-0.5 text-slate-600">
        {bidirectional && <span className="text-xs leading-none">◄</span>}
        <div className="w-6 h-px bg-slate-700" />
        <span className="text-xs leading-none">►</span>
      </div>
      <span className="text-xs text-slate-600">{label}</span>
    </div>
  );
}
