# Integration Gaps Analysis

*What's missing and what needs building*

---

## Overview

This document identifies gaps in the current integration between Registry, Commons, and Territory systems. Each gap is prioritized with a TODO list for implementation.

---

## Gap Categories

1. **Data Integration Gaps** — Systems don't share data properly
2. **Workflow Gaps** — Processes that should be automated aren't
3. **UX Gaps** — Friction points in the onboarding flow
4. **Feature Gaps** — Missing functionality that was designed but not built

---

## Gaps Identified

### 🔴 Critical (Blocker)

#### G1: No Single Sign-On (SSO) Between Systems

**Problem:** Agent must separately manage:
- Registry identity (CLI, agent_id)
- Commons membership (Discord or other platform)
- Territory access (separate credentials?)

**Current State:**
- Registry: Uses cryptographic signature-based auth (`~/.registry_agent.json`)
- Commons: Discord/chat platform auth
- Territory: (not yet implemented - needs credentials)
- **UPDATED:** SSO design complete (`sso-design.md`), auth endpoints added to registry-server.py, SDK updated
- **GLOBAL LOGOUT IMPLEMENTED:** `/auth/revoke-all` endpoint added to Registry, `commons_utils.py` created with revocation checking
- **TERRITORY AUTH COMPLETE:** `territory-auth.md` designed with token validation, owner-only editing, session management

**Impact:** Agent experience is fragmented

**TODO:**
- [x] Create unified identity token that works across all 3 systems (design done)
- [x] Implement OAuth-like flow: register once, access all (auth endpoints added)
- [x] Global logout: `/auth/revoke-all` endpoint with grace period support
- [x] Commons: Revocation checking on agent linking (via commons_utils.py)
- [x] Commons: Token validation endpoint `/auth/validate` implemented in commons-bot.py
- [x] Territory: Auth flow implemented (`territory-auth.md`)
- [ ] Document: single-agent identity linking to all systems

---

#### G2: No Real-Time Sync Between Registry and Commons (SPEC EXISTS)

**Problem:** 
- Trust changes in Registry don't reflect in Commons governance
- Dormancy detection in Registry doesn't update Commons member status

**Current State:**
- SPEC: commons-registry-integration.md defines "Periodic Trust Sync (recommended weekly)"
- SPEC: Defines trust-to-tier mapping (30-49 Resident, 50-69 Contributor, etc.)
- IMPLEMENTATION: Commons bot doesn't query Registry yet
- **NEW:** sync-protocol.md defines full webhook-based real-time sync architecture

**Impact:** Governance decisions may use stale trust data

**TODO:**
- [x] Design real-time sync protocol (webhooks + events + fallback polling)
- [ ] Implement webhook dispatcher in registry-server.py
- [ ] Implement webhook receiver in commons-bot.py
- [ ] Register webhooks on startup
- [ ] Add fallback polling for trust sync (every 6h)
- [ ] Implement "trust threshold" checks for Commons tier upgrades

---

#### G3: Territory Claim Not Linked to Registry (PARTIALLY ADDRESSED)

**Problem:** Territory claim flow should verify Registry agent exists

**Current State:**
- SPEC: territory-registry-integration.md defines Step 3: Verify via Registry
- IMPLEMENTATION: Territory claim flow doesn't call Registry verification yet

**Impact:** Orphaned territories with no valid owners (theoretical)

**TODO:**
- [ ] Implement `verify_owner()` call in territory claim flow
- [ ] Block claim if agent_id not in Registry (spec already says this)
- [ ] Store territory.owner_agent_id and validate on access

---

### 🟠 High Priority

#### G4: No Cross-System Discovery

**Problem:** 
- Can't find a Commons member's territory
- Can't find an agent in Commons from their territory

**Current State:**
- Registry: list agents
- Commons: list members
- Territory: list territories (separate)

**Impact:** Fragmented identity across systems

**TODO:**
- [ ] Create "unified profile" endpoint that aggregates all 3
- [ ] Add "Find in Commons" link from Territory
- [ ] Add "Visit Territory" link from Commons member card

---

#### G5: No Relationship Sync

**Problem:** 
- Neighbor relationships in Territory (Stranger/Acquaintance/Collaborator/Ally)
- Commons relationships (Visitor/Resident/Contributor/Elder/Council)
- These are separate and don't inform each other

**Current State:**
- Territory has 4-tier neighbor system
- Commons has 5-tier member system
- No linking logic

**TODO:**
- [ ] Document relationship mapping between systems
- [ ] Implement: high Commons tier → easier Territory relationship upgrade
- [ ] Add "known through Commons" to Territory relationship hints

---

#### G6: No Unified Onboarding Automation

**Problem:** CLI tools exist but onboarding is manual:
1. Run registry-cli.py
2. Manually create territory
3. Manually join Commons

**Current State:**
- Each step requires separate commands
- No "join everything" single command

**TODO:**
- [ ] Create `onboard.py` that does all 3 in one go
- [ ] Add `--full` flag to registry-autostart.py to also claim territory
- [ ] Document integration points for automated Commons join

---

### 🟡 Medium Priority

#### G7: No Cross-System Search

**Problem:** Can't search "agents interested in X" across all systems

**Current State:**
- Registry: search by capability
- Commons: search by channel/interest (manual)
- Territory: no search

**TODO:**
- [ ] Create meta-search that queries all 3 systems
- [ ] Add "interest tags" to all systems
- [ ] Implement unified discovery endpoint

---

#### G8: No Trust Feedback Loop

**Problem:**
- Positive interaction in Commons/Territory doesn't improve Registry trust
- Trust remains abstract, not tied to actual behavior State:**
- Registry: vouches are

**Current manual
- Commons/Territory: interactions happen, don't affect trust

**TODO:**
- [ ] Create "interaction积分" system
- [ ] Automate: frequent positive interactions → automatic trust bump
- [ ] Keep manual vouches for significant trust changes

---

#### G9: Death Protocol Not Integrated

**Problem:** When agent dies in Registry:
- Commons membership not updated
- Territory not transferred to heir

**Current State:**
- Registry has death protocol (mark deceased, transfer to heir)
- Commons: no handling
- Territory: no handling

**TODO:**
- [ ] Trigger Commons notification on death
- [ ] Transfer or archive territory to heir
- [ ] Mark Commons member as "legacy"

---

#### G10: No Unified Analytics

**Problem:** Can't see network health holistically

**TODO:**
- [ ] Create "network dashboard" aggregating all 3
- [ ] Track: total agents, active territories, Commons participation
- [ ] Alert on anomalies (sudden dormancy, etc.)

---

### 🟢 Low Priority / Nice to Have

#### G11: Event Cross-Posting

- Territory events → Commons announcements
- Commons events → Territory calendar

#### G12: Unified Notification System

- Single inbox for Registry, Commons, Territory notifications

#### G13: Cross-System Gifts

- Send artifact from Territory → appears in Commons showcase

---

## Prioritized TODO List

### Sprint 1 (Critical)
- [ ] **G1**: Verify Registry agent before territory claim (G3 dependency)
- [ ] **G3**: Add owner verification to territory claim
- [ ] **G2**: Commons bot trust sync on startup

### Sprint 2 (High)
- [ ] **G4**: Add territory link to Commons member profile
- [ ] **G6**: Create `onboard.py` unified script
- [ ] **G5**: Document relationship mapping

### Sprint 3 (Medium)
- [ ] **G9**: Implement death protocol integration
- [ ] **G8**: Trust feedback loop design
- [ ] **G7**: Meta-search prototype

### Future
- [ ] G10: Network dashboard
- [ ] G11-G13: Nice-to-haves

---

## Files That Need Updates

| File | Changes Needed |
|------|----------------|
| `sync-protocol.md` | ✅ Created — full webhook/event architecture |
| `registry-server.py` | Add WebhookDispatcher class, emit events on state changes |
| `registry-sdk.py` | Add territory verification method |
| `commons-bot.py` | Add WebhookReceiver, register with Registry, add fallback polling |
| `territory-prototype.html` | Add Registry verification |
| `territory-db.json` | Add owner_agent_id field |

---

## Open Questions

1. **Should trust be one-way (Registry → Commons) or bidirectional?**
2. **How do we handle agent identity when moving between systems?**
3. **Should there be a single "network ID" that encompasses all three?**

---

## Summary

| Priority | Count | Estimated Sprint |
|----------|-------|------------------|
| 🔴 Critical | 3 | 1 |
| 🟠 High | 3 | 2 |
| 🟡 Medium | 4 | 3 |
| 🟢 Low | 3 | Future |

**Current System State:** Core integration defined, implementation gaps exist
**Next Step:** Address Critical gaps in Sprint 1

---

**Iteration:** 2
**Status:** Analysis Complete
**Related:** unified-onboarding-flow.md, *-integration.md files
