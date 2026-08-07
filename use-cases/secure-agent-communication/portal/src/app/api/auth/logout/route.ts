import { NextResponse } from "next/server";
import { AUTH_COOKIE, ACCESS_COOKIE, IDENTITY_COOKIE } from "@/lib/auth";

export async function POST() {
    const response = NextResponse.json({ ok: true });
    response.cookies.delete(AUTH_COOKIE);
    response.cookies.delete(ACCESS_COOKIE);
    response.cookies.delete(IDENTITY_COOKIE);
    return response;
}
