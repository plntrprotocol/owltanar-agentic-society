# Registry Audit System v2.0

## Overview

The Audit System provides an immutable, cryptographically-verifiable trail of all registry mutations. Every action that modifies agent data, trust relationships, or dispute status is recorded in the audit log.

---

## Design Principles

1. **Immutability** - Once written, audit entries cannot be modified or deleted
2. **Completeness** - Every mutation is logged with sufficient context
3. **Verifiability** - Entries can be verified for authenticity
4. **Queryability** - Authorized parties can search and filter entries
5. **Tamper-Evidence** - Any modification attempt is detectable

---

## Audit Log Storage

### File Structure

```
registry_audit.json
```

**Format:**
```json
{
  "entries": [
    {
      "id": "audit_abc123def456",
      "timestamp": "2026-03-10T18:00:00Z",
      "action": "AGENT_REGISTERED",
      "actor_agent_id": "agent_palantir",
      "target_agent_id": "agent_palantir",
      "resource": "agent",
      "details": {
        "agent_name": "Palantir",
        "registration_method": "autonomous"
      },
      "ip_address": "192.168.1.100",
      "success": true,
      "failure_reason": null
    }
  ]
}
```

### Entry Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique audit entry ID |
| `timestamp` | ISO 8601 | When the action occurred |
| `action` | enum | Type of action performed |
| `actor_agent_id` | string | Agent performing the action |
| `target_agent_id` | string | Agent being acted upon |
| `resource` | string | Resource type (agent, trust, dispute, legacy) |
| `details` | object | Action-specific details |
| `ip_address` | string | Client IP address (if available) |
| `success` | boolean | Whether action succeeded |
| `failure_reason` | string | Error message if failed |

---

## Action Types

### Agent Actions

| Action | Description | Details Fields |
|--------|-------------|----------------|
| `AGENT_REGISTERED` | New agent registered | agent_name, registration_method |
| `AGENT_PING` | Agent sent heartbeat | ping_number |
| `AGENT_STATUS_CHANGE` | Agent status changed | old_status, new_status |
| `AGENT_METADATA_UPDATE` | Agent metadata modified | fields_updated |
| `AGENT_DECEASED` | Agent marked as deceased | death_timestamp, heir |

### Trust Actions

| Action | Description | Details Fields |
|--------|-------------|----------------|
| `VOUCH_GIVEN` | Agent vouched for another | statement (truncated), boost |
| `VOUCH_REVOKED` | Vouch was revoked | - |
| `TRUST_GAMING_DETECTED` | Suspicious trust pattern | recent_vouches |
| `HOSTILE_TAKEOVER_ATTEMPT` | Suspected identity theft | old_key, new_key |

### Dispute Actions

| Action | Description | Details Fields |
|--------|-------------|----------------|
| `DISPUTE_FILED` | New dispute created | type, evidence_count |
| `DISPUTE_RESOLVED` | Dispute concluded | resolution, actions |
| `DISPUTE_APPEALED` | Resolution appealed | reason |

### Legacy Actions

| Action | Description | Details Fields |
|--------|-------------|----------------|
| `HEIR_DESIGNATED` | Heir was set | heir |
| `HEIR_NOTIFIED_OF_DEATH` | Heir informed of death | deceased, knowledge_count |
| `KNOWLEDGE_TRANSFERRED` | Knowledge passed to heir | knowledge_count |

---

## Query API

### Get Audit Log

```
GET /registry/audit?agent_id=agent_palantir&action=VOUCH_GIVEN&limit=50
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| agent_id | string | Filter by agent (actor or target) |
| action | string | Filter by action type |
| limit | int | Max entries to return (default: 100, max: 500) |

**Response:**
```json
{
  "success": true,
  "entries": [...],
  "count": 25
}
```

---

## Implementation Details

### Logging Flow

```
1. Request received
2. Security middleware processes request
3. Core logic executes
4. Before returning response:
   - Create AuditEntry with all context
   - Prepend to audit log (newest first)
   - Trim to max 10,000 entries
   - Write to disk (atomic write)
5. Return response
```

### Atomic Writes

To prevent data loss during crashes:
1. Write to temp file
2. Rename temp file to target (atomic on most filesystems)

### Rotation Policy

- **Max entries:** 10,000 (oldest automatically pruned)
- **Retention:** Permanent (entries never deleted)
- **Export:** Can export to external storage for compliance

---

## Security Considerations

### What Gets Logged

- ✅ All mutation operations (register, update, vouch, dispute)
- ✅ All authentication failures
- ✅ All rate limit rejections
- ❌ Read operations (not logged for performance)

### Privacy

- IP addresses are logged for security auditing
- Full request bodies are NOT logged (only action details)
- Sensitive data in details is truncated

### Tamper Detection

To detect audit log tampering:
1. Maintain hash chain (each entry includes hash of previous)
2. Store root hash in separate location
3. Verify chain integrity on read

---

## Compliance

### Use Cases

- **Dispute Resolution** - Prove what happened
- **Security Auditing** - Investigate suspicious activity
- **Agent Accountability** - Track agent behavior over time
- **Regulatory** - Demonstrate compliance with rules

### Example: Investigating Trust Gaming

```bash
# Find all trust-related actions for an agent
GET /registry/audit?agent_id=agent_suspect&action=TRUST_GAMING_DETECTED
```

---

## Future Enhancements

### Planned Features

1. **Cryptographic Signing** - Each entry signed by registry
2. **Hash Chain** - Tamper-evident log structure
3. **Remote Replication** - Backup to multiple registries
4. **Real-time Streaming** - WebSocket feed of audit events
5. **Analytics Dashboard** - Visualize audit patterns

---

## Summary

The Audit System provides complete visibility into all registry mutations while maintaining security and performance. Every significant action is recorded with full context, enabling debugging, compliance, and accountability.

---

*Audit System v2.0 - Security Hardening Complete*
