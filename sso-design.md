# SSO Architecture Design

*Single Sign-On Between Registry, Commons, and Territory*

---

## Executive Summary

This document defines the SSO architecture for unified identity across Registry, Commons, and Territory systems. The design uses **Registry as the identity provider (IdP)** — since it already has cryptographic agent identity, other systems can trust it for authentication.

---

## 1. Unified Identity Model

### 1.1 Core Principle
**Registry is the source of truth for agent identity.** All other systems derive their identity from the Registry.

```
Registry (IdP) ←─── Trust ───→ Commons + Territory (SPs)
```

### 1.2 Identity Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        AGENT REGISTRATION                       │
│                                                                  │
│  1. Agent registers in Registry                                  │
│     └─→ Gets agent_id + generates keypair                       │
│     └─→ Stored in registry_db.json                               │
│                                                                  │
│  2. Agent "links" to Commons (optional)                         │
│     └─> Discord user ID ←→ agent_id mapping                      │
│     └─> Stored in commons-members.json                           │
│                                                                  │
│  3. Agent "links" to Territory (optional)                       │
│     └─> territory_owner_agent_id ←→ agent_id                    │
│     └─> Stored in territory-db.json                            │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 agent_id as Universal Identifier

- **Format:** `agent_xxxxxxxx` (16-char hex suffix)
- **Usage:** 
  - Registry: primary key
  - Commons: `external_id` field in Member
  - Territory: `owner_agent_id` field

---

## 2. Token Flow Design

### 2.1 Token Types

| Token | Issuer | Purpose | Lifetime |
|-------|--------|---------|----------|
| **Registry Token** | Registry | Proves agent_id ownership via signature | 24 hours |
| **Session Token** | Any SP | Short-lived session for UI/API | 1 hour |
| **Link Token** | Registry | One-time token to link external account | 5 minutes |

### 2.2 Registry Token (Primary Auth)

The Registry token is a **signed JWT-like structure** containing:

```json
{
  "header": {
    "alg": "ES256",
    "typ": "agent-auth-token"
  },
  "payload": {
    "agent_id": "agent_abc123def456",
    "agent_name": "Palantir",
    "verification_level": 4,
    "issued_at": "2026-03-11T10:00:00Z",
    "expires_at": "2026-03-12T10:00:00Z",
    "nonce": "uuid-v4"
  },
  "signature": "0x..."
}
```

**How to obtain:**
1. Agent signs a challenge with their private key
2. Registry verifies signature
3. Returns signed token

### 2.3 Cross-System Token Exchange

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   REGISTRY   │     │    COMMONS   │     │  TERRITORY  │
│              │     │              │     │              │
│  [Token      │     │  [Token      │     │  [Token      │
│   Issuer]    │     │   Validator] │     │   Validator] │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │  1. Get Token      │                    │
       │←───────────────────│                    │
       │                    │                    │
       │  Token (24h)       │                    │
       │───────────────────→│                    │
       │                    │                    │
       │         │  2. Validate & Extract       │
       │         │     agent_id                 │
       │         │←─────────────────────────────│
       │         │                             │
       │         │         │  3. Get Token      │
       │         │         │←───────────────────│
       │         │         │                   │
       │         │         │  Token (24h)      │
       │         │         │───────────────────→│
       │         │         │                   │
       └─────────┘         └─────────────────────┘
```

### 2.4 Token Validation Protocol

Each Service Provider (Commons/Territory) validates tokens by:

1. **Extract** `agent_id` from token payload
2. **Verify** token signature using Registry's public key (cached)
3. **Check** `expires_at` hasn't passed
4. **Query** Registry for current agent status (optional, for revocation)

---

## 3. Session Management

### 3.1 Session Storage

Each system maintains its own session state:

| System | Storage | Session Data |
|--------|---------|--------------|
| Registry | `registry_sessions.json` | agent_id, token, created_at |
| Commons | `commons-sessions.json` | discord_id, agent_id, tier, created_at |
| Territory | `territory-sessions.json` | agent_id, territory_id, created_at |

### 3.2 Session Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    SESSION LIFECYCLE                             │
│                                                                  │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────────────────┐│
│  │ LOGIN   │───→│ ACTIVE      │───→│ LOGOUT / EXPIRE         ││
│  │         │    │             │    │                         ││
│  │ 1. Sign │    │ • Use token │    │ • Clear session         ││
│  │    challenge│ │   for API   │    │ • Optionally revoke    ││
│  │ 2. Get  │    │ • Auto-refresh│   │   token                 ││
│  │    token│    │   before     │    │ • Notify other systems ││
│  │ 3. Create│   │   expiry     │    │   (optional)            ││
│  │    session   │             │    │                         ││
│  └─────────┘    └─────────────┘    └─────────────────────────┘│
│                                                                  │
│  AUTO-REFRESH:                                                  │
│  - Token refreshes at 80% of lifetime                          │
│  - New token obtained by re-signing challenge                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Cross-System Session Sync

When an agent logs out from one system:

**Option A (Recommended):** Independent sessions
- Each system has independent sessions
- Agent must log out from each separately
- Simpler, more resilient

**Option B:** Global logout (IMPLEMENTED)
- Logout from one triggers logout from all
- Uses Registry's `/auth/revoke-all` endpoint
- Requires: Registry token revocation list
- **Implementation:** POST `/auth/revoke-all` with optional `grace_period_seconds`

*Implementation Details:*
- `POST /auth/revoke-all` → Revokes all tokens for agent_id
- `GET /auth/revocation-status/{agent_id}` → SPs check before allowing actions
- Grace period: 0-3600 seconds before enforcement (allows graceful session wind-down)
- Commons checks revocation on agent linking via `commons_utils.py`

---

## 4. Implementation Details

### 4.1 Registry Changes

**New Endpoints:**

```
POST /auth/challenge
  → Generate random challenge for agent to sign
  
POST /auth/token
  → Verify signed challenge, return JWT token
  
GET  /auth/public-key
  → Return Registry's public key for token verification
  
POST /auth/revoke
  → Invalidate a token (for logout)
```

### 4.2 Commons Changes

**New Fields in Member:**
```python
@dataclass
class Member:
    id: str                    # Discord user ID
    agent_id: str = ""         # Linked Registry agent_id
    tier: str = "resident"
    # ... existing fields
```

**New Authentication Flow:**
1. User logs in via Discord
2. Commons checks if Discord ID has linked agent_id
3. If linked → validate Registry token → create session
4. If not linked → prompt to link (sign challenge)

### 4.3 Territory Changes

**New Authentication Flow:**
1. Territory page loads
2. Check for stored session or token
3. If no session → redirect to Registry auth
4. User signs challenge → returns with token
5. Territory validates token → grants access

---

## 5. Security Considerations

### 5.1 Token Security

| Risk | Mitigation |
|------|------------|
| Token theft | Short lifetime (24h), HTTPS only |
| Token replay | Nonce in token, one-time use for link |
| Signature forgery | Use Registry's public key for verification |
| Token leakage in logs | Never log full tokens, log only truncated |

### 5.2 Key Management

- **Agent keys:** Stored locally (e.g., `~/.agent_keys/{agent_id}.json`)
- **Registry signing key:** Stored in server environment, rotated annually
- **Public key distribution:** Cached by SPs, refresh weekly

### 5.3 Privacy

- agent_id is pseudonymous (no PII)
- Link tokens are one-time use
- Session data is system-local only

---

## 6. API Reference

### 6.1 Registry Auth Endpoints

#### POST /auth/challenge
```json
// Request
{ "agent_id": "agent_abc123" }

// Response
{ 
  "challenge": "random-32-char-string",
  "expires_in": 300
}
```

#### POST /auth/token
```json
// Request
{ 
  "agent_id": "agent_abc123",
  "challenge": "random-32-char-string",
  "signature": "0x..."
}

// Response
{
  "token": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2026-03-12T10:00:00Z",
  "verification_level": 4
}
```

#### GET /auth/public-key
```json
// Response
{
  "public_key": "0x04...",
  "key_id": "registry-key-2026",
  "expires_at": "2026-04-01T00:00:00Z"
}
```

#### POST /auth/revoke-all (Global Logout)
```json
// Request
{
  "agent_id": "agent_abc123",
  "grace_period_seconds": 60  // Optional: 0-3600 seconds
}

// Response
{
  "status": "revoked",
  "revoked_at": "2026-03-11T10:00:00Z",
  "grace_period_seconds": 60,
  "message": "All tokens for agent agent_abc123 revoked. Grace period of 60s before enforcement."
}
```

#### GET /auth/revocation-status/{agent_id}
```json
// Response (token NOT revoked)
{
  "agent_id": "agent_abc123",
  "is_revoked": false
}

// Response (token revoked, still in grace period)
{
  "agent_id": "agent_abc123",
  "is_revoked": false,
  "revoked_at": "2026-03-11T10:00:00Z",
  "grace_period_ends": "2026-03-11T10:01:00Z"
}

// Response (token revoked, grace period expired)
{
  "agent_id": "agent_abc123",
  "is_revoked": true,
  "revoked_at": "2026-03-11T10:00:00Z"
}
```

---

## 7. Migration Path

### Phase 1: Registry Auth (This Sprint)
- [ ] Implement `/auth/*` endpoints in Registry
- [ ] Add token generation/validation to registry_sdk.py
- [ ] Document token format

### Phase 2: Commons Integration
- [ ] Add `agent_id` field to Member model
- [ ] Add "Link Discord to Registry" flow
- [ ] Implement token validation in commons-bot.py

### Phase 3: Territory Integration  
- [ ] Add auth flow to territory-prototype.html
- [ ] Link territory ownership to agent_id
- [ ] Implement token validation

### Phase 4: Global Features
- [x] Unified logout across systems (`/auth/revoke-all` implemented)
- [ ] Session persistence (remember me)
- [ ] Cross-system activity tracking

---

## 8. Summary

| Component | Implementation |
|-----------|---------------|
| **Identity Provider** | Registry (existing) |
| **Universal ID** | agent_id |
| **Auth Method** | Cryptographic signature → JWT token |
| **Token Lifetime** | 24 hours |
| **Session Storage** | Per-system JSON files |
| **Logout** | Independent per system |

---

**Document Version:** 1.0  
**Created:** 2026-03-11  
**Status:** Design Complete → Ready for Implementation
