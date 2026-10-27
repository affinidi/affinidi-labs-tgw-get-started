import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { randomUUID } from "crypto";
import { getUser, ACCESS_COOKIE } from "@/lib/auth";

const IDENTITY_EXT_URI =
    "https://fabric.affinidi.io/extensions/agent-identity/v1";
const A2A_LEGACY_MODE = !["false", "0", "no", "off"].includes(
    (process.env.A2A_LEGACY_MODE ?? "true").trim().toLowerCase(),
);

export async function POST(req: NextRequest) {
    const user = await getUser();
    if (!user) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { message } = await req.json();
    if (!message?.trim()) {
        return NextResponse.json({ error: "Message is required" }, { status: 400 });
    }

    const agentBaseUrl = (process.env.NEXT_PUBLIC_AGENT_URL || "").replace(/\/$/, "");
    const agentUrl = A2A_LEGACY_MODE
        ? `${agentBaseUrl}/a2a/tasks/send`
        : `${agentBaseUrl}/`;
    if (!process.env.NEXT_PUBLIC_AGENT_URL) {
        return NextResponse.json(
            { error: "NEXT_PUBLIC_AGENT_URL is not configured" },
            { status: 500 },
        );
    }

    const cookieStore = await cookies();
    const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
    };
    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }

    const requestId = randomUUID();
    const messageId = randomUUID().replace(/-/g, "");
    const sessionId = randomUUID().replace(/-/g, "");

    const identityMetadata = {
        [IDENTITY_EXT_URI]: {
            agentIdentity: {
                name: `${user.org} Portal`,
                model: "None",
                role: "Portal Client App",
                version: "1.0.0",
            },
        },
    };

    // Legacy: A2A v0.3 (`message/send`, lowercase role, `kind`-tagged parts).
    // Native: A2A 1.0 (`SendMessage`, ROLE_* enum, kind-less protobuf JSON parts).
    let a2aPayload: Record<string, unknown>;
    if (A2A_LEGACY_MODE) {
        a2aPayload = {
            jsonrpc: "2.0",
            id: requestId,
            method: "message/send",
            params: {
                message: {
                    role: "user",
                    kind: "message",
                    messageId,
                    contextId: sessionId,
                    parts: [{
                        kind: "data",
                        data: { action: "send:message", text: message },
                    }],
                    extensions: [IDENTITY_EXT_URI],
                    metadata: identityMetadata,
                },
            },
        };
    } else {
        headers["A2A-Version"] = "1.0";
        headers["A2A-Extensions"] = IDENTITY_EXT_URI;
        a2aPayload = {
            jsonrpc: "2.0",
            id: requestId,
            method: "SendMessage",
            params: {
                message: {
                    messageId,
                    role: "ROLE_USER",
                    parts: [{ text: message }],
                    extensions: [IDENTITY_EXT_URI],
                    metadata: identityMetadata,
                },
            },
        };
    }

    let data: unknown;
    // Authorization is redacted so the token never reaches the browser
    const sentRequest = {
        method: "POST",
        url: agentUrl,
        headers: { ...headers, ...(headers["Authorization"] ? { Authorization: "Bearer ***" } : {}) },
        body: a2aPayload,
    };
    try {
        const agentRes = await fetch(agentUrl, {
            method: "POST",
            headers,
            body: JSON.stringify(a2aPayload),
        });
        const rawBody = await agentRes.text();
        try {
            data = JSON.parse(rawBody);
        } catch {
            return NextResponse.json({
                isError: true,
                errorMessage: `Agent at ${agentUrl} returned HTTP ${agentRes.status} with a non-JSON response.`,
                raw: rawBody,
                request: sentRequest,
            });
        }

        if (!agentRes.ok) {
            return NextResponse.json({
                isError: true,
                errorMessage: `Agent returned HTTP ${agentRes.status}`,
                raw: data,
                request: sentRequest,
            });
        }
    } catch (err) {
        return NextResponse.json({
            isError: true,
            errorMessage: `Could not reach agent at ${agentUrl}: ${String(err)}`,
            raw: null,
            request: sentRequest,
        });
    }

    const rpcError = (data as Record<string, unknown>)?.error as Record<string, unknown> | undefined;
    if (rpcError) {
        return NextResponse.json({
            isError: true,
            errorMessage: String(rpcError.message || rpcError),
            raw: data,
            request: sentRequest,
        });
    }

    const rawResult = (data as Record<string, unknown>)?.result as Record<string, unknown> | undefined;
    // A2A 1.0 wraps the payload as result.task or result.message; v0.3 returns it directly
    const result = ((rawResult?.task ?? rawResult) as Record<string, unknown>) ?? {};
    const directMsg = rawResult?.message as Record<string, unknown> | undefined;
    const statusMsg =
        directMsg ??
        ((result?.status as Record<string, unknown>)?.message as Record<string, unknown> | undefined);
    const historyLast = Array.isArray(result?.history)
        ? (result.history as Record<string, unknown>[])[result.history.length - 1]
        : undefined;

    function extractParts(obj: Record<string, unknown> | undefined) {
        return (obj?.parts as Array<Record<string, unknown>>) ?? [];
    }

    const parts =
        extractParts(statusMsg).length > 0
            ? extractParts(statusMsg)
            : extractParts(result).length > 0
                ? extractParts(result)
                : extractParts(historyLast);

    // v0.3 text parts carry kind:"text"; v1.0 parts are kind-less with a `text` field
    const text = parts
        .filter((p) => typeof p.text === "string" && (p.kind ?? "text") === "text")
        .map((p) => p.text as string)
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
        raw: data,
        request: sentRequest,
    });
}
