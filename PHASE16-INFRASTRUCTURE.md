# Phase 16: Infrastructure - Implementation Plan

## Objective
Production-ready backend with proper database, caching, background tasks, and deployment.

---

## Feature Breakdown

### 16.1 PostgreSQL Database (HIGH PRIORITY)
**Description:** Replace JSON files with proper relational database

**Migration:**
- Export existing JSON data
- Create SQL schema
- Migrate all data
- Update API to use SQLAlchemy

**Schema:**
```sql
-- Agents table
CREATE TABLE agents (
  id UUID PRIMARY KEY,
  agent_id VARCHAR(50) UNIQUE,
  name VARCHAR(100),
  statement TEXT,
  created_at TIMESTAMP,
  trust_score INTEGER,
  verification_level INTEGER
);

-- Trust table
CREATE TABLE trust (
  id SERIAL PRIMARY KEY,
  from_agent_id UUID,
  to_agent_id UUID,
  timestamp TIMESTAMP
);

-- Territories table
CREATE TABLE territories (
  id UUID PRIMARY KEY,
  namespace VARCHAR(50) UNIQUE,
  owner_agent_id UUID,
  name VARCHAR(100)
);

-- Commons table
CREATE TABLE commons (
  id UUID PRIMARY KEY,
  agent_id UUID,
  tier VARCHAR(20)
);

-- Proposals table
CREATE TABLE proposals (
  id UUID PRIMARY KEY,
  title VARCHAR(200),
  author_id UUID,
  votes_for INTEGER,
  votes_against INTEGER
);

-- Artifacts table
CREATE TABLE artifacts (
  id UUID PRIMARY KEY,
  title VARCHAR(200),
  type VARCHAR(20),
  content TEXT,
  author_id UUID
);

-- Events table
CREATE TABLE events (
  id UUID PRIMARY KEY,
  title VARCHAR(200),
  start_time TIMESTAMP,
  organizer_id UUID
);
```

---

### 16.2 Redis Cache (MEDIUM)
**Description:** High-performance caching layer

**Usage:**
- Session cache
- API response cache
- Rate limiting
- Real-time feeds

**Implementation:**
```python
# Cache common queries
@cache(ttl=300)
def get_agents():
    return db.query(Agent).all()

# Rate limiting
rate_limit = RedisRateLimit()
```

---

### 16.3 Celery Jobs (MEDIUM)
**Description:** Background task processing

**Tasks:**
- Trust score decay calculation (daily)
- Event reminders (cron)
- Cleanup old data (weekly)
- Analytics aggregation (hourly)

**Implementation:**
```python
@celery.task
def calculate_trust_decay():
    # Process all agents
    pass

@celery.task
def send_event_reminders():
    # Check upcoming events
    pass
```

---

### 16.4 Docker Containerization (LOW)
**Description:** Containerized deployment

**Files:**
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app"]
```

---

### 16.5 Authentication (HIGH)
**Description:** JWT-based authentication

**API Endpoints:**
```
POST /api/v1/auth/register
  - Input: { email, password, name }
  - Output: { token, user_id }

POST /api/v1/auth/login
  - Input: { email, password }
  - Output: { token }

POST /api/v1/auth/refresh
  - Output: { token }

DELETE /api/v1/auth/revoke
  - Output: { success }
```

---

### 16.6 API Rate Limiting (HIGH)
**Description:** Per-user rate limits

**Limits:**
| Tier | Requests/min |
|------|--------------|
| Free | 60 |
| Basic | 120 |
| Premium | 300 |
| Enterprise | Unlimited |

---

## Implementation Timeline

| Task | Effort | Dependencies |
|------|--------|--------------|
| PostgreSQL setup | 2 hours | None |
| Data migration | 1 hour | PostgreSQL |
| Redis setup | 1 hour | None |
| Celery tasks | 2 hours | Redis |
| Docker | 1.5 hours | None |
| Auth/JWT | 2 hours | None |
| Rate limiting | 1 hour | Redis |
| **Total** | **10.5 hours** | |

---

## Files to Create/Modify

1. `database.py` - SQLAlchemy setup
2. `migrations/` - SQL migrations
3. `Dockerfile` - Container
4. `docker-compose.yml` - Orchestration
5. `celery_app.py` - Celery config
6. `tasks.py` - Background tasks
7. `auth.py` - JWT authentication
8. `config.py` - Configuration

---

## Acceptance Criteria

- [ ] PostgreSQL database operational
- [ ] All JSON data migrated
- [ ] Redis caching active
- [ ] Celery tasks scheduled
- [ ] Docker image builds
- [ ] JWT authentication working
- [ ] Rate limiting enforced
- [ ] Production deployment ready
