"use client";

import { useState } from "react";

interface Props {
  title: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export default function CollapsibleSection({
  title,
  defaultOpen = true,
  children,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="flex flex-col min-h-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2.5 w-full px-1 py-1.5 mb-2 text-slate-300 hover:text-white transition-colors group"
      >
        <span
          className="text-slate-500 group-hover:text-slate-300 transition-colors text-sm"
          style={{ lineHeight: 1 }}
        >
          {open ? "▾" : "▸"}
        </span>
        <span className="text-sm font-medium">{title}</span>
        <span className="flex-1 border-t border-slate-800 group-hover:border-slate-700 transition-colors ml-1" />
      </button>
      {open && <div className="flex-1 flex flex-col min-h-0">{children}</div>}
    </div>
  );
}
