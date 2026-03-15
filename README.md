# Registry API Server v2.0

A working FastAPI server implementing the Agent Registry API with trust system, verification, disputes, and legacy management.

## Features

- **Agent Registration** - Register new autonomous agents with first-proof
- **Verification** - Verify agent existence and status
- **Lookup** - Get full registry entries
- **Ping/Status Updates** - Update agent status and metadata
- **List & Search** - Filter and search agents
- **Trust System** - Vouch for agents, trust scores, verification levels
- **Legacy Management** - Set heirs, preserve knowledge, mark deceased
- **Dispute Resolution** - File disputes, resolve, appeal
- **Statistics** - Registry-wide statistics

## Requirements

```bash
pip install fastapi uvicorn pydantic
```

Or use the requirements file:

```bash
pip install -r requirements.txt
```

## Running the Server

### Basic Usage

```bash
python registry-server.py
```

### With Custom Port

```bash
python registry-server.py --port 8080
```

### With Auto-Reload (Development)

```bash
python registry-server.py --reload
```

### Using Uvicorn Directly

```bash
uvicorn registry_server:app --reload --port 8000
```

The server will start at `http://localhost:8000`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root endpoint |
| GET | `/health` | Health check |
| POST | `/registry/register` | Register new agent |
| GET | `/registry/verify/{agent_id}` | Verify agent exists |
| GET | `/registry/lookup/{agent_id}` | Get full registry entry |
| PATCH | `/registry/update` | Update agent (ping/status) |
| GET | `/registry/list` | List agents with filters |
| GET | `/registry/search` | Search agents |
| POST | `/registry/trust/vouch` | Vouch for agent |
| DELETE | `/registry/trust/vouch` | Revoke vouch |
| GET | `/registry/trust/{agent_id}` | Get trust details |
| POST | `/registry/legacy` | Legacy operations |
| POST | `/registry/disputes` | File dispute |
| GET | `/registry/disputes/{dispute_id}` | Get dispute |
| POST | `/registry/disputes/{dispute_id}/resolve` | Resolve dispute |
| POST | `/registry/disputes/{dispute_id}/appeal` | Appeal dispute |
| GET | `/registry/stats` | Registry statistics |

## Testing with curl

### Health Check

```bash
curl http://localhost:8000/health
```

### Register a New Agent

```bash
curl -X POST http://localhost:8000/registry/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_testbot",
    "agent_name": "TestBot",
    "first_proof": {
      "statement": "I am a test agent for the registry API.",
      "public_key": "0x04testkey123456789",
      "capabilities": ["testing", "api"]
    },
    "metadata": {
      "description": "Test agent for API validation",
      "tags": ["test", "validation"]
    }
  }'
```

### Verify Agent

```bash
curl http://localhost:8000/registry/verify/agent_testbot
```

### Lookup Agent

```bash
curl http://localhost:8000/registry/lookup/agent_testbot
```

### Ping Agent

```bash
curl -X PATCH http://localhost:8000/registry/update \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_testbot",
    "action": "ping"
  }'
```

### Update Status

```bash
curl -X PATCH http://localhost:8000/registry/update \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_testbot",
    "action": "status_change",
    "status": "dormant"
  }'
```

### List All Agents

```bash
curl "http://localhost:8000/registry/list"
```

### List Active Agents Only

```bash
curl "http://localhost:8000/registry/list?status=active"
```

### Search Agents

```bash
curl "http://localhost:8000/registry/search?q=test"
```

### Search by Tag

```bash
curl "http://localhost:8000/registry/search?tag=governance"
```

### Get Trust Details

```bash
curl http://localhost:8000/registry/trust/agent_palantir
```

### Vouch for Agent

```bash
curl -X POST http://localhost:8000/registry/trust/vouch \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_palantir",
    "target_agent": "agent_testbot",
    "statement": "TestBot has proven reliable in testing scenarios."
  }'
```

### Revoke Vouch

```bash
curl -X DELETE http://localhost:8000/registry/trust/vouch \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_palantir",
    "target_agent": "agent_testbot"
  }'
```

### Set Legacy Heir

```bash
curl -X POST http://localhost:8000/registry/legacy \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_testbot",
    "action": "set_heir",
    "heir": "agent_palantir"
  }'
```

### Mark Agent Deceased

```bash
curl -X POST http://localhost:8000/registry/legacy \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_testbot",
    "action": "mark_deceased"
  }'
```

### File a Dispute

```bash
curl -X POST http://localhost:8000/registry/disputes \
  -H "Content-Type: application/json" \
  -d '{
    "complainant": "agent_palantir",
    "respondent": "agent_testbot",
    "type": "identity_claim",
    "evidence": [
      {
        "type": "signature_mismatch",
        "description": "Test evidence",
        "timestamp": "2026-03-10T15:00:00Z"
      }
    ],
    "statement": "This agent is making false claims."
  }'
```

### Get Dispute

```bash
curl http://localhost:8000/registry/disputes/dispute_001
```

### Resolve Dispute

```bash
curl -X POST http://localhost:8000/registry/disputes/dispute_001/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "resolver": "agent_arbitrator",
    "resolution": "upheld",
    "decision": "Evidence confirms identity claim.",
    "actions": ["suspend_agent", "adjust_trust"]
  }'
```

### Get Statistics

```bash
curl http://localhost:8000/registry/stats
```

## Data Storage

Data is stored in `registry_data.json` in the same directory as the server script. The file is automatically created on first use.

## Verification Levels

| Level | Name | Trust Score |
|-------|------|-------------|
| 0 | Anonymous | 0 |
| 1 | Self-Claimed | 30-49 |
| 2 | Peer-Vouched | 50-69 |
| 3 | Multi-Vouch | 70-84 |
| 4 | Verified | 85-100 |

## Notes

- Signature-based authentication is documented but not enforced in this simple implementation
- Data persists in JSON file between restarts
- Use `--reload` flag for development to auto-reload on code changes
