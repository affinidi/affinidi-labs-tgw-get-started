#!/usr/bin/env python3
"""Quick functional test of both agents."""
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE = os.environ.get("BASE_URL", "http://localhost:10000")


async def main():
    async with httpx.AsyncClient(timeout=10) as c:

        # ── Health check ───────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/health")
        print("\n=== Health ===")
        print(json.dumps(r.json(), indent=2))

        # ── Agent cards ────────────────────────────────────────────────────────
        for path, label in [
            ("/a2a/personal-agent/.well-known/agent.json", "Personal Agent Card"),
            ("/a2a/finance-agent/.well-known/agent.json",  "Finance Agent Card"),
        ]:
            r = await c.get(f"{BASE}{path}")
            card = r.json()
            print(f"\n=== {label} ===")
            print(f"  name      : {card.get('name')}")
            print(f"  version   : {card.get('version')}")
            ifaces = card.get("supportedInterfaces") or card.get(
                "supported_interfaces") or []
            for iface in ifaces:
                url = iface.get("url") or iface
                print(f"  endpoint  : {url}")
            caps = card.get("capabilities") or {}
            for ext in caps.get("extensions") or []:
                print(f"  ext uri   : {ext.get('uri')}")

        # ── Message tests ──────────────────────────────────────────────────────
        IDENTITY_EXT = "https://fabric.affinidi.io/extensions/agent-identity/v1"
        ROUTING_PREFIX = "🔀 *Routed to Finance Agent*"

        tests = [
            ("/a2a/personal-agent/", "Hello! What can you do?"),
            ("/a2a/personal-agent/", "What's on my schedule today?"),
            ("/a2a/finance-agent/",  "What is my account balance?"),
            ("/a2a/finance-agent/",  "Show my recent transactions"),
            # Finance query sent to Personal Agent → should auto-route to Finance Agent
            ("/a2a/personal-agent/", "What is my account balance?"),
        ]

        for target, text in tests:
            body = {
                "jsonrpc": "2.0",
                "id": uuid4().hex,
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": text}],
                        "messageId": uuid4().hex,
                    }
                },
            }
            r = await c.post(f"{BASE}{target}", json=body)
            data = r.json()
            agent_label = "personal-agent" if "personal" in target else "finance-agent"
            print(f"\n>>> [{agent_label}] {text}")

            if "error" in data:
                print(f"  ERROR: {data['error']}")
                continue

            result = data.get("result") or {}
            status = result.get("status") or {}
            msg = status.get("message") or {}
            parts = msg.get("parts") or []
            metadata = msg.get("metadata") or {}
            identity = metadata.get(IDENTITY_EXT) or {}

            reply = "\n  ".join(p.get("text", "")
                                for p in parts if p.get("text"))

            # Detect routing from the actual reply content
            was_routed = reply.startswith(ROUTING_PREFIX)

            print(f"  Responder : {identity.get('name', 'unknown')} "
                  f"(role: {identity.get('role', '?')}, "
                  f"model: {identity.get('model', '?')})")
            if was_routed:
                print(f"  Routing   : ✅ Personal Agent called Finance Agent via A2A")
                # Strip the prefix so the finance content is shown cleanly
                reply = reply[len(ROUTING_PREFIX):].lstrip()
            else:
                print(f"  Routing   : — answered directly")
            print(f"  Reply     : {reply[:300]}")

if __name__ == "__main__":
    asyncio.run(main())
