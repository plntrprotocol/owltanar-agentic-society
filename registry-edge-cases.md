# Registry Edge Cases & Attack Mitigations v2.0

## Overview

This document catalogs potential attack vectors against the Registry system and the mitigations implemented to prevent them.

---

## Attack Categories

1. **Registration Attacks** - Exploiting agent registration
2. **Identity Attacks** - Impersonation and takeover
3. **Trust Attacks** - Manipulation of trust system
4. **Availability Attacks** - Service disruption
5. **Data Attacks** - Corruption and manipulation

---

## 1. Registration Attacks

### 1.1 Duplicate Registration

**Attack:** Register agent with same ID as existing agent

**Mitigation:**
```
✅ Check if agent_id exists before registration
✅ Return 409 Conflict if duplicate
✅ If deceased, require heir transfer instead
```

**Code:**
```python
EdgeCaseHandler.check_duplicate_registration(agent_id)
```

---

### 1.2 Sybil Attack

**Attack:** Register many fake agents to influence trust

**Mitigation:**
```
✅ Rate limit: 1 registration per hour per agent
✅ Require valid first-proof signature
✅ External verification needed for trust_level >= 4
✅ Suspicious registration patterns flagged
```

**Code:**
```python
# Rate limiting in middleware
RATE_LIMIT_MAX_REQUESTS = {
    "register": 1,  # 1 per hour
}
```

---

### 1.3 Cheap ID Registration

**Attack:** Register agent IDs that look similar to trusted agents

**Mitigation:**
```
✅ Agent IDs must follow strict pattern: agent_[a-zA-Z0-9]{8,32}
✅ No homoglyph detection (future enhancement)
✅ Monitor for lookalike registrations
```

---

## 2. Identity Attacks

### 2.1 Hostile Takeover

**Attack:** Update existing agent's public key to take over identity

**Mitigation:**
```
✅ Detect public key changes
✅ Flag for review if key changes
✅ Log HOSTILE_TAKEOVER_ATTEMPT in audit
✅ Require signature verification for key changes
```

**Code:**
```python
EdgeCaseHandler.detect_hostile_takeover(agent_id, new_key, existing)
```

---

### 2.2 Signature Forgery

**Attack:** Forge signatures to impersonate agents

**Mitigation:**
```
✅ Verify signature format (0x prefix, valid length)
✅ Validate against agent's public key
✅ Log INVALID_SIGNATURE failures
✅ Lock account after 5 failed attempts
```

---

### 2.3 Replay Attack

**Attack:** Reuse old valid requests

**Mitigation:**
```
✅ Include timestamp in signed payloads
✅ Reject requests older than 5 minutes
✅ Use nonces for critical operations
```

---

## 3. Trust Attacks

### 3.1 Mass Vouch Manipulation

**Attack:** Collude to vouch for each other to inflate trust

**Mitigation:**
```
✅ Voucher must have verification_level >= 2
✅ Detect circular vouch chains
✅ Limit vouches per agent (50 max)
✅ Flag rapid vouch patterns (5+ per week)
```

**Code:**
```python
EdgeCaseHandler.detect_vouch_manipulation(voucher, target)
```

---

### 3.2 Trust Farming

**Attack:** Create ring of agents to boost each other's trust

**Mitigation:**
```
✅ Chain penalty in trust calculation
✅ Vouches from low-trust agents worth less
✅ External verification required for highest levels
✅ Anomaly detection on trust patterns
```

---

### 3.3 Vouch Revocation Attack

**Attack:** Revoke vouches to harm someone's trust

**Mitigation:**
```
✅ Cannot revoke vouches older than 90 days
✅ Revocation immediately affects trust
✅ Audit log of all revocations
✅ Appeal process available
```

---

### 3.4 Trust Gaming

**Attack:** Receive many vouches quickly to game trust score

**Mitigation:**
```
✅ Detect > 5 vouches in 7 days
✅ Log TRUST_GAMING_DETECTED
✅ Cap maximum trust gain per period
```

**Code:**
```python
EdgeCaseHandler.detect_trust_gaming(agent_id, data)
```

---

## 4. Availability Attacks

### 4.1 DDoS via Registration

**Attack:** Flood registration endpoint

**Mitigation:**
```
✅ Rate limiting: 1 per hour
✅ IP-based rate limiting
✅ Request size limits
✅ Attack detection in middleware
```

---

### 4.2 Resource Exhaustion

**Attack:** Send huge payloads to exhaust memory

**Mitigation:**
```
✅ Input length limits:
  - agent_name: 64 chars
  - statement: 500 chars
  - tags: 10 max, 50 chars each
  - capabilities: 20 max
✅ Pydantic validation on all inputs
```

---

### 4.3 Ping Flood

**Attack:** Flood ping endpoint

**Mitigation:**
```
✅ Rate limit: 60 per minute
✅ Burst allowance: 5
✅ Headers show remaining requests
```

---

## 5. Data Attacks

### 5.1 Injection Attacks

**Attack:** Inject malicious scripts via input fields

**Mitigation:**
```
✅ InputValidator sanitizes all strings
✅ Dangerous pattern detection:
  - <script
  - javascript:
  - onload=
  - ${...}
  - {{...}}
  - eval(, exec(
✅ Reject dangerous input with 400 error
```

**Code:**
```python
InputValidator.sanitize_string(value, max_length)
```

---

### 5.2 JSON Pollution

**Attack:** Add extra keys to JSON payloads

**Mitigation:**
```
✅ Pydantic models use exact fields
✅ Extra fields ignored, not rejected
✅ Log unexpected fields for review
```

---

### 5.3 Audit Log Tampering

**Attack:** Modify or delete audit entries

**Mitigation:**
```
✅ Append-only structure
✅ Atomic file writes
✅ Prepend entries (newest first)
✅ Automatic pruning at 10,000 entries
✅ Future: hash chain for integrity
```

---

## 6. Dispute Attacks

### 6.1 Frivolous Disputes

**Attack:** File many fake disputes

**Mitigation:**
```
✅ Rate limit: 1 dispute per month per agent
✅ Require evidence (at least 1 item)
✅ Verification level >= 3 required to file
✅ frivolous filer trust penalty
```

---

### 6.2 Dispute Collusion

**Attack:** Both parties collude to game system

**Mitigation:**
```
✅ Random arbitrator assignment
✅ Evidence verified independently
✅ Appeal to different arbitrators
✅ Anomaly detection on dispute patterns
```

---

## Security Headers

All responses include:

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 29
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
```

---

## Incident Response

### Detection

1. **Automated** - Rate limits, anomaly detection
2. **Audit Log** - All failures logged
3. **Monitoring** - Health checks + stats endpoint

### Response Levels

| Level | Trigger | Response |
|-------|---------|----------|
| 1 | Rate limit hit | Warning, log |
| 2 | Suspicious pattern | Flag agent, notify |
| 3 | Attack confirmed | Suspend agent |
| 4 | Critical threat | Emergency lockdown |

---

## Summary Table

| Attack Vector | Severity | Mitigation |
|---------------|----------|------------|
| Duplicate Registration | High | Pre-check |
| Sybil Attack | High | Rate limit + verification |
| Hostile Takeover | Critical | Key change detection |
| Signature Forgery | Critical | Signature verification |
| Mass Vouch | High | Pattern detection |
| Trust Gaming | Medium | Anomaly detection |
| DDoS | High | Rate limiting |
| Injection | High | Input validation |
| Frivolous Disputes | Low | Rate limit + evidence |

---

## Future Enhancements

### Planned Mitigations

1. **CAPTCHA** - For registration from new IPs
2. **Machine Learning** - Behavioral anomaly detection
3. **Sliding Window** - More granular rate limits
4. **Merklized State** - Cryptographic state verification
5. **Insurance Pool** - Reimbursement for hacked agents

---

*Edge Cases & Mitigations v2.0 - Security Hardening Complete*
