import { decodeJwt } from "jose";

const ENTRA_APP_ID_URI = process.env.ENTRA_APP_ID_URI || "";

export function getMicrosoftScopes(): string {
    const scopes = ["openid", "profile", "email"];
    if (ENTRA_APP_ID_URI) {
        // Use specific scope, not /.default — mixing /.default with openid/profile causes invalid_request
        const scopeName = process.env.ENTRA_SCOPE_NAME || "agent.access";
        scopes.push(`${ENTRA_APP_ID_URI}/${scopeName}`);
    }
    return scopes.join(" ");
}

export function decodeMicrosoftIdentityToken(token: string): {
    email: string;
    name: string;
} {
    const payload = decodeJwt(token);
    const email = (
        payload.email ||
        payload.preferred_username ||
        payload.upn ||
        ""
    ) as string;
    const name = (payload.name || payload.given_name || email || "") as string;
    return { email, name };
}
