import { NextRequest, NextResponse } from "next/server";
import { signInWithMicrosoft, AUTH_COOKIE, ACCESS_COOKIE, IDENTITY_COOKIE } from "@/lib/auth";
import { decodeMicrosoftIdentityToken, getMicrosoftScopes } from "@/lib/entra";

export async function GET(req: NextRequest) {
    const { searchParams } = req.nextUrl;
    const code = searchParams.get("code");
    const error = searchParams.get("error");

    const clientId = process.env.MICROSOFT_CLIENT_ID;
    const clientSecret = process.env.MICROSOFT_CLIENT_SECRET;
    const appUrl = (process.env.NEXT_PUBLIC_URL || "").replace(/\/$/, "");
    const redirectUri = `${appUrl}/api/auth/callback/microsoft`;
    const tenantId = process.env.MICROSOFT_TENANT_ID || "common";
    const scopes = getMicrosoftScopes();

    const appOrigin = appUrl || "http://localhost:3001";

    if (error || !code) {
        return NextResponse.redirect(
            `${appOrigin}/?error=${error || "auth_cancelled"}`,
        );
    }

    if (!clientId || !clientSecret || !appUrl) {
        return NextResponse.redirect(`${appOrigin}/?error=oauth_not_configured`);
    }

    try {
        const tokenRes = await fetch(
            `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`,
            {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: new URLSearchParams({
                    code,
                    client_id: clientId,
                    client_secret: clientSecret,
                    redirect_uri: redirectUri,
                    grant_type: "authorization_code",
                    scope: scopes,
                }),
            },
        );

        if (!tokenRes.ok) {
            return NextResponse.redirect(
                `${appOrigin}/?error=token_exchange_failed`,
            );
        }

        const tokens = await tokenRes.json();

        if (!tokens.id_token || !tokens.access_token) {
            return NextResponse.redirect(
                `${appOrigin}/?error=token_exchange_failed`,
            );
        }

        const { email, name } = decodeMicrosoftIdentityToken(tokens.id_token);
        if (!email) {
            return NextResponse.redirect(`${appOrigin}/?error=no_email`);
        }

        const jwt = await signInWithMicrosoft(email, name);

        const response = NextResponse.redirect(`${appOrigin}/dashboard`);
        response.cookies.set(AUTH_COOKIE, jwt, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            sameSite: "lax",
            maxAge: 60 * 60 * 8,
            path: "/",
        });
        response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            sameSite: "lax",
            maxAge: tokens.expires_in || 3600,
            path: "/",
        });
        response.cookies.set(IDENTITY_COOKIE, tokens.id_token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            sameSite: "lax",
            maxAge: tokens.expires_in || 3600,
            path: "/",
        });
        return response;
    } catch {
        return NextResponse.redirect(`${appOrigin}/?error=token_exchange_failed`);
    }
}
