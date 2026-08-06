import { NextResponse } from "next/server";
import { getMicrosoftScopes } from "@/lib/entra";

export async function GET() {
    const clientId = process.env.MICROSOFT_CLIENT_ID;
    const appUrl = (process.env.NEXT_PUBLIC_URL || "").replace(/\/$/, "");
    const redirectUri = `${appUrl}/api/auth/callback/microsoft`;
    const tenantId = process.env.MICROSOFT_TENANT_ID || "common";
    const scopes = getMicrosoftScopes();

    if (!clientId || !appUrl) {
        return NextResponse.json(
            { error: "Microsoft Entra ID is not configured" },
            { status: 500 },
        );
    }

    const params = new URLSearchParams({
        client_id: clientId,
        redirect_uri: redirectUri,
        response_type: "code",
        response_mode: "query",
        scope: scopes,
        prompt: "select_account",
    });

    return NextResponse.redirect(
        `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/authorize?${params}`,
    );
}
