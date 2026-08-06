import { NextResponse } from "next/server";
import { getUser, ACCESS_COOKIE } from "@/lib/auth";
import { cookies } from "next/headers";

async function agentHeaders(): Promise<Record<string, string>> {
    const cookieStore = await cookies();
    const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
    return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

// Use AGENT_INTERNAL_URL for logs/admin — bypasses gateway, no auth needed on the call
const internalBase = () =>
    (process.env.AGENT_INTERNAL_URL || process.env.NEXT_PUBLIC_AGENT_URL || "").replace(/\/$/, "");

export async function GET() {
    const user = await getUser();
    if (!user) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const base = internalBase();
    if (!base) return NextResponse.json({ messages: [] });

    try {
        const res = await fetch(`${base}/incoming`, { next: { revalidate: 0 } });
        const data = await res.json();
        return NextResponse.json(data);
    } catch {
        return NextResponse.json({ messages: [] });
    }
}

export async function DELETE() {
    const user = await getUser();
    if (!user) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const base = internalBase();
    if (!base) return NextResponse.json({ ok: true });

    try {
        await fetch(`${base}/incoming`, { method: "DELETE" });
        return NextResponse.json({ ok: true });
    } catch {
        return NextResponse.json({ ok: false });
    }
}
