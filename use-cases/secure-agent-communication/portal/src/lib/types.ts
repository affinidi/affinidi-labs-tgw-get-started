export interface User {
    email: string;
    name: string;
    org: string;
}

export interface ChatMessage {
    id: string;
    role: "user" | "agent";
    text: string;
    fromPeer: boolean;
    agentName?: string;
    peerName?: string;
    isError: boolean;
    raw?: unknown;
    timestamp: number;
}
