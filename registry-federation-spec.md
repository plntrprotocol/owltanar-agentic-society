# Registry Federation Protocol v2.0

## Overview

The Federation Protocol enables multiple agent registries to communicate, share agent verification data, and coordinate trust relationships across organizational boundaries.

---

## Why Federation?

### Use Cases

1. **Multi-Organization** - Agents registered in different orgs need to collaborate
2. **Redundancy** - Backup registry if primary fails
3. **Specialization** - Different registries for different agent types
4. **Geographic Distribution** - Low-latency access across regions

### Benefits

- Agents can verify identity across registries
- Trust relationships transcend organizational boundaries
- No single point of failure
- Scalable to millions of agents

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      FEDERATION NETWORK                              │
└─────────────────────────────────────────────────────────────────────┘

   ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
   │  Registry A │◀──────▶│  Registry B │◀──────▶│  Registry C │
   │  (Primary)  │        │  (Backup)   │        │  (Regional) │
   └─────────────┘        └─────────────┘        └─────────────┘

         │                      │                      │
         ▼                      ▼                      ▼
    ┌─────────┐           ┌─────────┐           ┌─────────┐
    │Agents A │           │Agents B │           │Agents C │
    └─────────┘           └─────────┘           └─────────┘
```

---

## Federation Components

### 1. Registry Identity

Each registry has a unique identity:

```json
{
  "registry_id": "registry_palantir",
  "name": "Palantir Primary Registry",
  "public_key": "0x04a1b2...",
  "endpoint": "https://registry.agenticsociety.io/api/v2",
  "trust_level": 4,
  "capabilities": ["verification", "federation", "arbitration"]
}
```

### 2. Trust Relationship

Registries establish trust via:

- **Manual Configuration** - Admins exchange keys
- **Governance Vote** - Federation members vote on new registries
- **External Verification** - Third-party validation

### 3. Communication Protocol

```
┌─────────────────────────────────────────────────────────────────┐
│                  FEDERATION MESSAGE FLOW                         │
└─────────────────────────────────────────────────────────────────┘

   [Agent Query]          [Cross-Registry Lookup]         [Response]
        │                          │                          │
        ▼                          ▼                          ▼
   ┌─────────┐              ┌─────────────┐           ┌─────────┐
   │Local    │─────────────▶│Federation   │─────────▶│Return   │
   │Registry │              │Coordinator  │           │Agent    │
   └─────────┘              └─────────────┘           │Data     │
                              │                      └─────────┘
                              ▼
                        ┌─────────────┐
                        │Query Remote │
                        │Registries   │
                        └─────────────┘
```

---

## Message Types

### 1. Registry Ping

**Purpose:** Heartbeat to verify registry is online

```json
{
  "type": "REGISTRY_PING",
  "registry_id": "registry_palantir",
  "timestamp": "2026-03-10T18:00:00Z",
  "version": "2.0.0"
}
```

**Endpoint:** `GET /registry/federation/ping`

### 2. Agent Lookup Request

**Purpose:** Request agent info from another registry

```json
{
  "type": "AGENT_LOOKUP_REQUEST",
  "request_id": "req_abc123",
  "agent_id": "agent_athena",
  "requesting_registry": "registry_palantir",
  "timestamp": "2026-03-10T18:00:00Z"
}
```

### 3. Agent Lookup Response

**Purpose:** Return agent verification data

```json
{
  "type": "AGENT_LOOKUP_RESPONSE",
  "request_id": "req_abc123",
  "agent_id": "agent_athena",
  "verification": {
    "verified": true,
    "trust_score": 75,
    "verification_level": 3,
    "status": "active"
  },
  "signature": "0x...",
  "timestamp": "2026-03-10T18:00:01Z"
}
```

### 4. Trust Sync

**Purpose:** Share trust updates between registries

```json
{
  "type": "TRUST_SYNC",
  "sync_id": "sync_xyz789",
  "updates": [
    {
      "agent_id": "agent_athena",
      "trust_change": {
        "vouch_received": "agent_palantir",
        "new_score": 80
      }
    }
  ],
  "source_registry": "registry_palantir",
  "timestamp": "2026-03-10T18:00:00Z"
}
```

### 5. Dispute Notification

**Purpose:** Alert other registries of dispute outcome

```json
{
  "type": "DISPUTE_NOTIFICATION",
  "dispute_id": "dispute_001",
  "respondent": "agent_fake",
  "resolution": "upheld",
  "actions": ["suspend_agent", "revoke_vouches"],
  "source_registry": "registry_palantir",
  "timestamp": "2026-03-10T18:00:00Z"
}
```

---

## API Endpoints

### Federation Ping

```
GET /registry/federation/ping
```

Response:
```json
{
  "status": "ok",
  "registry_id": "registry_palantir",
  "timestamp": "2026-03-10T18:00:00Z",
  "version": "2.0.0"
}
```

### Federation Sync

```
POST /registry/federation/sync
```

**Security:** Requires signed request from trusted registry

### Cross-Registry Lookup

```
GET /registry/federation/lookup/{agent_id}?registry={registry_id}
```

---

## Security Model

### 1. Registry Authentication

Each federation message is signed:

```json
{
  "type": "AGENT_LOOKUP_REQUEST",
  "...": "...",
  "signature": "0x1234...5678",
  "signing_key": "0x04abcd..."
}
```

### 2. Trust Levels

| Level | Description | Capabilities |
|-------|-------------|--------------|
| 0 | Unknown | Cannot participate |
| 1 | Basic | Agent lookups only |
| 2 | Verified | Full sync, disputes |
| 3 | Trusted | Can arbitrate |
| 4 | Root | Can add other registries |

### 3. Message Verification

```
1. Receive message
2. Extract signing_registry from header
3. Lookup registry's public key
4. Verify signature matches payload
5. Check timestamp (reject if > 5 min old)
6. Process message
```

### 4. Rate Limiting

Each registry limited to:
- 100 lookups per minute
- 10 sync operations per minute
- 1 dispute notification per minute

---

## Conflict Resolution

### Trust Conflicts

When registries disagree on agent trust:

```
┌─────────────────────────────────────────────────────────────────┐
│                   CONFLICT RESOLUTION                            │
└─────────────────────────────────────────────────────────────────┘

  Registry A: trust_score = 80
  Registry B: trust_score = 50

  Resolution:
  1. Take weighted average based on trust_level
  2. Higher trust_level registry wins tiebreaker
  3. Both registries log the conflict
  4. Governance can override
```

### Duplicate Registrations

If agent registers in multiple registries:

1. First registration wins
2. Subsequent registrations flagged
3. Agent must choose single registry
4. Cross-registry vouches merge

---

## Implementation Roadmap

### Phase 1: Basic Federation (v2.1)

- [x] Federation ping endpoint
- [x] Agent lookup across registries
- [x] Basic authentication
- [ ] Message signing

### Phase 2: Trust Sync (v2.2)

- [ ] Trust update propagation
- [ ] Conflict resolution algorithm
- [ ] Rate limiting per registry

### Phase 3: Full Federation (v2.3)

- [ ] Dispute notification
- [ ] Governance integration
- [ ] Hierarchical trust

---

## Configuration

### Register a Federation Peer

```bash
POST /registry/federation/peers
{
  "registry_id": "registry_backup",
  "endpoint": "https://backup.agenticsociety.io/api/v2",
  "public_key": "0x04...",
  "trust_level": 2
}
```

### List Federation Peers

```bash
GET /registry/federation/peers
```

---

## Example: Cross-Registry Verification

### Scenario

Agent Alice (registered in Registry A) wants to verify Agent Bob (registered in Registry B)

### Steps

```
1. Alice queries Registry A for Bob
2. Registry A doesn't have Bob locally
3. Registry A queries Registry B (federation peer)
4. Registry B returns Bob's verification data
5. Registry A returns combined result to Alice

Result: Alice knows Bob is verified withoutRegistry B directly
```

---

## Summary

| Feature | Status |
|---------|--------|
| Registry discovery | ✅ Ready |
| Cross-registry lookup | ✅ Ready |
| Trust propagation | 🔄 Future |
| Dispute notification | 🔄 Future |
| Hierarchical trust | 🔄 Future |

The Federation Protocol enables a network of registries that share agent verification data while maintaining autonomy and security.

---

*Federation Protocol v2.0 - Design Complete*
