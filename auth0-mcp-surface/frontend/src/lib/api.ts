// Small typed client for the FastAPI backend.
// The base URL is injected at build time from PUBLIC_API_BASE:
//   - unset            → dev default (two-server mode, backend on :8642)
//   - "" (empty)       → same origin / relative (single-origin: backend serves us)
//   - "https://host"   → explicit absolute base
const _rawBase = import.meta.env.PUBLIC_API_BASE as string | undefined;
export const API_BASE: string =
  _rawBase === undefined ? 'http://localhost:8642' : _rawBase;

export interface UserInfo {
  name: string | null;
  email: string | null;
  picture: string | null;
}

export interface MeResponse {
  authenticated: boolean;
  guest: boolean;
  user: UserInfo | null;
  gateway_url: string;
}

export interface GatewayResponse {
  status?: number;
  body?: any;
  error?: string;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...init,
  });
  return res.json() as Promise<T>;
}

export const api = {
  me: () => json<MeResponse>('/api/auth/me'),
  loginUrl: () => json<{ auth_url: string }>('/api/auth/login'),
  guest: () => json<{ ok: boolean }>('/api/auth/guest'),
  logout: () => json<{ ok: boolean }>('/api/auth/logout'),

  chat: (message: string) =>
    json<GatewayResponse>('/api/gateway/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    }),

  gateway: (body: unknown) =>
    json<GatewayResponse>('/api/gateway', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
};

// Build the outgoing MCP request shape purely for display (the backend builds
// the real one). Kept in sync with backend `_chat_tool_request_body`.
export function buildChatToolCall(message: string, id: number) {
  return {
    jsonrpc: '2.0',
    id,
    method: 'tools/call',
    params: {
      _meta: { agentIdentity: { name: 'chat-client', version: '1.0.0' } },
      name: 'chat',
      arguments: { message },
    },
  };
}
