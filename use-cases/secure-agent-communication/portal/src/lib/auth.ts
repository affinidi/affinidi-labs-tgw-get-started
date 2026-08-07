import { SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";
import type { User } from "./types";

const JWT_SECRET = new TextEncoder().encode(
    process.env.JWT_SECRET || "fallback-secret-replace-in-production",
);
const ORG_NAME = process.env.NEXT_PUBLIC_ORG_NAME || "Org";

// Unique per org so cookies from different portals on the same localhost don't collide
export const AUTH_COOKIE = `portal_auth_${process.env.NEXT_PUBLIC_ORG_ID || "default"}`;
export const ACCESS_COOKIE = `portal_access_${process.env.NEXT_PUBLIC_ORG_ID || "default"}`;
export const IDENTITY_COOKIE = `portal_identity_${process.env.NEXT_PUBLIC_ORG_ID || "default"}`;

export type { User };

export async function signInMock(email: string): Promise<string> {
    // Derive a display name from the email prefix
    const name = email
        .split("@")[0]
        .replace(/[._-]/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());

    return new SignJWT({ email, name, org: ORG_NAME })
        .setProtectedHeader({ alg: "HS256" })
        .setIssuedAt()
        .setExpirationTime("8h")
        .sign(JWT_SECRET);
}

export async function signInWithMicrosoft(
    email: string,
    displayName: string,
): Promise<string> {
    return new SignJWT({ email, name: displayName || email, org: ORG_NAME })
        .setProtectedHeader({ alg: "HS256" })
        .setIssuedAt()
        .setExpirationTime("8h")
        .sign(JWT_SECRET);
}

export async function getUser(): Promise<User | null> {
    const cookieStore = await cookies();
    const token = cookieStore.get(AUTH_COOKIE)?.value;
    if (!token) return null;
    try {
        const { payload } = await jwtVerify(token, JWT_SECRET);
        return payload as unknown as User;
    } catch {
        return null;
    }
}
