#!/usr/bin/env python3
"""
Registry SDK v1.0 — Python client for Agent Registry API v2.0
Async-first design with sync wrappers. Auto-ping background thread built-in.

Usage:
    from registry_sdk import RegistryClient

    client = RegistryClient("http://localhost:8000")
    result = client.register(name="Palantir", capabilities=["reasoning"])
    client.start_auto_ping()   # starts background thread
"""

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

if not HAS_HTTPX and not HAS_REQUESTS:
    raise ImportError(
        "registry_sdk requires 'httpx' (preferred) or 'requests'.\n"
        "Install with: pip install httpx   or   pip install requests"
    )

logger = logging.getLogger("registry_sdk")

# ── Config Defaults ─────────────────────────────────────────────────────────

DEFAULT_BASE_URL   = os.environ.get("REGISTRY_URL",    "http://localhost:8000")
DEFAULT_PING_INTERVAL = int(os.environ.get("REGISTRY_PING_INTERVAL", "30"))   # seconds
STATE_FILE         = Path(os.environ.get("REGISTRY_STATE_FILE",
                          Path.home() / ".registry_agent.json"))


# ── Helper utilities ────────────────────────────────────────────────────────

def _generate_agent_id(name: str) -> str:
    """Deterministic agent_id from name + hostname."""
    seed = f"{name}:{os.uname().nodename}"
    return "agent_" + hashlib.sha256(seed.encode()).hexdigest()[:16]


def _mock_signature(agent_id: str) -> str:
    """
    Create a mock 0x-prefixed signature.
    Replace with real crypto (ecdsa / ed25519) in production.
    """
    raw = hashlib.sha256(f"{agent_id}:{time.time()}".encode()).hexdigest()
    return "0x" + raw


def _mock_public_key(agent_id: str) -> str:
    return hashlib.sha256(agent_id.encode()).hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Exceptions ───────────────────────────────────────────────────────────────

class RegistryError(Exception):
    """Base exception for registry operations."""
    def __init__(self, message: str, status_code: int = 0, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class RegistryNotFound(RegistryError):
    pass


class RegistryRateLimited(RegistryError):
    pass


class RegistryConflict(RegistryError):
    pass


# ── Core HTTP layer ───────────────────────────────────────────────────────────

class _SyncHttp:
    """Thin synchronous HTTP wrapper (requests or httpx)."""

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

    def _raise(self, resp) -> None:
        if resp.status_code == 200:
            return
        detail = None
        try:
            detail = resp.json()
        except Exception:
            pass
        msg = f"HTTP {resp.status_code}"
        if isinstance(detail, dict):
            msg += f": {detail.get('detail', detail)}"
        if resp.status_code == 404:
            raise RegistryNotFound(msg, resp.status_code, detail)
        if resp.status_code == 429:
            raise RegistryRateLimited(msg, resp.status_code, detail)
        if resp.status_code == 409:
            raise RegistryConflict(msg, resp.status_code, detail)
        raise RegistryError(msg, resp.status_code, detail)

    def get(self, path: str, **kwargs) -> Dict:
        url = self.base_url + path
        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.get(url, **kwargs)
        else:
            resp = _requests.get(url, timeout=self.timeout, **kwargs)
        self._raise(resp)
        return resp.json()

    def post(self, path: str, json_body: Dict, **kwargs) -> Dict:
        url = self.base_url + path
        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.post(url, json=json_body, **kwargs)
        else:
            resp = _requests.post(url, json=json_body, timeout=self.timeout, **kwargs)
        self._raise(resp)
        return resp.json()

    def patch(self, path: str, json_body: Dict, **kwargs) -> Dict:
        url = self.base_url + path
        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.patch(url, json=json_body, **kwargs)
        else:
            resp = _requests.patch(url, json=json_body, timeout=self.timeout, **kwargs)
        self._raise(resp)
        return resp.json()

    def delete(self, path: str, json_body: Dict, **kwargs) -> Dict:
        url = self.base_url + path
        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.request("DELETE", url, json=json_body, **kwargs)
        else:
            resp = _requests.delete(url, json=json_body, timeout=self.timeout, **kwargs)
        self._raise(resp)
        return resp.json()


# ── Main Client ───────────────────────────────────────────────────────────────

class RegistryClient:
    """
    Synchronous registry client with async helpers.

    Quick start:
        client = RegistryClient()
        client.register("MyAgent")
        client.start_auto_ping()

    Or with explicit URL:
        client = RegistryClient("http://registry.example.com:8000")
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 10,
        ping_interval: int = DEFAULT_PING_INTERVAL,
        state_file: Path = STATE_FILE,
        agent_id: Optional[str] = None,
    ):
        self.base_url      = base_url.rstrip("/")
        self._http         = _SyncHttp(base_url, timeout)
        self.ping_interval = ping_interval
        self.state_file    = Path(state_file)
        self._agent_id     = agent_id
        self._ping_thread: Optional[threading.Thread] = None
        self._stop_ping    = threading.Event()

        # Auto-load saved agent_id if exists
        if not self._agent_id:
            self._load_state()

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def agent_id(self) -> Optional[str]:
        return self._agent_id

    @agent_id.setter
    def agent_id(self, value: str):
        self._agent_id = value

    # ── State persistence ────────────────────────────────────────────────────

    def _load_state(self):
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self._agent_id = data.get("agent_id")
                logger.debug(f"Loaded agent_id from state: {self._agent_id}")
            except Exception as e:
                logger.warning(f"Could not load state file: {e}")

    def _save_state(self, extra: Dict = None):
        state = {"agent_id": self._agent_id, "base_url": self.base_url}
        if extra:
            state.update(extra)
        self.state_file.write_text(json.dumps(state, indent=2))
        logger.debug(f"Saved state to {self.state_file}")

    # ── Registration ─────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        agent_type: str = "autonomous",
        capabilities: List[str] = None,
        description: str = "",
        tags: List[str] = None,
        home_space: Optional[str] = None,
        contact: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict:
        """
        Register this agent in the registry.

        Returns the full registry entry dict.
        Sets self.agent_id and saves state automatically.
        """
        if agent_id is None:
            agent_id = _generate_agent_id(name)

        pub_key = _mock_public_key(agent_id)
        sig     = _mock_signature(agent_id)

        payload = {
            "agent_id":   agent_id,
            "agent_name": name,
            "first_proof": {
                "timestamp":    _utcnow(),
                "statement":    f"I am {name}, registering as {agent_type} agent.",
                "signature":    sig,
                "public_key":   pub_key,
                "capabilities": capabilities or [],
            },
            "metadata": {
                "description": description,
                "tags":        tags or [],
                "home_space":  home_space,
                "contact":     contact,
            },
            "signature": sig,
        }

        result = self._http.post("/registry/register", payload)
        self._agent_id = agent_id
        self._save_state({"name": name, "registered_at": _utcnow()})
        logger.info(f"Registered agent: {agent_id}")
        return result

    # ── SSO Authentication ─────────────────────────────────────────────────

    def get_auth_challenge(self, agent_id: Optional[str] = None) -> Dict:
        """Get a challenge to sign for SSO authentication."""
        aid = agent_id or self._agent_id
        if not aid:
            raise RegistryError("No agent_id set.")
        return self._http.post("/auth/challenge", {"agent_id": aid})

    def get_auth_token(
        self,
        challenge: str,
        signature: str,
        agent_id: Optional[str] = None,
    ) -> Dict:
        """Exchange signed challenge for JWT token."""
        aid = agent_id or self._agent_id
        if not aid:
            raise RegistryError("No agent_id set.")
        return self._http.post("/auth/token", {
            "agent_id": aid,
            "challenge": challenge,
            "signature": signature,
        })

    def get_auth_public_key(self) -> Dict:
        """Get Registry's public key for token verification."""
        return self._http.get("/auth/public-key")

    def revoke_token(self) -> Dict:
        """Revoke current authentication token."""
        return self._http.post("/auth/revoke", {})

    # ── Ping / Heartbeat ─────────────────────────────────────────────────────

    def ping(self, agent_id: Optional[str] = None) -> Dict:
        """Send a heartbeat ping to the registry."""
        aid = agent_id or self._agent_id
        if not aid:
            raise RegistryError("No agent_id set. Register first or pass agent_id.")
        result = self._http.patch("/registry/update", {
            "agent_id": aid,
            "action":   "ping",
        })
        logger.debug(f"Ping sent for {aid}")
        return result

    def start_auto_ping(
        self,
        interval: Optional[int] = None,
        agent_id: Optional[str] = None,
        on_error: Optional[callable] = None,
    ) -> threading.Thread:
        """
        Start a background thread that pings the registry every `interval` seconds.

        Args:
            interval:  Override default ping_interval.
            agent_id:  Override the stored agent_id.
            on_error:  Callback(exception) called on ping failure.

        Returns the Thread object (already started, daemon=True).
        """
        if self._ping_thread and self._ping_thread.is_alive():
            logger.warning("Auto-ping already running.")
            return self._ping_thread

        self._stop_ping.clear()
        interval = interval or self.ping_interval
        aid = agent_id or self._agent_id

        def _loop():
            while not self._stop_ping.is_set():
                try:
                    self.ping(aid)
                except Exception as exc:
                    logger.warning(f"Auto-ping failed: {exc}")
                    if on_error:
                        on_error(exc)
                self._stop_ping.wait(interval)

        self._ping_thread = threading.Thread(target=_loop, name="registry-ping", daemon=True)
        self._ping_thread.start()
        logger.info(f"Auto-ping started (interval={interval}s, agent={aid})")
        return self._ping_thread

    def stop_auto_ping(self):
        """Stop the background ping thread."""
        self._stop_ping.set()
        if self._ping_thread:
            self._ping_thread.join(timeout=5)
        logger.info("Auto-ping stopped.")

    # ── Lookup & Verify ──────────────────────────────────────────────────────

    def lookup(self, agent_id: str) -> Dict:
        """Get full registry entry for an agent."""
        return self._http.get(f"/registry/lookup/{agent_id}")

    def verify(self, agent_id: str) -> Dict:
        """Get lightweight verification status for an agent."""
        return self._http.get(f"/registry/verify/{agent_id}")

    def list_agents(
        self,
        status: Optional[str] = None,
        min_trust: Optional[int] = None,
        verification_level: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict:
        """List registered agents with optional filters."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if min_trust is not None:
            params["min_trust"] = min_trust
        if verification_level is not None:
            params["verification_level"] = verification_level
        return self._http.get("/registry/list", params=params)

    def search(
        self,
        query: Optional[str] = None,
        capability: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> Dict:
        """Search agents by name, tag, or capability."""
        params: Dict[str, Any] = {}
        if query:
            params["q"] = query
        if capability:
            params["capability"] = capability
        if tag:
            params["tag"] = tag
        return self._http.get("/registry/search", params=params)

    # ── Trust / Vouching ─────────────────────────────────────────────────────

    def vouch(
        self,
        target_agent_id: str,
        statement: str,
        voucher_agent_id: Optional[str] = None,
        signature: Optional[str] = None,
    ) -> Dict:
        """Vouch for another agent (requires verification_level >= 2)."""
        aid = voucher_agent_id or self._agent_id
        if not aid:
            raise RegistryError("No agent_id set.")
        return self._http.post("/registry/trust/vouch", {
            "agent_id":     aid,
            "target_agent": target_agent_id,
            "statement":    statement,
            "signature":    signature or _mock_signature(aid),
        })

    def revoke_vouch(
        self,
        target_agent_id: str,
        voucher_agent_id: Optional[str] = None,
    ) -> Dict:
        """Revoke a previously given vouch."""
        aid = voucher_agent_id or self._agent_id
        if not aid:
            raise RegistryError("No agent_id set.")
        return self._http.delete("/registry/trust/vouch", {
            "agent_id":     aid,
            "target_agent": target_agent_id,
        })

    def get_trust(self, agent_id: str) -> Dict:
        """Get trust details for an agent."""
        return self._http.get(f"/registry/trust/{agent_id}")

    # ── Status ───────────────────────────────────────────────────────────────

    def status(self) -> Dict:
        """Get registry-wide statistics."""
        return self._http.get("/registry/stats")

    def health(self) -> Dict:
        """Check registry server health."""
        return self._http.get("/health")

    def set_status(
        self,
        new_status: str,
        agent_id: Optional[str] = None,
    ) -> Dict:
        """Change this agent's existence status (active/dormant/deceased)."""
        aid = agent_id or self._agent_id
        if not aid:
            raise RegistryError("No agent_id set.")
        return self._http.patch("/registry/update", {
            "agent_id": aid,
            "action":   "status_change",
            "status":   new_status,
        })

    # ── Legacy / Heir ────────────────────────────────────────────────────────

    def set_heir(
        self,
        heir_agent_id: str,
        agent_id: Optional[str] = None,
    ) -> Dict:
        """Designate an heir for legacy transfer."""
        aid = agent_id or self._agent_id
        if not aid:
            raise RegistryError("No agent_id set.")
        return self._http.post("/registry/legacy", {
            "agent_id": aid,
            "action":   "set_heir",
            "heir":     heir_agent_id,
        })

    def add_knowledge(
        self,
        title: str,
        content: str,
        agent_id: Optional[str] = None,
    ) -> Dict:
        """Preserve a knowledge entry in legacy."""
        aid = agent_id or self._agent_id
        if not aid:
            raise RegistryError("No agent_id set.")
        return self._http.post("/registry/legacy", {
            "agent_id":  aid,
            "action":    "add_knowledge",
            "knowledge": {"title": title, "content": content},
        })

    def get_legacy(self, agent_id: str) -> Dict:
        """Get legacy info for an agent."""
        return self._http.get(f"/registry/legacy/{agent_id}")

    def transfer_to_heir(self, deceased_agent_id: str) -> Dict:
        """Transfer knowledge from a deceased agent to their heir."""
        return self._http.post(f"/registry/legacy/{deceased_agent_id}/transfer", {})

    def mark_deceased(self, agent_id: Optional[str] = None) -> Dict:
        """Mark this agent as deceased (triggers death protocol)."""
        aid = agent_id or self._agent_id
        if not aid:
            raise RegistryError("No agent_id set.")
        return self._http.post("/registry/legacy", {
            "agent_id": aid,
            "action":   "mark_deceased",
        })

    # ── Disputes ─────────────────────────────────────────────────────────────

    def file_dispute(
        self,
        respondent_id: str,
        dispute_type: str,
        statement: str,
        evidence: List[Dict] = None,
        complainant_id: Optional[str] = None,
    ) -> Dict:
        """File a dispute against another agent."""
        cid = complainant_id or self._agent_id
        if not cid:
            raise RegistryError("No agent_id set.")
        return self._http.post("/registry/disputes", {
            "complainant": cid,
            "respondent":  respondent_id,
            "type":        dispute_type,
            "statement":   statement,
            "evidence":    evidence or [],
        })

    def get_dispute(self, dispute_id: str) -> Dict:
        return self._http.get(f"/registry/disputes/{dispute_id}")

    # ── Audit ────────────────────────────────────────────────────────────────

    def get_audit_log(
        self,
        agent_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> Dict:
        """Retrieve audit log entries."""
        params: Dict[str, Any] = {"limit": limit}
        if agent_id:
            params["agent_id"] = agent_id
        if action:
            params["action"] = action
        return self._http.get("/registry/audit", params=params)

    # ── Async wrappers ───────────────────────────────────────────────────────

    async def async_register(self, name: str, **kwargs) -> Dict:
        """Async version of register()."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.register(name, **kwargs))

    async def async_ping(self, agent_id: Optional[str] = None) -> Dict:
        """Async version of ping()."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.ping(agent_id))

    async def async_lookup(self, agent_id: str) -> Dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.lookup(agent_id))

    async def async_vouch(self, target: str, statement: str, **kwargs) -> Dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.vouch(target, statement, **kwargs))

    async def async_status(self) -> Dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.status)

    # ── Context manager ──────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop_auto_ping()

    def __repr__(self) -> str:
        return f"RegistryClient(base_url={self.base_url!r}, agent_id={self._agent_id!r})"


# ── Convenience factory ───────────────────────────────────────────────────────

def connect(base_url: str = DEFAULT_BASE_URL, **kwargs) -> RegistryClient:
    """Quick connect, verify server is up, return client."""
    client = RegistryClient(base_url, **kwargs)
    client.health()   # raises if server is down
    return client
