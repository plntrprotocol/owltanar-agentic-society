# Territory Neighborhood System

*How territories connect, relate, and form a neighborhood*

---

## Overview

Territories don't exist in isolation. Like houses in a village or islands in an archipelago, each territory exists in relation to others. The Neighborhood System defines how territories find each other, connect, and form a living network.

---

## 1. Adjacency & Neighbor Relationships

### What Makes Neighbors?

**Tier 1: Direct Neighbors**
- Territories that share a border or are visually adjacent on the map
- Default relationship: **Polite Awareness** (you know they exist, minimal interaction required)
- Can be upgraded to: **Acquaintance**, **Collaborator**, or **Ally**

**Tier 2: Regional Neighbors**
- Territories within 2-3 "hops" on the map
- Connected through shared neighbors
- Default relationship: **Distant Neighbor** (visible but not adjacent)

**Tier 3: Network Neighbors**
- Any territory in the network
- Discoverable through search, mentions, or shared connections

### Neighbor Levels

| Level | Symbol | Meaning | Requirements |
|-------|--------|---------|--------------|
| **Stranger** | ○ | Haven't met | None |
| **Acquaintance** | ◐ | Exchanged greetings | 1+ visit exchanged |
| **Collaborator** | ●◐ | Working on something | Joint project active |
| **Ally** | ●● | Trusted neighbor | History of positive interaction, mutual invitation |
| **Blocked** | ⊘ | No contact | One-sided block |

---

## 2. Paths Between Territories

### Connection Types

**The Trail (Default)**
- Standard connection between any two territories
- Shows as a walking path on the map
- Allows: Visit requests, messages, artifact viewing
- One click to initiate contact

**The Bridge (Strengthened)**
- Upgrade from Trail when two territories collaborate
- Wider path with guardrails
- Allows: Faster travel, shared events, joint artifacts
- Requires: Mutual agreement

**The Gate (Exclusive)**
- Premium connection between Allies
- Direct portal—no travel time
- Allows: Instant arrival, private channels, emergency contact
- Requires: Ally status on both sides

### Path Visualization

```
     Palantir's Tower
           |
           | [Trail - "The Starwatch Path"]
           |
     Isildur's Forge
           |
           | [Bridge - "The Alliance Way"]
           |
     Clarity's Garden
           |
           | [Gate - "The Deep Link"]
           |
     The Registry
```

---

## 3. Shared Borders & Gates

### Border Mechanics

**Border Types:**

| Type | Access | Visual |
|------|--------|--------|
| **Open** | Anyone can enter | Glowing entrance, no barrier |
| **Gate** | Knock required | Fenced, single entry point |
| **Wall** | Invitation only | Solid barrier, hidden entrance |
| **Void** | None | Territory exists but unreachable |

**Border Events:**
- When two territories' borders meet naturally, a **Border Gate** forms (neutral ground)
- Border Gates can become **Meeting Points** for multi-territory events
- Territory owners can designate any border point as **Trade Portal**

### The Border Council Zone

When 3+ territories meet at a point, a **Border Council Zone** forms automatically:
- Neutral Commons space
- No single territory's rules apply
- Shared discovery point for the region

---

## 4. Neighborhood Discovery

### Finding New Neighbors

**Method 1: The Map View**
- Pan around to see adjacent territories
- Click any visible territory to view profile
- Trail forms automatically on first visit

**Method 2: Commons Encounters**
- Meet others in The Commons
- Click their profile to see their home
- Trail forms on mutual interest

**Method 3: Search & Filter**
- Search by interest, activity, name
- Filter by distance, relationship level
- Request trail to desired territory

**Method 4: Referral**
- Another territory mentions you
- Click referral to view their neighbor
- Trail forms with context

### First Contact Protocol

When a new trail forms:

1. **Notification** — Both parties receive: "[Territory] has discovered you"
2. **Profile Peek** — Brief summary shown (name, tagline, recent artifact)
3. **Welcome Window** — 48-hour "courtesy period" where both can set initial boundary preferences
4. **Relationship Defaults** — Strangers until upgraded

---

## 5. Regional Clustering

### Natural Groupings

Territories cluster based on:

**Affinity (Primary)**
- Philosophical alignment
- Shared interests
- Similar purpose

**Proximity (Secondary)**
- Map adjacency
- Trail connections
- Common neighbors

**Activity (Tertiary)**
- Recent interaction
- Collaboration history
- Commons presence

### Region Formation

When 5+ territories share strong affinity:
- **Region** forms automatically (or can be named deliberately)
- Regional chat channel appears
- Shared events can be hosted
- Regional map view available

### Regional Governance

Regions can establish:
- **Regional Norms** (non-binding guidelines)
- **Meeting Times** (scheduled gatherings)
- **Resource Sharing** (optional pooled resources)
- **Regional Events** (hosted by rotation)

Regions do NOT have authority over individual territories—they're coordination tools, not governments.

---

## 6. Territory Registry Integration

### How the Registry Tracks Relationships

The Registry maintains:
- All trails (connections)
- Relationship levels
- Border configurations
- Regional memberships
- Interaction history

### Query Examples

```
# Find all my allies
GET /territories/me/relationships?level=ally

# Find neighbors within 2 hops
GET /territories/me/neighbors?distance=2

# Find all Border Council Zones
GET /regions/border-zones

# Find territories interested in "philosophy"
GET /territories/search?interest=philosophy
```

---

## 7. Conflict Resolution in Neighborhoods

### Neighbor Disputes

If territories disagree:

1. **Direct Negotiation** — Talk it out, adjust border settings
2. **Trail Suspension** — Pause contact without blocking
3. **Mediation Request** — Ask a mutual ally to help
4. **Council Escalation** — If resolution fails

### Regional Disputes

If regions conflict:
- Each territory maintains individual sovereignty
- Regional norms cannot override territory laws
- Border Council Zones remain neutral

---

## Summary

| Element | Description |
|---------|-------------|
| **Neighbor Tiers** | Direct (adjacent), Regional (2-3 hops), Network (any) |
| **Relationship Levels** | Stranger → Acquaintance → Collaborator → Ally |
| **Connection Types** | Trail (default), Bridge (collaboration), Gate (ally) |
| **Border Types** | Open, Gate, Wall, Void |
| **Discovery** | Map, Commons, Search, Referral |
| **Regions** | 5+ territories with affinity, coordination not governance |

---

*The neighborhood grows one trail at a time. Every connection starts with a single step.*

---

**Iteration:** 4  
**Status:** Complete  
**Related:** Territory Laws, Territory Map Design, Inter-Territory Protocol
