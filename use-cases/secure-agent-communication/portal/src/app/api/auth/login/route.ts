import { NextRequest, NextResponse } from "next/server";
import { signInMock, AUTH_COOKIE, ACCESS_COOKIE, IDENTITY_COOKIE } from "@/lib/auth";

export async function POST(req: NextRequest) {
    const body = await req.json();

    if (!body.guest) {
        return NextResponse.json({ error: "Invalid request" }, { status: 400 });
    }

    const orgSlug = (process.env.NEXT_PUBLIC_ORG_NAME || "org")
        .toLowerCase()
        .replace(/\s+/g, "-");
    const token = await signInMock(`guest@${orgSlug}.local`);

    const response = NextResponse.json({ ok: true });
    response.cookies.set(AUTH_COOKIE, token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 60 * 8,
        path: "/",
    });
    response.cookies.delete(ACCESS_COOKIE);
    response.cookies.delete(IDENTITY_COOKIE);
    return response;
}
