# Affinidi Trust Fabric - Getting Started

## Welcome to Affinidi Trust Fabric

Affinidi Trust Fabric enables secure, privacy-preserving communication between organizations through a decentralized network of Affinidi Gateways. Using the DIDComm protocol, gateways can establish trusted connections and exchange data securely without exposing direct network access.

---

## Core Concepts

### What is a Gateway?
An **Affinidi Gateway** is a controlled entry point that manages communications on behalf of your organization. It implements security policies, handles routing, and ensures all communications comply with your governance rules.

### What is a Mediator?
A **DIDComm Mediator** is an intermediary service that facilitates asynchronous message routing between gateways. It enables secure communication without requiring gateways to expose direct network endpoints, making it ideal for distributed architectures.

### What is a Fabric Connection?
A **Fabric Connection** (Gateway-to-Gateway Connection) is a secure, encrypted tunnel between two Affinidi Gateways established through a DIDComm Mediator. This enables organizations to trust each other and exchange information through a standardized protocol.

---

## Getting Started Guides

### 1. [Mediator Setup Guide](./mediator-guide.md)

Start here if you need to create a DIDComm Mediator or add an existing one to your gateways.

**Covers:**
- Creating a new DIDComm Mediator in the Affinidi Developer Portal
- Adding a mediator to an Affinidi Gateway
- Configuring multiple gateways with the same mediator
- Monitoring mediator health and troubleshooting

**Time to complete:** ~10-15 minutes

**Prerequisites:**
- Access to Affinidi Developer Portal (portal.affinidi.com)
- At least one Affinidi Gateway with admin access

---

### 2. [Gateway-to-Gateway Connection Guide](./fabric-connection-guide.md)

Follow this guide to establish a secure connection between two Affinidi Gateways.

**Covers:**
- Creating connection endpoints on the initiating gateway
- Connecting from the receiving gateway using invitation links
- Approving gateway connections
- Verifying end-to-end connectivity
- Using gateway connections with Surfaces

**Time to complete:** ~20-30 minutes

**Prerequisites:**
- A DIDComm Mediator (create one using the [Mediator Setup Guide](./mediator-guide.md))
- Two Affinidi Gateways with admin access
- Mediator added to both gateways

---

## Quick Start Checklist

### Phase 1: Prepare Infrastructure
- [ ] Create a DIDComm Mediator in Affinidi Developer Portal
- [ ] Have access to two Affinidi Gateways
- [ ] Ensure you have admin privileges on both gateways

### Phase 2: Configure Mediator
- [ ] Add mediator to Gateway 1 (AG1)
- [ ] Add mediator to Gateway 2 (AG2)
- [ ] Test mediator heartbeat on both gateways
- [ ] Verify mediator is showing as Active/Healthy

### Phase 3: Establish Gateway Connection
- [ ] Create connection endpoint on Gateway 1 (AG1)
- [ ] Copy gateway invitation link and secret
- [ ] Connect to Gateway 1 from Gateway 2 (AG2)
- [ ] Approve connection from Gateway 1 (AG1)
- [ ] Verify connection status is Active on both gateways

### Phase 4: Test and Deploy
- [ ] Test heartbeat/ping between gateways
- [ ] Create a test Surface on each gateway
- [ ] Configure Surface to use gateway connection
- [ ] Verify data can flow through the connection

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Affinidi Trust Fabric                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐                   ┌──────────────────┐    │
│  │  Organization A  │                   │  Organization B  │    │
│  │  (Gateway AG1)   │                   │  (Gateway AG2)   │    │
│  │                  │                   │                  │    │
│  │  ┌────────────┐  │    DIDComm        │  ┌────────────┐  │    │
│  │  │ Surfaces   │  │ ┌──────────────┐  │  │ Surfaces   │  │    │
│  │  │ (A2A, MCP) │  │ │              │  │  │ (A2A, MCP) │  │    │
│  │  └────────────┘  │ │   Mediator   │  │  └────────────┘  │    │
│  │                  │ │              │  │                  │    │
│  └──────────────────┘ └──────────────┘  └──────────────────┘    │
│          │                   ▲                       │            │
│          └───────────────────┼───────────────────────┘            │
│                     Encrypted via DIDComm                        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Features

✅ **End-to-End Encryption** - All communications are encrypted using cryptographic keys  
✅ **Decentralized Trust** - No central authority; trust is established through DIDs  
✅ **Asynchronous Messaging** - Communicate without requiring synchronous connections  
✅ **Protocol Standard** - Built on the industry-standard DIDComm protocol  
✅ **Multi-Gateway Mesh** - Connect many gateways in a mesh topology  
✅ **Surface Diversity** - Support multiple surface types (A2A, MCP, etc.) over the same connection  

---

## Common Workflows

### Scenario 1: Two Organizations Sharing Data
1. Both organizations create Affinidi Gateways
2. Both add the same DIDComm Mediator
3. Establish gateway-to-gateway connection
4. Configure A2A Surfaces to communicate securely

### Scenario 2: Multi-Party Collaboration Network
1. Create a DIDComm Mediator for the network
2. Add multiple gateways (one per organization)
3. Each gateway connects to 1-2 hub gateways
4. Gateways share MCP Surfaces for distributed processing

### Scenario 3: Agent-Mediated Communication
1. Set up a central gateway as an agent hub
2. Connecting gateways host individual agents
3. Agents interact through gateway-to-gateway connections
4. Mediator ensures reliable message delivery

---

## Troubleshooting Quick Reference

| Issue | Guide Section |
|-------|---------------|
| Cannot create mediator | [Mediator Setup - Create Mediator](./mediator-guide.md#part-1-create-a-mediator) |
| Cannot add mediator to gateway | [Mediator Setup - Add Mediator](./mediator-guide.md#part-2-add-mediator-to-your-gateway) |
| Heartbeat fails | [Mediator - Troubleshooting](./mediator-guide.md#troubleshooting-mediator-issues) |
| Connection endpoint fails | [Gateway Connection - Troubleshooting](./fabric-connection-guide.md#troubleshooting) |
| Cannot see remote gateway surfaces | [Gateway Connection - Usage](./fabric-connection-guide.md#step-6-using-gateway-connections-with-surfaces) |

---

## Additional Resources

- **Affinidi Trust Fabric Docs**: [https://docs.affinidi.com/products/affinidi-trust-fabric/](https://docs.affinidi.com/products/affinidi-trust-fabric/)
- **DIDComm Specification**: [https://didcomm.org/](https://didcomm.org/)
- **Affinidi Developer Portal**: [https://portal.affinidi.com/](https://portal.affinidi.com/)
- **W3C DIDs**: [https://www.w3.org/TR/did-core/](https://www.w3.org/TR/did-core/)

---

## Support

For additional assistance:
1. Check the [Troubleshooting](./fabric-connection-guide.md#troubleshooting) sections in the guides
2. Review the [FAQ](./mediator-guide.md#faq) in the Mediator Guide
3. Consult the [Affinidi Documentation](https://docs.affinidi.com/)
4. Contact Affinidi Support through the Developer Portal

---

## Document Version

- **Created**: 2026-07-29
- **Last Updated**: 2026-07-29
- **Version**: 1.0

For the latest version of these guides, visit the Affinidi documentation portal.

