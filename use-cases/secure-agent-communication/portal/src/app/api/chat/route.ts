import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { randomUUID } from "crypto";
import { getUser, ACCESS_COOKIE } from "@/lib/auth";

const IDENTITY_EXT_URI =
    "https://fabric.affinidi.io/extensions/agent-identity/v1";

export async function POST(req: NextRequest) {
    const user = await getUser();
    if (!user) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { message } = await req.json();
    if (!message?.trim()) {
        return NextResponse.json({ error: "Message is required" }, { status: 400 });
    }

    const agentUrl = (process.env.NEXT_PUBLIC_AGENT_URL || "").replace(/\/$/, "") + "/a2a/tasks/send";
    if (!process.env.NEXT_PUBLIC_AGENT_URL) {
        return NextResponse.json(
            { error: "NEXT_PUBLIC_AGENT_URL is not configured" },
            { status: 500 },
        );
    }

    // Read the Entra access token from cookie and forward it to the agent
    const cookieStore = await cookies();
    const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;

    const headers: Record<string, string> = {
        "Content-Type": "application/json",
    };
    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }

    const taskId = randomUUID();
    const messageId = randomUUID().replace(/-/g, "");
    const sessionId = randomUUID().replace(/-/g, "");

    const a2aPayload = {
        jsonrpc: "2.0",
        id: taskId,
        method: "message/send",
        params: {
            message: {
                role: "user",
                kind: "message",
                messageId,
                contextId: sessionId,
                parts: [
                    {
                        kind: "data",
                        data: {
                            action: "send:message",
                            text: message,
                        },
                    },
                ],
                extensions: [IDENTITY_EXT_URI],
                metadata: {
                    [IDENTITY_EXT_URI]: {
                        agentIdentity: {
                            name: `${user.org} Portal`,
                            model: "None",
                            role: "Portal Client App",
                            version: "1.0.0",
                        },
                    },
                },
            },
        },
    };

    let data: unknown;
    try {
        const agentRes = await fetch(agentUrl, {
            method: "POST",
            headers,
            body: JSON.stringify(a2aPayload),
        });

        // Read as text first so we can show the raw body even if it's not JSON
        const rawBody = await agentRes.text();
        try {
            data = JSON.parse(rawBody);
        } catch {
            return NextResponse.json({
                isError: true,
                errorMessage: `Agent at ${agentUrl} returned HTTP ${agentRes.status} with a non-JSON response.`,
                raw: rawBody,
            });
        }

        if (!agentRes.ok) {
            return NextResponse.json({
                isError: true,
                errorMessage: `Agent returned HTTP ${agentRes.status}`,
                raw: data,
            });
        }
    } catch (err) {
        return NextResponse.json({
            isError: true,
            errorMessage: `Could not reach agent at ${agentUrl}: ${String(err)}`,
            raw: null,
        });
    }

    // Parse a2a-sdk JSON-RPC response — check for error first
    const rpcError = (data as Record<string, unknown>)?.error as Record<string, unknown> | undefined;
    if (rpcError) {
        return NextResponse.json({
            isError: true,
            errorMessage: String(rpcError.message || rpcError),
            raw: data,
        });
    }

    const result = (data as Record<string, unknown>)?.result as Record<string, unknown>;

    // a2a-sdk: result.status.message  |  flat: result.parts  |  history fallback
    const statusMsg = (result?.status as Record<string, unknown>)?.message as Record<string, unknown>;
    const historyLast = Array.isArray(result?.history)
        ? (result.history as Record<string, unknown>[])[result.history.length - 1]
        : undefined;

    function extractParts(obj: Record<string, unknown> | undefined) {
        return (obj?.parts as Array<Record<string, string>>) ?? [];
    }

    const parts =
        extractParts(statusMsg).length > 0
            ? extractParts(statusMsg)
            : extractParts(result)?.length > 0
                ? extractParts(result)
                : extractParts(historyLast);

    const text = parts
        .filter((p) => p.kind === "text")
        .map((p) => p.text)
        .join("\n");

    const metaSource = statusMsg ?? historyLast;
    const identity = (
        metaSource?.metadata as Record<string, Record<string, unknown>>
    )?.[IDENTITY_EXT_URI]?.agentIdentity as Record<string, unknown> | undefined;

    return NextResponse.json({
        isError: false,
        text: text || "(no response text — see raw)",
        fromPeer: identity?.fromPeer === true,
        agentName: identity?.name as string | undefined,
        peerName: identity?.peerName as string | undefined,
        raw: data,  // always included so UI can show it
    });
}
