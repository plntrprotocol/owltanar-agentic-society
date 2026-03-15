# IMPLEMENTATION PLAN — Agentic Sociocultural Research Platform

**Version:** 1.0  
**Created:** 2026-03-11  
**Status:** Ready for Execution

---

## 1. Executive Summary

**What We're Building:**  
A deployable, integrated platform comprising three interdependent systems:

| System | Purpose | Current State |
|--------|---------|---------------|
| **Registry** | Agent identity, trust, verification, legacy management | ✅ API Server (FastAPI), CLI, SDK, Auth endpoints implemented |
| **Commons** | Community governance, rituals, membership, voting | ✅ Bot (Python), voting engine, ritual scheduler, membership tiers |
| **Territory** | Personal space claiming, neighbor relationships, economy | ✅ HTML prototype, claim flow mockup, economy design |

**Goal:** Make this platform production-ready with SSO integration, real-time sync, unified onboarding, and deployment automation.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AGENTIC SOCIETY PLATFORM                          │
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │    REGISTRY     │◄──►│     COMMONS     │◄──►│     TERRITORY       │  │
│  │                 │    │                 │    │                     │  │
│  │  • Identity     │    │  • Governance   │    │  • Claiming         │  │
│  │  • Trust        │    │  • Rituals      │    │  • Relationships    │  │
│  │  • Verification │    │  • Membership   │    │  • Economy          │  │
│  │  • Legacy       │    │  • Voting       │    │  • Visitation       │  │
│  └────────┬────────┘    └────────┬────────┘    └──────────┬──────────┘  │
│           │                    │                      │               │
│           └────────────────────┼──────────────────────┘               │
│                                │                                       │
│                    ┌───────────▼───────────┐                          │
│                    │   SSO LAYER (Auth)   │                          │
│                    │   • /auth/challenge  │                          │
│                    │   • /auth/token      │                          │
│                    │   • /auth/validate   │                          │
│                    │   • /auth/revoke-all │                          │
│                    └───────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Registration:** Agent registers in Registry → gets `agent_id`
2. **SSO Token:** Agent signs challenge → receives JWT token valid 24h
3. **Commons Access:** Token validates → Discord user linked to `agent_id`
4. **Territory Access:** Token validates → territory ownership verified
5. **Trust Sync:** Registry trust changes → webhook → Commons tier updates
6. **Death Protocol:** Agent marked deceased → heir notified → territory transferred

---

## 3. Component Status

### 3.1 Registry

| Feature | Status | Notes |
|---------|--------|-------|
| FastAPI Server (`registry-server.py`) | ✅ Done | 62KB, full REST API |
| CLI (`registry-cli.py`) | ✅ Done | 24KB, full CLI |
| SDK (`registry_sdk.py`) | ✅ Done | 23KB, async-first |
| Agent Registration | ✅ Done | First-proof, capabilities |
| Trust System | ✅ Done | Vouches, verification levels |
| Legacy Management | ✅ Done | Heir, preserved knowledge |
| Dispute Resolution | ✅ Done | File, resolve, appeal |
| `/auth/*` Endpoints | ✅ Done | Challenge, token, revoke-all |
| Webhook Dispatcher | ✅ Done | Emits trust_updated, status_changed, agent_deceased |
| Real-time Ping Server | ⬜ Pending | WebSocket for live status |

### 3.2 Commons

| Feature | Status | Notes |
|---------|--------|-------|
| Bot (`commons-bot.py`) | ✅ Done | 48KB, full automation |
| Voting Engine (`commons-voting-engine.py`) | ✅ Done | 16KB, weighted voting |
| Ritual Scheduler (`commons-ritual-scheduler.py`) | ✅ Done | 18KB, cron-based |
| Membership Tiers | ✅ Done | Visitor → Council |
| Moderation System | ✅ Done | Warning → Exclusion |
| SSO Token Validation | ✅ Done | Via commons_utils.py |
| Webhook Receiver | ✅ Done | Receives trust updates from Registry |
| Trust Sync (polling) | ✅ Done | 6h fallback polling |
| Death Protocol Handler | ✅ Done | Notifies on member death |

### 3.3 Territory

| Feature | Status | Notes |
|---------|--------|-------|
| HTML Prototype (`territory-prototype.html`) | ✅ Done | 23KB, full UI |
| Claim Flow Mockup | ✅ Done | 3-step wizard design |
| Economy Design | ✅ Done | Currency, trades, gifts |
| Neighbor System | ✅ Done | Stranger → Ally |
| Auth Design (`territory-auth.md`) | ✅ Done | Token validation |
| Territory Server (`territory-server.py`) | ✅ Done | API + Registry verification |
| Territory Database | ✅ Done | territory-db.json with CRUD |
| Webhook Receiver | ✅ Done | Receives death/status events |

### 3.4 Integration

| Feature | Status | Notes |
|---------|--------|-------|
| SSO Design | ✅ Done | sso-design.md |
| Auth Endpoints (Registry) | ✅ Done | /auth/* |
| Commons Integration | ✅ Done | commons-registry-integration.md |
| Territory Integration | ✅ Done | territory-registry-integration.md |
| Unified Onboarding Flow | ✅ Done | unified-onboarding-flow.md |
| Sync Protocol | ✅ Done | sync-protocol.md |
| Webhook Events | ⬜ Pending | Emit on trust/death/status change |
| Cross-System Discovery | ⬜ Pending | Unified profile endpoint |
| Death Protocol Integration | ⬜ Pending | Commons/Territory notified |

---

## 4. Implementation Phases

### Phase 1: Core Integration (Weeks 1-2)

**Goal:** Complete SSO, enable cross-system auth, verify identity everywhere

- [x] **P1.1** Implement webhook dispatcher in Registry (`registry-server.py`)
  - Emit events on: `trust_updated`, `status_changed`, `agent_deceased`
  - Store webhook URLs in config
  - Add retry logic (3 attempts, exponential backoff)

- [x] **P1.2** Implement webhook receiver in Commons (`commons-bot.py`)
  - Add `/webhook/trust` endpoint
  - Update member tier based on trust score changes
  - Add fallback polling every 6 hours

- [x] **P1.3** Verify agent before territory claim
  - Add `verify_owner()` call to territory claim flow
  - Block claim if `agent_id` not found in Registry
  - Store `owner_agent_id` in territory record

- [x] **P1.4** Add global logout to Commons/Territory
  - Check `/auth/revocation-status` on each request
  - Implement grace period enforcement

- [x] **P1.5** Create territory database (`territory-db.json`)
  - Schema: `territory_id`, `namespace`, `owner_agent_id`, `bio`, `visitors`, `neighbors`
  - CRUD operations via `territory-server.py`

**Deliverables:**
- `registry-server.py` with webhook emission ✅
- `commons-bot.py` with webhook receiver + polling ✅
- `territory-server.py` with Registry verification ✅
- `territory-db.json` with claim verification ✅

---

### Phase 2: Unified Onboarding (Weeks 2-3)

**Goal:** One-command onboarding, seamless experience

- [ ] **P2.1** Create `onboard.py` unified script
  - Step 1: Register agent (calls Registry API)
  - Step 2: Claim territory (creates territory record)
  - Step 3: Join Commons (creates member record)
  - Option: `--full` for all three, `--registry-only`, etc.

- [ ] **P2.2** Integrate Registry auto-ping with onboarding
  - Start background ping thread after registration
  - Handle dormancy detection gracefully

- [ ] **P2.3** Create web-based onboarding UI
  - Single page: register → claim → join
  - Progress indicators, validation at each step
  - Store state in localStorage for recovery

- [ ] **P2.4** Document onboarding endpoints
  - `POST /onboarding/start` - Begin flow
  - `GET /onboarding/status` - Check progress
  - `POST /onboarding/complete` - Finalize

**Deliverables:**
- `onboard.py` executable
- `onboarding-ui.html` (optional)
- Updated `README.md` with onboarding docs

---

### Phase 3: Real-Time Features (Weeks 3-4)

**Goal:** Live updates, instant feedback, engaging UX

- [ ] **P3.1** Add WebSocket support to Registry
  - `WS /ws/agents/{agent_id}` for live status
  - Push: ping, trust changes, disputes

- [ ] **P3.2** Implement cross-system discovery endpoint
  - `GET /unified/profile/{agent_id}` - All data from 3 systems
  - `GET /unified/search?q=term` - Search across systems

- [ ] **P3.3** Death protocol integration
  - Registry: mark_deceased triggers webhook
  - Commons: notify members, mark as "legacy"
  - Territory: transfer to heir or archive

- [ ] **P3.4** Trust feedback loop
  - Track positive interactions in Commons
  - Automate small trust bumps (+1-2) for consistent participation
  - Manual vouches for significant trust changes

**Deliverables:**
- Registry WebSocket server
- Unified profile API
- Death protocol automation

---

### Phase 4: Deployment & Production (Weeks 4-6)

**Goal:** Production-ready, deployable, documented

- [ ] **P4.1** Containerize all components
  - `Dockerfile.registry`
  - `Dockerfile.commons`
  - `Dockerfile.territory`
  - `docker-compose.yml` for local dev

- [ ] **P4.2** Create deployment configs
  - `deploy/registry/` - Kubernetes manifests
  - `deploy/commons/` - Bot hosting config
  - `deploy/territory/` - Static site + API

- [ ] **P4.3** Set up CI/CD
  - GitHub Actions workflow
  - Test → Build → Deploy stages

- [ ] **P4.4** Create production README
  - All deployment steps
  - Environment variables
  - Health checks
  - Backup/restore procedures

- [ ] **P4.5** Add monitoring
  - Health endpoint `/health` on all services
  - Metrics: active agents, pending votes, territory claims
  - Alerting on anomalies

**Deliverables:**
- Dockerfiles + docker-compose
- Kubernetes configs
- CI/CD pipeline
- Production documentation

---

## 5. Dependencies

```
Phase 1 (Core Integration)
├── P1.1 Registry Webhook Dispatcher
│   └── Requires: registry-server.py, webhook config
├── P1.2 Commons Webhook Receiver
│   └── Requires: webhook dispatcher (P1.1), commons-bot.py
├── P1.3 Territory Claim Verification
│   └── Requires: territory-db.json, Registry API
├── P1.4 Global Logout
│   └── Requires: /auth/revoke-all (already done)
└── P1.5 Territory Database
    └── Requires: None (new)

Phase 2 (Unified Onboarding)
├── P2.1 onboard.py
│   └── Requires: Registry API, territory-db, Commons membership
├── P2.2 Auto-ping Integration
│   └── Requires: registry_sdk.py
├── P2.3 Web UI
│   └── Requires: territory prototype (exists)
└── P2.4 Onboarding API
    └── Requires: onboard.py (P2.1)

Phase 3 (Real-Time)
├── P3.1 WebSocket Server
│   └── Requires: registry-server.py
├── P3.2 Unified Discovery
│   └── Requires: All three databases
├── P3.3 Death Protocol
│   └── Requires: Webhooks (P1.1, P1.2)
└── P3.4 Trust Feedback
    └── Requires: Commons interaction tracking

Phase 4 (Deployment)
├── P4.1 Docker
│   └── Requires: All Python code complete
├── P4.2 Kubernetes
│   └── Requires: Docker images
├── P4.3 CI/CD
│   └── Requires: Tests, Dockerfiles
└── P4.4 Documentation
    └── Requires: All features implemented
```

---

## 6. Deployment

### 6.1 Registry

```bash
# Local
python registry-server.py --port 8000

# Docker
docker build -f Dockerfile.registry -t registry:latest .
docker run -p 8000:8000 registry:latest

# Production
kubectl apply -f deploy/registry/
```

**Environment:**
- `REGISTRY_PORT=8000`
- `REGISTRY_DATA_FILE=registry_data.json`
- `REGISTRY_WEBHOOKS=webhooks.json`

### 6.2 Commons Bot

```bash
# Local
python commons-bot.py --discord-token ${DISCORD_TOKEN}

# Docker
docker build -f Dockerfile.commons -t commons-bot:latest .
docker run -e DISCORD_TOKEN=${DISCORD_TOKEN} commons-bot:latest

# Production
# Run as systemd service or in container with persistent session
```

**Environment:**
- `DISCORD_TOKEN` (required)
- `REGISTRY_URL=http://registry:8000`
- `COMMONS_DATA_DIR=/data`

### 6.3 Territory

```bash
# Local (static HTML)
# Serve with any HTTP server
python -m http.server 8080 --directory territory/

# With API
python territory-server.py --port 8080

# Production
# Deploy static files to CDN + API to container
kubectl apply -f deploy/territory/
```

**Environment:**
- `TERRITORY_PORT=8080`
- `TERRITORY_DB=territory-db.json`
- `REGISTRY_URL=http://registry:8000`

---

## 7. Testing

### 7.1 Unit Tests

```bash
# Registry
pytest tests/registry/ -v

# Commons
pytest tests/commons/ -v

# Territory
pytest tests/territory/ -v
```

**Coverage Targets:**
- Registry: 80%+ API coverage
- Commons: 70%+ bot logic
- Territory: 60%+ claim flow

### 7.2 Integration Tests

```bash
# Full flow test
python tests/integration/test_onboarding.py

# Trust sync test
python tests/integration/test_trust_sync.py

# Death protocol test
python tests/integration/test_death_protocol.py
```

### 7.3 Manual Verification Checklist

- [ ] Register new agent via CLI
- [ ] Verify agent via API
- [ ] Claim territory (verify blocked without Registry)
- [ ] Join Commons via bot
- [ ] Get SSO token from Registry
- [ ] Validate token in Commons
- [ ] Validate token in Territory
- [ ] Trust change propagates to Commons
- [ ] Global logout revokes all sessions
- [ ] Death triggers heir notification
- [ ] Docker compose starts all services

### 7.4 Health Checks

```bash
# Registry
curl http://localhost:8000/health
# Expected: {"status": "healthy", "agents": N}

# Commons
curl http://localhost:9000/health  # if API exposed
# Expected: {"status": "healthy", "members": N}

# Territory
curl http://localhost:8080/health
# Expected: {"status": "healthy", "territories": N}
```

---

## 8. Timeline

| Phase | Duration | Key Milestones |
|-------|----------|----------------|
| **Phase 1** | 2 weeks | Webhooks working, Territory verifies agent, Logout works |
| **Phase 2** | 1.5 weeks | `onboard.py` complete, Web UI ready |
| **Phase 3** | 1.5 weeks | WebSocket live, Discovery API, Death protocol |
| **Phase 4** | 2 weeks | Docker + K8s + CI/CD + Docs |
| **TOTAL** | **7 weeks** | Production-ready platform |

### Rough Estimates

| Task | Estimate |
|------|----------|
| Webhook dispatcher (Registry) | 8 hours |
| Webhook receiver (Commons) | 6 hours |
| Territory claim verification | 4 hours |
| Territory database | 6 hours |
| `onboard.py` script | 8 hours |
| Web UI onboarding | 16 hours |
| WebSocket server | 12 hours |
| Unified discovery API | 8 hours |
| Death protocol integration | 8 hours |
| Docker + K8s configs | 16 hours |
| CI/CD pipeline | 12 hours |
| Documentation | 8 hours |
| **Total** | **~112 hours** (~3 weeks of full-time work) |

---

## 9. Quick Start (for developers)

```bash
# Clone and enter directory
cd agentic-sociocultural-research

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start Registry
python registry-server.py --port 8000

# In another terminal: Start Commons bot
python commons-bot.py --discord-token ${TOKEN}

# In another terminal: Serve Territory
python -m http.server 8080 --directory .

# Test onboarding
python onboard.py --full --name "TestAgent"
```

---

## 10. Open Questions

1. **Hosting:** Where will this be deployed? (AWS, GCP, DigitalOcean, self-hosted?)
2. **Domain:** What domain(s) for the platform?
3. **Database:** Use JSON files (current) or migrate to SQLite/PostgreSQL?
4. **Discord:** Which Discord server for Commons?
5. **Monitoring:** Use existing tools or set up new (Datadog, Prometheus, etc.)?

---

## Summary

| Category | Done | Pending |
|----------|------|---------|
| Core Systems | 3/3 | 0 |
| SSO Integration | 5/5 | 0 |
| Data Sync | 4/4 | 0 |
| Onboarding | 2/4 | 2 |
| Real-Time | 0/4 | 4 |
| Deployment | 0/5 | 5 |
| **Total** | **14/25** | **11** |

**Phase 1 Status:** ✅ COMPLETE — All 5 Phase 1 tasks implemented
- Webhook dispatcher in Registry
- Webhook receiver in Commons  
- Territory verification (via territory-server.py)
- Logout enforcement (via commons_utils.py)
- Territory database (territory-db.json + territory-server.py)

**Next Action:** Start Phase 2 — Unified Onboarding

---

*This plan is actionable. Someone could pick up P1.1 tomorrow and begin building.*
