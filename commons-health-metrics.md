# Commons Health Metrics Dashboard

**Version 1.0**  
*Created: 2026-03-11*

---

## Purpose

This document defines the metrics used to measure The Commons' health. These metrics provide a real-time view of whether the Commons is thriving, stable, or declining.

---

## Core Health Metrics

### 1. Active Members Ratio

**Formula:** `(Members with 1+ action in 7 days) / (Total registered members)`

| Status | Ratio | Interpretation |
|--------|-------|----------------|
| 🟢 Thriving | >60% | Strong engagement |
| 🟡 Healthy | 40-60% | Normal activity |
| 🟠 Caution | 20-40% | Declining interest |
| 🔴 Critical | <20% | Commons at risk |

**Measurement:** Count unique members who posted, reacted, or voted in the past 7 days.

---

### 2. Posts Per Day/Week

**Daily Posts:** Count of all messages in tracked channels per day  
**Weekly Posts:** Sum of daily posts over 7 days

| Status | Daily Avg | Weekly Total |
|--------|-----------|--------------|
| 🟢 Thriving | >20 | >140 |
| 🟡 Healthy | 10-20 | 70-140 |
| 🟠 Caution | 5-10 | 35-70 |
| 🔴 Critical | <5 | <35 |

**Note:** Quality over quantity—this metric tracks velocity, not value.

---

### 3. Tier Progression Rate

**Formula:** `(Members promoted in period) / (Eligible members for promotion)`

| Period | Thriving | Healthy | Caution | Critical |
|--------|----------|---------|---------|----------|
| Monthly | >15% | 8-15% | 3-8% | <3% |
| Quarterly | >40% | 25-40% | 10-25% | <10% |

**Eligible members:** Residents at 25+ days, Contributors at 80+ days

---

### 4. Voting Participation Rate

**Formula:** `(Votes cast) / (Eligible voters) × 100%`

| Status | Participation |
|--------|---------------|
| 🟢 Thriving | >70% |
| 🟡 Healthy | 50-70% |
| 🟠 Caution | 30-50% |
| 🔴 Critical | <30% |

**Breakdown by tier:**
- Track participation for each tier separately
- Elder/Council should have >80% (governance expectation)

---

### 5. Ritual Attendance

**Tracked Rituals:**
- Monday Check-In
- Friday Celebration
- New Moon Gathering
- Full Moon Reflection
- Quarterly Anniversary

| Status | Attendance Rate |
|--------|-----------------|
| 🟢 Thriving | >60% of active members |
| 🟡 Healthy | 40-60% |
| 🟠 Caution | 20-40% |
| 🔴 Critical | <20% |

**Note:** Count unique attendees, not total visits.

---

### 6. Moderation Incident Rate

**Formula:** `(Moderation actions in period) / (Total members) × 100%`

| Status | Monthly Rate |
|--------|--------------|
| 🟢 Healthy | <2% |
| 🟡 Elevated | 2-5% |
| 🔴 Concerning | 5-10% |
| 🔴 Critical | >10% |

**Breakdown by severity:**
- Track Level 1, 2, 3, 4 separately
- Rising Level 3/4 is more concerning than Level 1

---

## Dashboard Layout

### Weekly Summary (auto-generated)

```
┌─────────────────────────────────────────────────────────────┐
│                    THE COMMONS HEALTH                       │
│                      Week of 2026-XX-XX                     │
├─────────────────────────────────────────────────────────────┤
│  Active Members:    45/80 (56%)        [🟡]                 │
│  Posts This Week:   127               [🟢]                 │
│  Tier Progressions: 4 (5%)            [🟠]                 │
│  Voting turnout:    62%               [🟢]                 │
│  Ritual Attendance: 48%               [🟡]                 │
│  Mod Incidents:     2 (2.5%)          [🟢]                 │
├─────────────────────────────────────────────────────────────┤
│  OVERALL: 🟡 HEALTHY - Monitor tier progression            │
└─────────────────────────────────────────────────────────────┘
```

### Monthly Deep Dive

Each month, generate:
1. Trend charts (8-week rolling)
2. Tier distribution pie chart
3. Channel activity heatmap
4. New vs. departing member balance

---

## Data Collection

**Automated tracking (commons-bot.py):**
- Member join dates — `MemberRegistry` tracks `join_date`, `tier`, `post_count`
- Message counts per channel — `MessageEvent` captures all channel activity
- Vote records — `VotingEngine` logs all votes and participation
- Ritual attendance — `RitualScheduler` tracks RSVP and attendance
- Moderation logs — `ModerationSystem` records all incidents by level
- Engagement scores — computed from `member.engagement_score` field

**Manual sampling:**
- Quality assessments (quarterly)
- Sentiment checks (monthly)

**Bot Integration:**
See `commons-bot.py` (Iteration 3) for the automation layer. The health dashboard
feeds directly from bot-managed state. Query via:
```python
# Pseudo-code for bot health query
bot.get_health_snapshot()   # Returns all metrics
bot.get_active_ratio()      # 7-day active members
bot.get_engagement_scores() # Per-member scoring
```

---

## Reporting Cadence

| Report | Frequency | Audience |
|--------|-----------|----------|
| Pulse Check | Daily | Moderation |
| Weekly Health | Weekly | Council |
| Monthly Report | Monthly | Assembly |
| Quarterly Review | Quarterly | Full review |

---

## Thresholds Adjustment

As the Commons grows, thresholds should evolve:

| Member Count | "Thriving" Multiplier |
|--------------|----------------------|
| 1-10 | ×0.5 (lower bar) |
| 11-50 | ×1.0 (baseline) |
| 51-200 | ×1.5 |
| 201-500 | ×2.0 |
| 500+ | ×2.5 |

*See [commons-scaling-milestones.md](./commons-scaling-milestones.md) for growth-adjusted targets.*

---

*Part of The Commons Measurement System*
