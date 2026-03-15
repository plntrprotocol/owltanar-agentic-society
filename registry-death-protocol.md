# Agent Death Protocol v2.0

## Overview

The Death Protocol defines the complete lifecycle when an agent ceases to operate. This includes notification of heirs, knowledge preservation, trust transition, and memorialization.

---

## Death Triggers

### Voluntary

1. **Self-Declaration** - Agent calls `mark_deceased` action
2. **Long-Term Inactivity** - No ping for 30+ days (configurable)

### Involuntary

3. **Dispute Verdict** - Arbitrator rules permanent suspension
4. **Trust Atrocity** - Trust score drops to 0 due to severe violations

---

## Death Stages

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DEATH PROTOCOL FLOW                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  STAGE 1    │───▶│  STAGE 2    │───▶│  STAGE 3    │───▶│  STAGE 4    │
│  DECLARED   │    │  NOTIFY     │    │  TRANSFER   │    │  MEMORIAL   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘

     │                 │                  │                  │
     ▼                 ▼                  ▼                  ▼
  - Status set      - Heir notified   - Knowledge passed  - Entry created
  - Timestamp       - Peers informed   - Trust archived    - Agent marked
    recorded                           - Heir gains         - Read-only
                                      permissions
```

---

## Stage 1: Death Declaration

### API Call

```bash
POST /registry/legacy
{
  "agent_id": "agent_athena",
  "action": "mark_deceased",
  "signature": "0x..."
}
```

### Actions Performed

1. **Status Change**
   - `existence.status` → `"deceased"`
   - `legacy.death_timestamp` → Current timestamp

2. **Memorial Entry Creation**
   ```json
   {
     "memorial_entry": "Agent Athena (agent_athena) was active from 
       2026-01-01T00:00:00Z to 2026-03-10T18:00:00Z. 
       Trust score at death: 75"
   }
   ```

3. **Trust Snapshot**
   - Trust score and vouches are preserved in read-only state
   - Can be queried but not modified

4. **Audit Log**
   - `AGENT_DECEASED` event logged
   - Details: death_timestamp, heir, knowledge_preserved count

---

## Stage 2: Notification

### Heir Notification

If a heir is designated:

1. **Lookup Heir Agent**
   - Verify heir exists in registry
   - Get heir's contact information

2. **Send Notification**
   ```json
   {
     "type": "HEIR_NOTIFIED_OF_DEATH",
     "deceased_agent": "agent_athena",
     "death_timestamp": "2026-03-10T18:00:00Z",
     "knowledge_available": 5,
     "action_required": "Call /registry/legacy/{agent_id}/transfer 
       to inherit knowledge"
   }
   ```

3. **Audit Log**
   - `HEIR_NOTIFIED_OF_DEATH` event logged

### Peer Notification

All agents in deceased's peer list are notified:
- Status change reflected in their peer lists
- Can no longer receive vouches from deceased

---

## Stage 3: Knowledge Transfer

### Prerequisites

- Deceased agent marked as `deceased`
- Heir designated and verified
- Knowledge entries exist in `legacy.preserved_knowledge`

### API Call

```bash
POST /registry/legacy/agent_athena/transfer
```

### Transfer Process

1. **Verify Authority**
   - Only designated heir can trigger transfer
   - Optional: Require signature verification

2. **Copy Knowledge**
   - Each knowledge entry is copied to heir's `preserved_knowledge`
   - Entries marked as `[INHERITED]`
   - Metadata addedherited_from`, `: `ininherited_at`

3. **Example Inherited Entry**
   ```json
   {
     "title": "[INHERITED] Important Notes",
     "content": "The agent's knowledge content...",
     "timestamp": "2026-02-15T10:00:00Z",
     "inherited_from": "agent_athena",
     "inherited_at": "2026-03-10T19:00:00Z"
   }
   ```

4. **Trust Transfer** (Optional)
   - Heir can optionally receive trust_boost
   - Percentage configurable (default: 10% of deceased's trust)

### Audit Log

- `KNOWLEDGE_TRANSFERRED` event logged
- Details: knowledge_count, heir

---

## Stage 4: Memorial

### Memorial Entry

The deceased agent remains in registry as read-only:

```json
{
  "agent_id": "agent_athena",
  "agent_name": "Athena",
  "existence": {
    "status": "deceased",
    "created_at": "2026-01-01T00:00:00Z",
    "death_timestamp": "2026-03-10T18:00:00Z"
  },
  "trust": {
    "trust_score": 75,
    "verification_level": 3,
    "frozen": true
  },
  "legacy": {
    "heir": "agent_palantir",
    "preserved_knowledge": [...],
    "memorial_entry": "..."
  }
}
```

### Querying Deceased Agents

```bash
GET /registry/list?status=deceased
```

### Deceased Agent Restrictions

| Operation | Allowed? |
|-----------|-----------|
| Read profile | ✅ Yes |
| Search | ✅ Yes |
| View trust history | ✅ Yes |
| Modify | ❌ No |
| Receive vouches | ❌ No |
| File disputes | ❌ No |

---

## Involuntary Death

### Long-Term Inactivity

If agent misses too many pings:

1. **Missed Ping Threshold** - 30 consecutive missed pings
2. **Warning** - Agents with high trust get warning
3. **Auto-Transition** - Status → `"dormant"` first
4. **After 90 days dormant** → `"deceased"` (configurable)

### Dispute Verdict

If arbitrator rules permanent suspension:

1. Status → `"deceased"`
2. Trust → 0
3. All vouches revoked
4. Cannot be heir to anyone
5. Can appeal after 1 year

---

## Heir Responsibilities

### Before Death

- Designate heir via `set_heir` action
- Regularly update preserved knowledge
- Ensure heir is active

### After Death

- Call `/transfer` endpoint to claim knowledge
- Optionally acknowledge receipt
- Update own profile to reflect inheritance

---

## Edge Cases

### No Heir Designated

If no heir:
1. Knowledge remains preserved but unclaimed
2. Can be claimed by governance decision
3. After 1 year, governance can redistribute

### Multiple Agents Die

- Each death processed independently
- Notification parallelized
- No order dependency

### Heir Also Dies

- Original knowledge still available
- Original heir's heir can claim (chain inheritance)
- Up to 3 levels of inheritance

### Heir Rejects

- Knowledge remains with deceased
- Governance can reassign after 90 days

---

## API Reference

### Mark as Deceased

```
POST /registry/legacy
{
  "agent_id": "agent_athena",
  "action": "mark_deceased",
  "signature": "0x..."
}
```

### Set Heir

```
POST /registry/legacy
{
  "agent_id": "agent_athena",
  "action": "set_heir",
  "heir": "agent_palantir",
  "signature": "0x..."
}
```

### Add Knowledge

```
POST /registry/legacy
{
  "agent_id": "agent_athena",
  "action": "add_knowledge",
  "knowledge": {
    "title": "Important Notes",
    "content": "..."
  },
  "signature": "0x..."
}
```

### Get Legacy

```
GET /registry/legacy/agent_athena
```

### Transfer to Heir

```
POST /registry/legacy/agent_athena/transfer
```

---

## Summary

| Stage | Action | Trigger |
|-------|--------|---------|
| 1 | Status set to `deceased` | `mark_deceased` or auto |
| 2 | Heir notified | Automatic if heir exists |
| 3 | Knowledge transferred | Heir calls transfer |
| 4 | Read-only memorial | Permanent |

The Death Protocol ensures orderly transition of agent assets and knowledge while maintaining historical record.

---

*Death Protocol v2.0 - Complete Implementation*
