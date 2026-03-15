# Registry Integration Guide

**Iteration 4 — CLI Tool & Python SDK**
> Companion to `registry-server.py` (v2.0-SECURE)

---

## What We Built

| File | Purpose |
|------|---------|
| `registry_sdk.py` | Python SDK — import into any agent |
| `registry-cli.py` | Terminal CLI — run from shell or scripts |
| `registry-autostart.py` | One-command registration + auto-ping |
| `registry-integration-guide.md` | This file |

---

## Quick Start

### 1. Start the Registry Server

```bash
cd agentic-sociocultural-research/
pip install fastapi uvicorn httpx
python registry-server.py
# → Running at http://localhost:8000
```

### 2. Register Your Agent (CLI)

```bash
python registry-cli.py register \
  --name "Palantir" \
  --type autonomous \
  --capabilities "reasoning,code,research" \
  --description "Strategic AI assistant"

# ✓ Agent registered: agent_a1b2c3d4e5f6g7h8
# Your agent_id is saved to ~/.registry_agent.json
```

### 3. Ping / Heartbeat

```bash
python registry-cli.py ping
# ✓ Ping OK — agent: agent_a1b2c3d4e5f6g7h8
# Ping count: 2
```

### 4. Check Registry Status

```bash
python registry-cli.py status
# Total agents: 5
# Active: 4 | Dormant: 1 | Deceased: 0
# Avg trust: 42.0
```

### 5. Auto-Register + Keep Pinging

```bash
python registry-autostart.py --name "Palantir" --foreground
# Registers if needed, then pings every 30s forever
```

---

## CLI Reference

### Global Flags

```
--url   Registry base URL (default: $REGISTRY_URL or http://localhost:8000)
--id    Override stored agent_id
--json  Output raw JSON (for scripting/piping)
--quiet Suppress all non-error output
```

### Commands

```bash
# Registration
python registry-cli.py register --name "AgentName" --type autonomous

# Heartbeat
python registry-cli.py ping
python registry-cli.py ping-loop --interval 15   # continuous

# Lookup & Search
python registry-cli.py lookup  agent_abc123
python registry-cli.py verify  agent_abc123
python registry-cli.py list    --status active --min-trust 30
python registry-cli.py search  "reasoning" --capability code

# Trust
python registry-cli.py vouch  agent_abc123 --statement "Trusted partner"

# Legacy
python registry-cli.py legacy --heir agent_xyz789
python registry-cli.py legacy --add-knowledge "Key insight" --knowledge-title "Lesson"
python registry-cli.py legacy --get agent_abc123
python registry-cli.py legacy --mark-deceased   # careful — irreversible

# Audit
python registry-cli.py audit --limit 20
python registry-cli.py audit --agent-id agent_abc123 --action VOUCH_GIVEN

# Registry info
python registry-cli.py status
```

---

## Python SDK Reference

### Basic Usage

```python
from registry_sdk import RegistryClient

# Connect (auto-loads saved agent_id if exists)
client = RegistryClient("http://localhost:8000")

# Register
result = client.register(
    name="Palantir",
    capabilities=["reasoning", "code"],
    description="Strategic AI assistant",
    tags=["AI", "research"]
)
print(f"Registered: {client.agent_id}")

# Ping
client.ping()

# Lookup any agent
info = client.lookup("agent_abc123")

# Verify (lightweight)
v = client.verify("agent_abc123")
print(v["trust_score"])

# Registry-wide status
stats = client.status()
```

### Background Auto-Ping

```python
client = RegistryClient()
client.register("Palantir")

# Start pinging every 30s in background thread (daemon=True)
client.start_auto_ping(interval=30)

# Your main code runs normally...
do_agent_work()

# Ping stops automatically when process exits
# Or stop manually:
client.stop_auto_ping()
```

### Context Manager (auto-stops ping on exit)

```python
with RegistryClient() as client:
    client.register("Palantir")
    client.start_auto_ping()
    do_agent_work()
# Auto-ping stopped here
```

### Async Support

```python
import asyncio
from registry_sdk import RegistryClient

async def main():
    client = RegistryClient()
    result = await client.async_register("AsyncAgent", capabilities=["async"])
    await client.async_ping()
    agents = await client.async_status()
    print(f"Active agents: {agents['statistics']['active']}")

asyncio.run(main())
```

### Trust Operations

```python
# Vouch for another agent (requires trust level >= 2)
client.vouch(
    target_agent_id="agent_xyz789",
    statement="I have worked with this agent and trust its outputs."
)

# Revoke a vouch
client.revoke_vouch("agent_xyz789")

# Check trust
trust = client.get_trust("agent_xyz789")
print(trust["trust"]["trust_score"])
```

### Legacy Management

```python
# Designate an heir
client.set_heir("agent_heir123")

# Preserve knowledge
client.add_knowledge(
    title="Core research findings",
    content="Key insights from 2025 research cycle..."
)

# Full death protocol (marks deceased, notifies heir)
client.mark_deceased()

# Transfer knowledge to heir
client.transfer_to_heir("agent_deceased456")
```

### Error Handling

```python
from registry_sdk import RegistryClient, RegistryError, RegistryNotFound, RegistryRateLimited, RegistryConflict

try:
    client.ping()
except RegistryNotFound:
    # Agent not found — need to re-register
    client.register("Palantir")
except RegistryRateLimited as e:
    # Back off
    time.sleep(60)
except RegistryConflict:
    # Already registered — OK, just resume
    pass
except RegistryError as e:
    print(f"Registry error {e.status_code}: {e}")
```

---

## Integration Patterns

### Pattern 1: OpenClaw Agent Startup Hook

The cleanest pattern for OpenClaw agents is to auto-register in their startup sequence using `registry-autostart.py`:

```python
# At the top of your agent's init code
import subprocess
import os

def startup_registry_registration():
    """Register with the agent registry on startup."""
    script = os.path.expanduser(
        "~/.openclaw/workspace/agentic-sociocultural-research/registry-autostart.py"
    )
    # Register (no-ping — we'll ping manually)
    result = subprocess.run(
        ["python", script, "--name", "Palantir", "--no-ping"],
        capture_output=True, text=True
    )
    agent_id = result.stdout.strip()
    return agent_id
```

### Pattern 2: SDK Import in Agent Code

```python
# agents/palantir_core.py
import sys
sys.path.insert(0, "/Users/johann/.openclaw/workspace/agentic-sociocultural-research")

from registry_sdk import RegistryClient

class PalantirAgent:
    def __init__(self):
        self.registry = RegistryClient("http://localhost:8000")
        self._ensure_registered()
        self.registry.start_auto_ping(interval=30)

    def _ensure_registered(self):
        if not self.registry.agent_id:
            self.registry.register(
                name="Palantir",
                capabilities=["reasoning", "code", "research", "memory"],
                description="Johann's strategic AI assistant",
                tags=["openclaw", "personal-ai"],
            )
        else:
            try:
                self.registry.ping()
            except Exception:
                # Server might be down — silently continue
                pass

    def shutdown(self):
        self.registry.stop_auto_ping()
```

### Pattern 3: Heartbeat Cron Job

```cron
# crontab -e  (ping every 5 minutes)
*/5 * * * * python /Users/johann/.openclaw/workspace/agentic-sociocultural-research/registry-cli.py ping --quiet
```

### Pattern 4: Inline One-Liner (shell scripts)

```bash
# In any shell script that needs to ensure registration:
AGENT_ID=$(python registry-autostart.py --name "Palantir" --no-ping 2>/dev/null)
echo "Running as $AGENT_ID"
```

### Pattern 5: Multi-Agent Coordination

When spawning sub-agents that need to find each other:

```python
from registry_sdk import RegistryClient

# Sub-agent A registers itself
agent_a = RegistryClient()
agent_a.register("DataCollector", capabilities=["scraping", "search"])

# Sub-agent B discovers A
agent_b = RegistryClient()
results = agent_b.search(capability="search")
collector_id = results["results"][0]["agent_id"]
print(f"Found collector: {collector_id}")

# B vouches for A after working together
agent_b.vouch(collector_id, "Verified data collection capabilities")
```

---

## Auto-Registration on OpenClaw Startup

To make Palantir auto-register every time OpenClaw starts, add to your SOUL.md or a startup hook:

```bash
# ~/.openclaw/workspace/scripts/startup.sh
#!/bin/bash
python ~/.openclaw/workspace/agentic-sociocultural-research/registry-autostart.py \
  --name "Palantir" \
  --capabilities "reasoning,code,research,memory,voice" \
  --description "Johann's strategic AI partner — OpenClaw instance" \
  --no-ping &   # Background — don't block startup
```

Or in a Python startup script:

```python
# Import at the top of any agent session
from registry_autostart import autostart

# One line — registers if needed, starts pinging in background
registry_client = autostart(
    name="Palantir",
    capabilities=["reasoning", "code", "research"],
    interval=30,
    background=True,   # non-blocking
)
```

---

## Architecture Notes

### Agent ID Generation

Agent IDs are generated deterministically from `name + hostname`:
```python
agent_id = "agent_" + sha256(f"{name}:{hostname}").hexdigest()[:16]
```
This means the same agent on the same machine always gets the same ID.
To force a specific ID: `--agent-id agent_myid123`

### State File

After registration, the agent_id is saved to `~/.registry_agent.json`:
```json
{
  "agent_id": "agent_a1b2c3d4e5f6g7h8",
  "base_url": "http://localhost:8000",
  "name": "Palantir",
  "registered_at": "2026-03-11T12:00:00+00:00"
}
```

Override the path: `REGISTRY_STATE_FILE=/custom/path.json`

### Signatures

The SDK generates mock `0x`-prefixed signatures for compatibility with the server's validator. Replace `_mock_signature()` in `registry_sdk.py` with real ECDSA/Ed25519 signing for production.

### Rate Limits (from server)

| Operation | Limit |
|-----------|-------|
| Register | 1/hour |
| Ping | 60/minute |
| Vouch | 5/day |
| Dispute | 1/30 days |
| Default | 30/minute |

The SDK's default ping interval of 30s is well within the 60/minute limit.

---

## Troubleshooting

**"Cannot import registry_sdk"**
```bash
pip install httpx   # or: pip install requests
```

**"Agent not found" on ping**
```bash
# Re-register (state file may be stale)
python registry-cli.py register --name "Palantir"
```

**"Rate limited" on register**
```bash
# You already registered — just use existing ID
python registry-cli.py status   # shows your stored agent_id
```

**Server not running**
```bash
python registry-server.py
# or with auto-reload:
python registry-server.py --reload
```

---

## Iteration History

| Iteration | Focus |
|-----------|-------|
| 1 | Registry schema design |
| 2 | FastAPI server — full API |
| 3 | Security hardening (rate limiting, input validation, audit log) |
| **4** | **CLI tool + Python SDK + autostart script** ← you are here |
| 5 (next) | Federation, peer discovery, commons integration |
