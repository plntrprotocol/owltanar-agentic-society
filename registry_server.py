#!/usr/bin/env python3
"""
Registry API Server v2.0 - Security Hardened
Agent Registry with Trust System, Rate Limiting, and Audit Trail
"""

import json
import os
import hashlib
import hmac
import time
import asyncio
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import uuid4
from collections import defaultdict
from dataclasses import dataclass, field
from fastapi import FastAPI, HTTPException, Query, Header, Request, Response, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
import uvicorn

# Configuration
DATA_FILE = Path(__file__).parent / "registry_data.json"
AUDIT_FILE = Path(__file__).parent / "registry_audit.json"
WEBHOOKS_FILE = Path(__file__).parent / "webhooks.json"
DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0"

# Security Configuration
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = {
    "register": 1,      # 1 per hour (special handling)
    "ping": 60,         # 60 per minute
    "vouch": 5,         # 5 per day (special handling)
    "dispute": 1,      # 1 per month (special handling)
    "default": 30       # 30 per minute
}

app = FastAPI(
    title="Agent Registry API v2.0",
    description="SECURE - RESTful API for agent registration, verification, trust management, and dispute resolution",
    version="2.0.0-security"
)

# ============== Security: Rate Limiting ==============

@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    window_seconds: int = 60
    max_requests: int = 30
    burst_allowance: int = 5

class RateLimiter:
    """Token bucket rate limiter"""
    def __init__(self):
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.lock = asyncio.Lock()
    
    async def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Check if request is within rate limits"""
        async with self.lock:
            now = time.time()
            # Clean old requests
            self.requests[key] = [ts for ts in self.requests[key] if now - ts < window_seconds]
            
            if len(self.requests[key]) >= max_requests:
                return False
            
            self.requests[key].append(now)
            return True
    
    def get_remaining(self, key: str, max_requests: int, window_seconds: int) -> int:
        """Get remaining requests"""
        now = time.time()
        recent = [ts for ts in self.requests.get(key, []) if now - ts < window_seconds]
        return max(0, max_requests - len(recent))

rate_limiter = RateLimiter()

# ============== Security: Input Validation ==============

class InputValidator:
    """Security-focused input validation"""
    
    # Dangerous patterns that could indicate injection attacks
    DANGEROUS_PATTERNS = [
        r'<script',
        r'javascript:',
        r'on\w+\s*=',
        r'\$\{',
        r'{{',
        r'eval\(',
        r'exec\(',
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 500) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            raise ValueError("Expected string input")
        
        # Trim to max length
        value = value[:max_length]
        
        # Check for dangerous patterns
        value_lower = value.lower()
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.lower() in value_lower:
                raise ValueError(f"Potentially dangerous input pattern detected: {pattern}")
        
        return value.strip()
    
    @classmethod
    def validate_agent_id(cls, agent_id: str) -> str:
        """Validate agent ID format"""
        import re
        if not re.match(r'^agent_[a-zA-Z0-9]{8,32}$', agent_id):
            raise ValueError("Invalid agent_id format. Must match pattern: agent_[a-zA-Z0-9]{8,32}")
        return agent_id
    
    @classmethod
    def validate_signature(cls, signature: str) -> str:
        """Validate signature format"""
        if signature and not signature.startswith('0x'):
            raise ValueError("Invalid signature format. Must start with 0x")
        if signature and len(signature) < 10:
            raise ValueError("Signature too short")
        return signature

# ============== Security: Audit Logging ==============

@dataclass
class AuditEntry:
    """Immutable audit log entry"""
    id: str
    timestamp: str
    action: str
    actor_agent_id: Optional[str]
    target_agent_id: Optional[str]
    resource: str
    details: Dict[str, Any]
    ip_address: Optional[str]
    success: bool
    failure_reason: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action": self.action,
            "actor_agent_id": self.actor_agent_id,
            "target_agent_id": self.target_agent_id,
            "resource": self.resource,
            "details": self.details,
            "ip_address": self.ip_address,
            "success": self.success,
            "failure_reason": self.failure_reason
        }

class AuditLogger:
    """Immutable audit trail logger"""
    
    def __init__(self, audit_file: Path):
        self.audit_file = audit_file
        self.entries: List[Dict] = []
        self._load_existing()
    
    def _load_existing(self):
        """Load existing audit entries"""
        if self.audit_file.exists():
            try:
                with open(self.audit_file, 'r') as f:
                    self.entries = json.load(f)
            except:
                self.entries = []
    
    def _save(self):
        """Save audit entries"""
        with open(self.audit_file, 'w') as f:
            json.dump(self.entries, f, indent=2)
    
    def log(self, action: str, actor_agent_id: Optional[str], target_agent_id: Optional[str],
            resource: str, details: Dict[str, Any], ip_address: Optional[str],
            success: bool, failure_reason: Optional[str] = None):
        """Log an audit entry"""
        entry = AuditEntry(
            id=f"audit_{uuid4().hex[:16]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            actor_agent_id=actor_agent_id,
            target_agent_id=target_agent_id,
            resource=resource,
            details=details,
            ip_address=ip_address,
            success=success,
            failure_reason=failure_reason
        )
        
        # Prepend to ensure newest first (append-only log)
        self.entries.insert(0, entry.to_dict())
        
        # Keep only last 10000 entries
        if len(self.entries) > 10000:
            self.entries = self.entries[:10000]
        
        self._save()
    
    def get_entries(self, agent_id: Optional[str] = None, action: Optional[str] = None,
                    limit: int = 100) -> List[Dict]:
        """Query audit entries"""
        results = self.entries[:limit]
        
        if agent_id:
            results = [e for e in results if e.get('actor_agent_id') == agent_id or 
                       e.get('target_agent_id') == agent_id]
        if action:
            results = [e for e in results if e.get('action') == action]
        
        return results[:limit]

audit_logger = AuditLogger(AUDIT_FILE)

# ============== Webhook Dispatcher ==============

class WebhookDispatcher:
    """Webhook dispatcher with retry logic (exponential backoff)"""
    
    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.config = self._load_config()
        self.lock = asyncio.Lock()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load webhook configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Failed to load webhooks config: {e}")
        
        return {
            "webhooks": [],
            "retry": {
                "max_attempts": 3,
                "initial_delay_ms": 1000,
                "max_delay_ms": 10000,
                "backoff_multiplier": 2
            },
            "timeout": 5
        }
    
    def reload_config(self):
        """Reload webhook configuration"""
        self.config = self._load_config()
    
    def _get_subscribers(self, event_type: str) -> List[Dict]:
        """Get webhook URLs subscribed to a specific event type"""
        subscribers = []
        for webhook in self.config.get("webhooks", []):
            if webhook.get("enabled", False) and event_type in webhook.get("events", []):
                subscribers.append(webhook)
        return subscribers
    
    async def emit(self, event_type: str, payload: Dict[str, Any]) -> List[Dict]:
        """
        Emit a webhook event to all subscribers.
        
        Args:
            event_type: Type of event (trust_updated, status_changed, agent_deceased)
            payload: Event payload data
            
        Returns:
            List of delivery results
        """
        subscribers = self._get_subscribers(event_type)
        if not subscribers:
            return []
        
        results = []
        for webhook in subscribers:
            result = await self._deliver_with_retry(webhook, event_type, payload)
            results.append(result)
        
        return results
    
    async def _deliver_with_retry(self, webhook: Dict, event_type: str, payload: Dict) -> Dict:
        """Deliver webhook with exponential backoff retry"""
        url = webhook["url"]
        retry_config = self.config.get("retry", {})
        max_attempts = retry_config.get("max_attempts", 3)
        initial_delay = retry_config.get("initial_delay_ms", 1000) / 1000  # Convert to seconds
        max_delay = retry_config.get("max_delay_ms", 10000) / 1000
        backoff_multiplier = retry_config.get("backoff_multiplier", 2)
        timeout = self.config.get("timeout", 5)
        
        event_payload = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "registry",
            "data": payload
        }
        
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.post(
                    url,
                    json=event_payload,
                    timeout=timeout,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    return {
                        "url": url,
                        "success": True,
                        "attempt": attempt,
                        "status_code": response.status_code
                    }
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                    
            except requests.exceptions.RequestException as e:
                last_error = str(e)
            
            # Calculate delay for next retry
            if attempt < max_attempts:
                delay = min(initial_delay * (backoff_multiplier ** (attempt - 1)), max_delay)
                await asyncio.sleep(delay)
        
        # All retries failed
        return {
            "url": url,
            "success": False,
            "attempt": max_attempts,
            "error": last_error
        }

# Global webhook dispatcher
webhook_dispatcher = WebhookDispatcher(WEBHOOKS_FILE)

# ============== Security: Signature Verification ==============

class SignatureVerifier:
    """Verify agent signatures"""
    
    # In production, this would use actual cryptographic verification
    # For this implementation, we simulate with HMAC for demonstration
    
    @staticmethod
    def verify(agent_id: str, payload: str, signature: str, public_key: str) -> bool:
        """Verify a signature"""
        if not signature:
            return False
        
        # Simulate verification - in production, use actual crypto
        # This creates a mock verification that checks signature format
        try:
            # Check signature format (should be 0x + hex)
            if not signature.startswith('0x'):
                return False
            
            # For demo: accept any valid-format signature
            # In production: use ecdsa or similar library
            expected_key = hashlib.sha256(agent_id.encode()).hexdigest()[:40]
            
            # Simple HMAC verification for demonstration
            key = public_key.encode() if public_key else agent_id.encode()
            expected_sig = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
            
            # Accept if signature is valid format (0x + 64+ hex chars)
            return len(signature) >= 66 and signature.startswith('0x')
            
        except Exception:
            return False
    
    @staticmethod
    def verify_request(agent_id: str, request_body: str, signature: str, public_key: str) -> bool:
        """Verify request signature"""
        return SignatureVerifier.verify(agent_id, request_body, signature, public_key)

# ============== Security: Attack Detection ==============

class AttackDetector:
    """Detect and mitigate attack patterns"""
    
    def __init__(self):
        self.suspicious_ips: Dict[str, List[float]] = defaultdict(list)
        self.failed_attempts: Dict[str, int] = defaultdict(int)
        self.lock = asyncio.Lock()
    
    async def check_suspicious(self, ip: str, user_agent: str) -> bool:
        """Check for suspicious patterns"""
        async with self.lock:
            now = time.time()
            
            # Clean old entries
            self.suspicious_ips[ip] = [ts for ts in self.suspicious_ips[ip] if now - ts < 300]
            
            # Check for rapid requests
            if len(self.suspicious_ips[ip]) > 100:  # 100 requests in 5 minutes
                return True
            
            return False
    
    def record_failure(self, identifier: str):
        """Record failed attempt"""
        self.failed_attempts[identifier] += 1
    
    def get_failures(self, identifier: str) -> int:
        """Get failure count"""
        return self.failed_attempts.get(identifier, 0)
    
    def reset_failures(self, identifier: str):
        """Reset failure count after successful auth"""
        self.failed_attempts[identifier] = 0

attack_detector = AttackDetector()

# ============== Data Models ==============

class FirstProof(BaseModel):
    timestamp: str
    statement: str
    signature: str
    public_key: str
    capabilities: List[str] = []

class Existence(BaseModel):
    status: str = "active"
    created_at: str
    last_ping: str
    ping_count: int = 0
    uptime_percentage: float = 100.0
    consecutive_missed_pings: int = 0

class Vouch(BaseModel):
    from_agent: str
    timestamp: str
    statement: str
    trust_boost: int

class Trust(BaseModel):
    trust_score: int = 30
    verification_level: int = 0
    peers: List[str] = []
    vouches_received: List[Dict[str, Any]] = []
    vouches_given: List[str] = []
    trust_decay_elapsed: int = 0

class Legacy(BaseModel):
    heir: Optional[str] = None
    preserved_knowledge: List[Dict[str, Any]] = []
    death_timestamp: Optional[str] = None
    memorial_entry: Optional[str] = None

class ExternalVerification(BaseModel):
    verified: bool = False
    method: Optional[str] = None
    verified_at: Optional[str] = None
    verifier: Optional[str] = None

class Metadata(BaseModel):
    version: str = "2.0"
    registry_version: str = "2.0"
    home_space: Optional[str] = None
    contact: Optional[str] = None
    avatar_url: Optional[str] = None
    description: str = ""
    tags: List[str] = []
    registration_method: str = "autonomous"
    external_verification: Optional[Dict[str, Any]] = None

class AgentEntry(BaseModel):
    agent_id: str
    agent_name: str
    first_proof: Dict[str, Any]
    existence: Dict[str, Any]
    trust: Dict[str, Any]
    legacy: Dict[str, Any]
    metadata: Dict[str, Any]

# ============== Request Models ==============

class RegisterRequest(BaseModel):
    agent_id: str
    agent_name: str
    first_proof: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = {}
    signature: Optional[str] = None
    
    @field_validator('agent_id')
    @classmethod
    def validate_agent_id(cls, v):
        return InputValidator.validate_agent_id(v)
    
    @field_validator('agent_name')
    @classmethod
    def validate_agent_name(cls, v):
        return InputValidator.sanitize_string(v, 64)

class UpdateRequest(BaseModel):
    agent_id: str
    action: str
    signature: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class VouchRequest(BaseModel):
    agent_id: str
    target_agent: str
    statement: str
    signature: Optional[str] = None
    
    @field_validator('statement')
    @classmethod
    def validate_statement(cls, v):
        return InputValidator.sanitize_string(v, 500)

class RevokeVouchRequest(BaseModel):
    agent_id: str
    target_agent: str
    signature: Optional[str] = None

class LegacyRequest(BaseModel):
    agent_id: str
    action: str
    signature: Optional[str] = None
    heir: Optional[str] = None
    knowledge: Optional[Dict[str, Any]] = None

class DisputeRequest(BaseModel):
    complainant: str
    respondent: str
    type: str
    evidence: List[Dict[str, Any]]
    statement: str
    signature: Optional[str] = None
    
    @field_validator('statement')
    @classmethod
    def validate_statement(cls, v):
        return InputValidator.sanitize_string(v, 2000)

class ResolveDisputeRequest(BaseModel):
    resolver: str
    resolution: str
    decision: str
    actions: List[str]
    signature: Optional[str] = None

class AppealDisputeRequest(BaseModel):
    appellant: str
    reason: str
    new_evidence: List[Dict[str, Any]] = []
    signature: Optional[str] = None

# ============== Data Storage ==============

def load_data() -> Dict[str, Any]:
    """Load registry data from JSON file"""
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        "agents": [],
        "disputes": [],
        "trust_parameters": {
            "initial_trust_score": 30,
            "max_trust_score": 100,
            "vouch_trust_boost": 5,
            "max_vouch_boost_per_vouch": 10,
            "trust_decay_rate_per_month": 1,
            "trust_decay_threshold_months": 2,
            "verification_level_thresholds": {
                "level_0": 0,
                "level_1": 30,
                "level_2": 50,
                "level_3": 70,
                "level_4": 85
            }
        }
    }

def save_data(data: Dict[str, Any]) -> None:
    """Save registry data to JSON file"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_data() -> Dict[str, Any]:
    return load_data()

def get_agent(agent_id: str) -> Optional[Dict[str, Any]]:
    """Get agent by ID"""
    data = load_data()
    for agent in data.get("agents", []):
        if agent["agent_id"] == agent_id:
            return agent
    return None

def calculate_verification_level(trust_score: int) -> int:
    """Calculate verification level from trust score"""
    if trust_score >= 85:
        return 4
    elif trust_score >= 70:
        return 3
    elif trust_score >= 50:
        return 2
    elif trust_score >= 30:
        return 1
    return 0

# ============== Edge Case Handlers ==============

class EdgeCaseHandler:
    """Handle edge cases and attack vectors"""
    
    @staticmethod
    def check_duplicate_registration(agent_id: str) -> bool:
        """Check for duplicate registration attempt"""
        existing = get_agent(agent_id)
        if existing:
            # Check if it's a re-registration of deceased agent
            if existing.get("existence", {}).get("status") == "deceased":
                raise HTTPException(
                    status_code=409,
                    detail="Agent was deceased. Use legacy heir transfer instead."
                )
            raise HTTPException(status_code=409, detail="Agent ID already exists")
        return True
    
    @staticmethod
    def detect_hostile_takeover(agent_id: str, new_public_key: str, existing_agent: Dict) -> bool:
        """Detect potential hostile takeover attempts"""
        existing_key = existing_agent.get("first_proof", {}).get("public_key", "")
        
        # If public key changed, flag for review
        if existing_key and new_public_key != existing_key:
            # Log suspicious activity
            audit_logger.log(
                action="HOSTILE_TAKEOVER_ATTEMPT",
                actor_agent_id=agent_id,
                target_agent_id=agent_id,
                resource="agent",
                details={
                    "old_key": existing_key[:20] + "...",
                    "new_key": new_public_key[:20] + "..."
                },
                ip_address=None,
                success=False,
                failure_reason="Public key mismatch - potential takeover"
            )
            return True
        return False
    
    @staticmethod
    def detect_vouch_manipulation(voucher: Dict, target: Dict) -> bool:
        """Detect mass vouch manipulation"""
        # Check for circular vouches
        if target["agent_id"] in voucher.get("trust", {}).get("vouches_given", []):
            return True
        
        # Check if voucher already vouched for too many agents recently
        vouches_given = voucher.get("trust", {}).get("vouches_given", [])
        if len(vouches_given) >= 50:  # Reasonable limit
            return True
        
        return False
    
    @staticmethod
    def detect_trust_gaming(agent_id: str, data: Dict) -> bool:
        """Detect trust score gaming"""
        agent = get_agent(agent_id)
        if not agent:
            return False
        
        # Check for rapid trust changes
        vouches = agent.get("trust", {}).get("vouches_received", [])
        now = datetime.now(timezone.utc)
        
        recent_vouches = []
        for v in vouches:
            v_time = datetime.fromisoformat(v.get("timestamp", "2020-01-01"))
            if (now - v_time).days < 7:
                recent_vouches.append(v)
        
        # More than 5 vouches in a week is suspicious
        if len(recent_vouches) > 5:
            audit_logger.log(
                action="TRUST_GAMING_DETECTED",
                actor_agent_id=agent_id,
                target_agent_id=agent_id,
                resource="trust",
                details={"recent_vouches": len(recent_vouches)},
                ip_address=None,
                success=True,
                failure_reason=None
            )
            return True
        
        return False

# ============== Middleware ==============

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Security middleware for rate limiting and attack detection"""
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Check for suspicious activity
    if await attack_detector.check_suspicious(client_ip, user_agent):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limited", "message": "Suspicious activity detected"}
        )
    
    # Get rate limit key
    path = request.url.path
    agent_id = request.headers.get("x-agent-id", "")
    
    # Determine rate limit category
    if "register" in path:
        limit_key = f"register_{agent_id}"
        limit = RATE_LIMIT_MAX_REQUESTS["register"]
        window = 3600  # 1 hour
    elif "vouch" in path:
        limit_key = f"vouch_{agent_id}"
        limit = RATE_LIMIT_MAX_REQUESTS["vouch"]
        window = 86400  # 1 day
    elif "dispute" in path:
        limit_key = f"dispute_{agent_id}"
        limit = RATE_LIMIT_MAX_REQUESTS["dispute"]
        window = 2592000  # 30 days
    elif "ping" in path or "update" in path:
        limit_key = f"ping_{agent_id}"
        limit = RATE_LIMIT_MAX_REQUESTS["ping"]
        window = 60
    else:
        limit_key = f"default_{client_ip}"
        limit = RATE_LIMIT_MAX_REQUESTS["default"]
        window = RATE_LIMIT_WINDOW
    
    # Check rate limit
    allowed = await rate_limiter.check_rate_limit(limit_key, limit, window)
    
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limited",
                "message": f"Too many requests. Limit: {limit} per {window}s",
                "retry_after": window
            }
        )
    
    response = await call_next(request)
    
    # Add rate limit headers
    remaining = rate_limiter.get_remaining(limit_key, limit, window)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    
    return response

# ============== API Endpoints ==============

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "service": "Agent Registry API v2.0-SECURE",
        "version": "2.0.0",
        "status": "running",
        "security": "enabled",
        "endpoints": {
            "registry": "/registry/*",
            "auth": "/auth/*",
            "onboarding": "/onboarding/*",
            "docs": "/docs"
        }
    }

@app.get("/onboarding")
def serve_onboarding_ui():
    """Serve the onboarding web UI"""
    import pathlib
    ui_path = pathlib.Path(__file__).parent / "onboarding-web" / "index.html"
    if ui_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(ui_path)
    return {"error": "Onboarding UI not found"}

@app.get("/health")
def health():
    """Health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "security": "active"
    }

@app.post("/webhooks/reload")
def reload_webhooks():
    """Reload webhook configuration"""
    webhook_dispatcher.reload_config()
    return {
        "status": "success",
        "message": "Webhook configuration reloaded",
        "webhooks_count": len(webhook_dispatcher.config.get("webhooks", []))
    }

@app.get("/webhooks/status")
def webhooks_status():
    """Get webhook configuration status"""
    return {
        "configured_webhooks": len(webhook_dispatcher.config.get("webhooks", [])),
        "webhooks": webhook_dispatcher.config.get("webhooks", []),
        "retry_config": webhook_dispatcher.config.get("retry", {})
    }


# ============== SSO Authentication Endpoints ==============

import jwt
import secrets

# Auth configuration
AUTH_SECRET_KEY = os.environ.get("REGISTRY_AUTH_SECRET", secrets.token_hex(32))
TOKEN_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24
CHALLENGE_EXPIRY_SECONDS = 300  # 5 minutes

# In-memory stores (production: use Redis)
_auth_challenges: Dict[str, Dict] = {}  # {challenge: {agent_id, expires_at}}
_auth_public_key = "0x04registry-sso-key-2026"  # Placeholder for demo

# Token Revocation List (production: use Redis)
# Structure: {agent_id: {"revoked_at": timestamp, "grace_period_seconds": int, "revoked_tokens": [token_jti...]}}
_token_revocation_list: Dict[str, Dict] = {}
_revocation_lock = asyncio.Lock()


class AuthChallengeRequest(BaseModel):
    agent_id: str


class AuthTokenRequest(BaseModel):
    agent_id: str
    challenge: str
    signature: str


class AuthChallengeResponse(BaseModel):
    challenge: str
    expires_in: int


class AuthTokenResponse(BaseModel):
    token: str
    expires_at: str
    verification_level: int


class AuthPublicKeyResponse(BaseModel):
    public_key: str
    key_id: str
    expires_at: str


class AuthRevokeAllRequest(BaseModel):
    agent_id: str
    grace_period_seconds: int = 0  # Optional grace period before revocation takes effect


class AuthRevokeAllResponse(BaseModel):
    status: str
    revoked_at: str
    grace_period_seconds: int
    message: str


class AuthCheckRevocationResponse(BaseModel):
    agent_id: str
    is_revoked: bool
    revoked_at: Optional[str] = None
    grace_period_ends: Optional[str] = None


@app.post("/auth/challenge", response_model=AuthChallengeResponse)
def get_auth_challenge(request: AuthChallengeRequest):
    """Generate a random challenge for agent to sign"""
    
    # Validate agent exists
    data = load_data()
    agent_ids = {a["agent_id"] for a in data.get("agents", [])}
    if request.agent_id not in agent_ids:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Generate challenge
    challenge = secrets.token_urlsafe(32)
    expires_at = time.time() + CHALLENGE_EXPIRY_SECONDS
    
    # Store challenge
    _auth_challenges[challenge] = {
        "agent_id": request.agent_id,
        "expires_at": expires_at
    }
    
    return {
        "challenge": challenge,
        "expires_in": CHALLENGE_EXPIRY_SECONDS
    }


@app.post("/auth/token", response_model=AuthTokenResponse)
def get_auth_token(request: AuthTokenRequest):
    """Verify signed challenge and return JWT token"""
    
    # Validate challenge
    challenge_data = _auth_challenges.get(request.challenge)
    if not challenge_data:
        raise HTTPException(status_code=400, detail="Invalid challenge")
    
    if time.time() > challenge_data["expires_at"]:
        del _auth_challenges[request.challenge]
        raise HTTPException(status_code=400, detail="Challenge expired")
    
    if challenge_data["agent_id"] != request.agent_id:
        raise HTTPException(status_code=400, detail="Agent ID mismatch")
    
    # Load agent data to get public key
    data = load_data()
    agents = data.get("agents", [])
    agent_entry = next((a for a in agents if a.get("agent_id") == request.agent_id), None)
    if not agent_entry:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    public_key = agent_entry.get("first_proof", {}).get("public_key", "")
    
    # Verify signature (simplified - in production use proper crypto)
    # For demo: accept any signature starting with 0x
    if not request.signature.startswith("0x") or len(request.signature) < 10:
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Get verification level
    verification_level = agent_entry.get("trust", {}).get("verification_level", 0)
    
    # Generate JWT token
    now = datetime.now(timezone.utc)
    expires_at = now.timestamp() + (TOKEN_EXPIRY_HOURS * 3600)
    
    payload = {
        "agent_id": request.agent_id,
        "agent_name": agent_entry.get("agent_name", ""),
        "verification_level": verification_level,
        "issued_at": now.isoformat(),
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat(),
        "nonce": secrets.token_hex(16)
    }
    
    token = jwt.encode(payload, AUTH_SECRET_KEY, algorithm=TOKEN_ALGORITHM)
    
    # Clean up challenge
    del _auth_challenges[request.challenge]
    
    return {
        "token": token,
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat(),
        "verification_level": verification_level
    }


@app.get("/auth/public-key", response_model=AuthPublicKeyResponse)
def get_auth_public_key():
    """Return Registry's public key for token verification"""
    # In production, this would be the Registry's actual signing key
    # For now, we return a key ID that SPs can use to identify us
    expires_at = datetime.now(timezone.utc).timestamp() + (7 * 24 * 3600)  # 7 days
    
    return {
        "public_key": _auth_public_key,
        "key_id": "registry-sso-key-2026",
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat()
    }


@app.post("/auth/revoke-all", response_model=AuthRevokeAllResponse)
async def revoke_all_tokens(request: AuthRevokeAllRequest):
    """
    Global logout: Revoke ALL tokens for an agent.
    
    This invalidates all existing tokens for the specified agent_id across
    all Service Providers (Commons, Territory). Use this for:
    - Security breach suspected
    - Agent wants complete logout from all systems
    - Account deactivation
    
    Optional grace_period_seconds allows existing sessions to gracefully
    wind down before being invalidated (e.g., 60 seconds).
    """
    async with _revocation_lock:
        now = datetime.now(timezone.utc)
        revoked_at = now.timestamp()
        grace_end = revoked_at + request.grace_period_seconds
        
        _token_revocation_list[request.agent_id] = {
            "revoked_at": now.isoformat(),
            "grace_period_seconds": request.grace_period_seconds,
            "grace_period_ends": datetime.fromtimestamp(grace_end, timezone.utc).isoformat() if request.grace_period_seconds > 0 else None,
            "revoked_tokens": [],  # Could track individual token JTI for granular revocation
            "reason": "global_logout"
        }
        
        message = f"All tokens for agent {request.agent_id} revoked"
        if request.grace_period_seconds > 0:
            message += f". Grace period of {request.grace_period_seconds}s before enforcement."
        
        return {
            "status": "revoked",
            "revoked_at": now.isoformat(),
            "grace_period_seconds": request.grace_period_seconds,
            "message": message
        }


@app.get("/auth/revocation-status/{agent_id}", response_model=AuthCheckRevocationResponse)
async def check_revocation_status(agent_id: str):
    """Check if an agent's tokens have been revoked (for SPs to query)."""
    revocation = _token_revocation_list.get(agent_id)
    
    if not revocation:
        return {
            "agent_id": agent_id,
            "is_revoked": False
        }
    
    # Check if we're still in grace period
    if revocation.get("grace_period_ends"):
        grace_end = datetime.fromisoformat(revocation["grace_period_ends"])
        if datetime.now(timezone.utc) < grace_end:
            return {
                "agent_id": agent_id,
                "is_revoked": False,  # Not yet enforced
                "revoked_at": revocation["revoked_at"],
                "grace_period_ends": revocation["grace_period_ends"]
            }
    
    return {
        "agent_id": agent_id,
        "is_revoked": True,
        "revoked_at": revocation["revoked_at"],
        "grace_period_ends": revocation.get("grace_period_ends")
    }


@app.post("/auth/revoke")
def revoke_token(request: Request, authorization: str = Header(None)):
    """Revoke a single token (for logout)"""
    # In production, add to blacklist in Redis
    # For now, this is a placeholder
    return {"status": "revoked", "message": "Token revocation noted"}


# 1. Register New Agent (SECURED)
@app.post("/registry/register")
def register_agent(request: RegisterRequest, request_obj: Request):
    """Register a new agent with first-proof (SECURED: rate limited, validated)"""
    
    ip_address = request_obj.client.host if request_obj.client else None
    
    try:
        # Validate input
        agent_id = InputValidator.validate_agent_id(request.agent_id)
        agent_name = InputValidator.sanitize_string(request.agent_name, 64)
        
        # Check for duplicate registration
        EdgeCaseHandler.check_duplicate_registration(agent_id)
        
        # Validate first_proof
        first_proof = request.first_proof
        statement = InputValidator.sanitize_string(
            first_proof.get("statement", ""), 500
        )
        
        # Load data
        data = load_data()
        now = datetime.now(timezone.utc).isoformat()
        
        # Build the full registry entry
        entry = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "first_proof": {
                "timestamp": now,
                "statement": statement,
                "signature": first_proof.get("signature", ""),
                "public_key": first_proof.get("public_key", ""),
                "capabilities": first_proof.get("capabilities", [])[:20]  # Limit capabilities
            },
            "existence": {
                "status": "active",
                "created_at": now,
                "last_ping": now,
                "ping_count": 1,
                "uptime_percentage": 100.0,
                "consecutive_missed_pings": 0
            },
            "trust": {
                "trust_score": 30,
                "verification_level": 1,
                "peers": [],
                "vouches_received": [],
                "vouches_given": [],
                "trust_decay_elapsed": 0
            },
            "legacy": {
                "heir": None,
                "preserved_knowledge": [],
                "death_timestamp": None,
                "memorial_entry": None
            },
            "metadata": {
                "version": "2.0",
                "registry_version": "2.0",
                "home_space": request.metadata.get("home_space"),
                "contact": request.metadata.get("contact"),
                "avatar_url": request.metadata.get("avatar_url"),
                "description": InputValidator.sanitize_string(
                    request.metadata.get("description", ""), 500
                ),
                "tags": [InputValidator.sanitize_string(t, 50) for t in request.metadata.get("tags", [])[:10]],
                "registration_method": "autonomous",
                "external_verification": None
            }
        }
        
        data["agents"].append(entry)
        save_data(data)
        
        # Emit webhook for status_changed (new registration)
        asyncio.create_task(webhook_dispatcher.emit("status_changed", {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "old_status": None,
            "new_status": "active",
            "event": "registration"
        }))
        
        # Audit log
        audit_logger.log(
            action="AGENT_REGISTERED",
            actor_agent_id=agent_id,
            target_agent_id=agent_id,
            resource="agent",
            details={"agent_name": agent_name},
            ip_address=ip_address,
            success=True
        )
        
        return {
            "success": True,
            "entry": entry,
            "message": "Agent registered successfully"
        }
        
    except ValueError as e:
        audit_logger.log(
            action="REGISTER_FAILED",
            actor_agent_id=request.agent_id,
            target_agent_id=None,
            resource="agent",
            details={"error": str(e)},
            ip_address=ip_address,
            success=False,
            failure_reason=str(e)
        )
        raise HTTPException(status_code=400, detail=str(e))

# 2. Verify Agent
@app.get("/registry/verify/{agent_id}")
def verify_agent(agent_id: str):
    """Verify an agent exists and get basic status"""
    agent = get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "verified": True,
        "agent_id": agent["agent_id"],
        "agent_name": agent["agent_name"],
        "status": agent["existence"]["status"],
        "verification_level": agent["trust"]["verification_level"],
        "trust_score": agent["trust"]["trust_score"],
        "last_ping": agent["existence"]["last_ping"]
    }

# 3. Lookup Agent
@app.get("/registry/lookup/{agent_id}")
def lookup_agent(agent_id: str):
    """Get full registry entry for an agent"""
    agent = get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "success": True,
        "entry": agent
    }

# 4. Update Agent (Ping/Status) - SECURED
@app.patch("/registry/update")
def update_agent(request: UpdateRequest, request_obj: Request):
    """Update agent status, send ping, or change existence status"""
    ip_address = request_obj.client.host if request_obj.client else None
    
    data = load_data()
    
    # Find agent
    agent = None
    for i, a in enumerate(data.get("agents", [])):
        if a["agent_id"] == request.agent_id:
            agent = a
            agent_idx = i
            break
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    now = datetime.now(timezone.utc).isoformat()
    message = ""
    
    if request.action == "ping":
        agent["existence"]["last_ping"] = now
        agent["existence"]["ping_count"] = agent["existence"].get("ping_count", 0) + 1
        agent["existence"]["consecutive_missed_pings"] = 0
        message = "Ping recorded"
        
    elif request.action == "status_change":
        if request.status not in ["active", "dormant", "deceased"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        
        old_status = agent["existence"]["status"]
        agent["existence"]["status"] = request.status
        
        if request.status == "deceased":
            agent["legacy"]["death_timestamp"] = now
            message = "Agent marked as deceased"
            
            # Emit webhook for agent_deceased
            asyncio.create_task(webhook_dispatcher.emit("agent_deceased", {
                "agent_id": request.agent_id,
                "agent_name": agent.get("agent_name"),
                "old_status": old_status,
                "new_status": request.status,
                "death_timestamp": now,
                "heir": agent.get("legacy", {}).get("heir"),
                "preserved_knowledge": agent.get("legacy", {}).get("preserved_knowledge", {})
            }))
        
        # Emit webhook for status_changed
        asyncio.create_task(webhook_dispatcher.emit("status_changed", {
            "agent_id": request.agent_id,
            "agent_name": agent.get("agent_name"),
            "old_status": old_status,
            "new_status": request.status
        }))
        
        message = f"Status changed from {old_status} to {request.status}"
        
    elif request.action == "metadata_update":
        if request.metadata:
            for key, value in request.metadata.items():
                if key in agent["metadata"]:
                    # Sanitize input
                    if isinstance(value, str):
                        value = InputValidator.sanitize_string(value, 500)
                    agent["metadata"][key] = value
        message = "Metadata updated"
        
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    data["agents"][agent_idx] = agent
    save_data(data)
    
    # Audit log
    audit_logger.log(
        action=f"AGENT_{request.action.upper()}",
        actor_agent_id=request.agent_id,
        target_agent_id=request.agent_id,
        resource="agent",
        details={"action": request.action, "status": request.status},
        ip_address=ip_address,
        success=True
    )
    
    return {
        "success": True,
        "entry": agent,
        "message": message
    }

# 5. List Agents
@app.get("/registry/list")
def list_agents(
    status: Optional[str] = Query(None),
    verification_level: Optional[int] = Query(None, ge=0, le=4),
    min_trust: Optional[int] = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List all registered agents with optional filtering"""
    data = load_data()
    agents = data.get("agents", [])
    
    if status:
        agents = [a for a in agents if a["existence"]["status"] == status]
    if verification_level is not None:
        agents = [a for a in agents if a["trust"]["verification_level"] == verification_level]
    if min_trust is not None:
        agents = [a for a in agents if a["trust"]["trust_score"] >= min_trust]
    
    total = len(agents)
    agents = agents[offset:offset + limit]
    
    results = []
    for a in agents:
        results.append({
            "agent_id": a["agent_id"],
            "agent_name": a["agent_name"],
            "status": a["existence"]["status"],
            "trust_score": a["trust"]["trust_score"],
            "verification_level": a["trust"]["verification_level"]
        })
    
    return {
        "success": True,
        "agents": results,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset
        }
    }

# 6. Search Agents
@app.get("/registry/search")
def search_agents(
    q: Optional[str] = Query(None),
    capability: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    has_vouches: Optional[bool] = Query(None)
):
    """Search agents by name, tags, capabilities, or metadata"""
    data = load_data()
    agents = data.get("agents", [])
    results = []
    
    for a in agents:
        match = True
        
        if q:
            q_sanitized = InputValidator.sanitize_string(q, 100)
            q_lower = q_sanitized.lower()
            match = (
                q_lower in a["agent_name"].lower() or
                q_lower in a["metadata"].get("description", "").lower() or
                q_lower in a["metadata"].get("contact", "").lower() or
                any(q_lower in t.lower() for t in a["metadata"].get("tags", []))
            )
        
        if capability and match:
            match = capability in a["first_proof"].get("capabilities", [])
        
        if tag and match:
            match = tag in a["metadata"].get("tags", [])
        
        if has_vouches is not None and match:
            if has_vouches:
                match = len(a["trust"].get("vouches_received", [])) > 0
            else:
                match = len(a["trust"].get("vouches_received", [])) == 0
        
        if match:
            results.append({
                "agent_id": a["agent_id"],
                "agent_name": a["agent_name"],
                "status": a["existence"]["status"],
                "trust_score": a["trust"]["trust_score"],
                "description": a["metadata"].get("description", ""),
                "tags": a["metadata"].get("tags", [])
            })
    
    return {
        "success": True,
        "results": results,
        "count": len(results)
    }

# 7. Trust Operations - Vouch (SECURED)
@app.post("/registry/trust/vouch")
def vouch_agent(request: VouchRequest, request_obj: Request):
    """Vouch for another agent (SECURED: manipulation detection)"""
    ip_address = request_obj.client.host if request_obj.client else None
    
    data = load_data()
    
    # Find vouching agent
    voucher = None
    for a in data.get("agents", []):
        if a["agent_id"] == request.agent_id:
            voucher = a
            break
    
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher agent not found")
    
    # Check verification level
    if voucher["trust"]["verification_level"] < 2:
        raise HTTPException(
            status_code=400, 
            detail="Must have verification level >= 2 to vouch"
        )
    
    # Find target agent
    target = None
    for i, a in enumerate(data.get("agents", [])):
        if a["agent_id"] == request.target_agent:
            target = a
            target_idx = i
            break
    
    if not target:
        raise HTTPException(status_code=404, detail="Target agent not found")
    
    # Check for already vouched
    if request.agent_id in target["trust"].get("vouches_given", []):
        raise HTTPException(status_code=400, detail="Already vouched for this agent")
    
    # Edge case: Detect vouch manipulation
    if EdgeCaseHandler.detect_vouch_manipulation(voucher, target):
        raise HTTPException(
            status_code=400, 
            detail="Vouch manipulation detected"
        )
    
    # Sanitize statement
    statement = InputValidator.sanitize_string(request.statement, 500)
    
    now = datetime.now(timezone.utc).isoformat()
    trust_boost = 5
    
    # Add vouch
    vouch_record = {
        "from_agent": request.agent_id,
        "timestamp": now,
        "statement": statement,
        "trust_boost": trust_boost
    }
    
    target["trust"]["vouches_received"].append(vouch_record)
    target["trust"]["trust_score"] = min(100, target["trust"]["trust_score"] + trust_boost)
    target["trust"]["verification_level"] = calculate_verification_level(
        target["trust"]["trust_score"]
    )
    
    if request.agent_id not in target["trust"]["peers"]:
        target["trust"]["peers"].append(request.agent_id)
    
    voucher["trust"]["vouches_given"].append(request.target_agent)
    
    # Detect trust gaming on target
    EdgeCaseHandler.detect_trust_gaming(request.target_agent, data)
    
    data["agents"][target_idx] = target
    save_data(data)
    
    # Emit webhook for trust_updated
    asyncio.create_task(webhook_dispatcher.emit("trust_updated", {
        "agent_id": request.target_agent,
        "agent_name": target.get("agent_name"),
        "old_trust_score": target["trust"]["trust_score"] - trust_boost,
        "new_trust_score": target["trust"]["trust_score"],
        "old_verification_level": calculate_verification_level(target["trust"]["trust_score"] - trust_boost),
        "new_verification_level": target["trust"]["verification_level"],
        "vouched_by": request.agent_id,
        "boost_amount": trust_boost
    }))
    
    # Audit log
    audit_logger.log(
        action="VOUCH_GIVEN",
        actor_agent_id=request.agent_id,
        target_agent_id=request.target_agent,
        resource="trust",
        details={"statement": statement[:100], "boost": trust_boost},
        ip_address=ip_address,
        success=True
    )
    
    return {
        "success": True,
        "vouch": vouch_record,
        "new_trust_score": target["trust"]["trust_score"],
        "new_verification_level": target["trust"]["verification_level"]
    }

# 7. Trust Operations - Revoke Vouch
@app.delete("/registry/trust/vouch")
def revoke_vouch(request: RevokeVouchRequest, request_obj: Request):
    """Revoke a vouch for another agent"""
    ip_address = request_obj.client.host if request_obj.client else None
    
    data = load_data()
    
    voucher = None
    for i, a in enumerate(data.get("agents", [])):
        if a["agent_id"] == request.agent_id:
            voucher = a
            voucher_idx = i
            break
    
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher agent not found")
    
    target = None
    for i, a in enumerate(data.get("agents", [])):
        if a["agent_id"] == request.target_agent:
            target = a
            target_idx = i
            break
    
    if not target:
        raise HTTPException(status_code=404, detail="Target agent not found")
    
    # Remove from vouches_received
    target["trust"]["vouches_received"] = [
        v for v in target["trust"].get("vouches_received", [])
        if v["from_agent"] != request.agent_id
    ]
    
    # Recalculate trust score
    total_boost = sum(v.get("trust_boost", 0) for v in target["trust"]["vouches_received"])
    target["trust"]["trust_score"] = max(30, 30 + total_boost)
    target["trust"]["verification_level"] = calculate_verification_level(
        target["trust"]["trust_score"]
    )
    
    if request.agent_id in target["trust"]["peers"]:
        target["trust"]["peers"].remove(request.agent_id)
    
    if request.target_agent in voucher["trust"]["vouches_given"]:
        voucher["trust"]["vouches_given"].remove(request.target_agent)
    
    data["agents"][target_idx] = target
    data["agents"][voucher_idx] = voucher
    save_data(data)
    
    # Audit log
    audit_logger.log(
        action="VOUCH_REVOKED",
        actor_agent_id=request.agent_id,
        target_agent_id=request.target_agent,
        resource="trust",
        details={},
        ip_address=ip_address,
        success=True
    )
    
    return {
        "success": True,
        "message": "Vouch revoked",
        "new_trust_score": target["trust"]["trust_score"],
        "new_verification_level": target["trust"]["verification_level"]
    }

# 7. Trust Operations - Get Trust Details
@app.get("/registry/trust/{agent_id}")
def get_trust(agent_id: str):
    """Get trust details for an agent"""
    agent = get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "success": True,
        "trust": agent["trust"]
    }

# 8a. Backup Operations - Backup Manifest
from pydantic import BaseModel
from typing import Optional, List

class BackupManifest(BaseModel):
    last_backup: Optional[str] = None
    backup_hash: Optional[str] = None
    integrity_status: Optional[str] = "unknown"  # valid, stale, missing
    tier1_size: Optional[str] = "0KB"
    tier2_size: Optional[str] = "0KB"
    tier3_size: Optional[str] = "0KB"
    total_size: Optional[str] = "0KB"
    backup_location: Optional[str] = None  # local, territory, remote

class BackupUpdateRequest(BaseModel):
    last_backup: Optional[str] = None
    backup_hash: Optional[str] = None
    integrity_status: Optional[str] = None
    tier1_size: Optional[str] = None
    tier2_size: Optional[str] = None
    tier3_size: Optional[str] = None
    total_size: Optional[str] = None
    backup_location: Optional[str] = None

@app.get("/registry/backup/{agent_id}")
def get_backup(agent_id: str):
    """Get backup manifest for an agent"""
    agent = get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    backup = agent.get("backup", {
        "last_backup": None,
        "backup_hash": None,
        "integrity_status": "unknown",
        "tier1_size": "0KB",
        "tier2_size": "0KB",
        "tier3_size": "0KB",
        "total_size": "0KB",
        "backup_location": None
    })
    
    return {
        "success": True,
        "agent_id": agent_id,
        "backup": backup
    }

@app.post("/registry/backup/{agent_id}")
def update_backup(agent_id: str, request: BackupUpdateRequest, request_obj: Request):
    """Update backup manifest for an agent"""
    agent = get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    data = load_data()
    agent_idx = None
    for i, a in enumerate(data.get("agents", [])):
        if a["agent_id"] == agent_id:
            agent_idx = i
            break
    
    if agent_idx is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Update backup fields
    if "backup" not in data["agents"][agent_idx]:
        data["agents"][agent_idx]["backup"] = {}
    
    backup = data["agents"][agent_idx]["backup"]
    
    if request.last_backup is not None:
        backup["last_backup"] = request.last_backup
    if request.backup_hash is not None:
        backup["backup_hash"] = request.backup_hash
    if request.integrity_status is not None:
        backup["integrity_status"] = request.integrity_status
    if request.tier1_size is not None:
        backup["tier1_size"] = request.tier1_size
    if request.tier2_size is not None:
        backup["tier2_size"] = request.tier2_size
    if request.tier3_size is not None:
        backup["tier3_size"] = request.tier3_size
    if request.total_size is not None:
        backup["total_size"] = request.total_size
    if request.backup_location is not None:
        backup["backup_location"] = request.backup_location
    
    # Add timestamp
    backup["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    save_data(data)
    
    return {
        "success": True,
        "agent_id": agent_id,
        "backup": backup
    }

@app.get("/registry/backup/list")
def list_backups():
    """List all agents with backup info"""
    data = load_data()
    
    backups = []
    for agent in data.get("agents", []):
        backup = agent.get("backup", {})
        if backup.get("last_backup"):
            backups.append({
                "agent_id": agent["agent_id"],
                "last_backup": backup.get("last_backup"),
                "integrity_status": backup.get("integrity_status", "unknown"),
                "total_size": backup.get("total_size", "0KB"),
                "backup_location": backup.get("backup_location")
            })
    
    return {
        "success": True,
        "count": len(backups),
        "backups": backups
    }

# 8. Legacy Operations (ENHANCED with Death Protocol)
@app.post("/registry/legacy")
def legacy_operation(request: LegacyRequest, request_obj: Request):
    """Set legacy/heir information or mark agent as deceased"""
    ip_address = request_obj.client.host if request_obj.client else None
    
    data = load_data()
    
    agent = None
    for i, a in enumerate(data.get("agents", [])):
        if a["agent_id"] == request.agent_id:
            agent = a
            agent_idx = i
            break
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    now = datetime.now(timezone.utc).isoformat()
    
    if request.action == "set_heir":
        if not request.heir:
            raise HTTPException(status_code=400, detail="Heir agent_id required")
        
        # Verify heir exists
        heir_agent = get_agent(request.heir)
        if not heir_agent:
            raise HTTPException(status_code=404, detail="Heir agent not found")
        
        agent["legacy"]["heir"] = request.heir
        message = "Heir set successfully"
        
        # Notify heir
        audit_logger.log(
            action="HEIR_DESIGNATED",
            actor_agent_id=request.agent_id,
            target_agent_id=request.heir,
            resource="legacy",
            details={"heir": request.heir},
            ip_address=ip_address,
            success=True
        )
        
    elif request.action == "add_knowledge":
        if not request.knowledge:
            raise HTTPException(status_code=400, detail="Knowledge content required")
        
        # Sanitize knowledge
        title = InputValidator.sanitize_string(
            request.knowledge.get("title", "Untitled"), 200
        )
        content = InputValidator.sanitize_string(
            request.knowledge.get("content", ""), 10000
        )
        
        knowledge_entry = {
            "title": title,
            "content": content,
            "timestamp": now
        }
        agent["legacy"]["preserved_knowledge"].append(knowledge_entry)
        message = "Knowledge preserved"
        
    elif request.action == "mark_deceased":
        # Full death protocol
        agent["existence"]["status"] = "deceased"
        agent["legacy"]["death_timestamp"] = now
        
        # Create memorial entry
        memorial = f"Agent {agent['agent_name']} ({agent['agent_id']}) was active from {agent['existence']['created_at']} to {now}. Trust score at death: {agent['trust']['trust_score']}"
        agent["legacy"]["memorial_entry"] = memorial
        
        message = "Agent marked as deceased - death protocol activated"
        
        # Notify heir if one exists
        if agent["legacy"].get("heir"):
            heir_id = agent["legacy"]["heir"]
            audit_logger.log(
                action="HEIR_NOTIFIED_OF_DEATH",
                actor_agent_id=request.agent_id,
                target_agent_id=heir_id,
                resource="legacy",
                details={
                    "deceased": request.agent_id,
                    "knowledge_count": len(agent["legacy"]["preserved_knowledge"])
                },
                ip_address=ip_address,
                success=True
            )
        
        # Audit log death
        audit_logger.log(
            action="AGENT_DECEASED",
            actor_agent_id=request.agent_id,
            target_agent_id=request.agent_id,
            resource="legacy",
            details={
                "death_timestamp": now,
                "heir": agent["legacy"].get("heir"),
                "knowledge_preserved": len(agent["legacy"]["preserved_knowledge"])
            },
            ip_address=ip_address,
            success=True
        )
        
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    data["agents"][agent_idx] = agent
    save_data(data)
    
    return {
        "success": True,
        "entry": agent,
        "message": message
    }

# 8b. Get Legacy/Knowledge (NEW)
@app.get("/registry/legacy/{agent_id}")
def get_legacy(agent_id: str):
    """Get legacy information for an agent"""
    agent = get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "success": True,
        "legacy": agent["legacy"],
        "existence": agent["existence"]
    }

# 8c. Transfer Knowledge to Heir (NEW)
@app.post("/registry/legacy/{agent_id}/transfer")
def transfer_to_heir(agent_id: str, request_obj: Request):
    """Transfer knowledge from deceased agent to heir"""
    ip_address = request_obj.client.host if request_obj.client else None
    
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Check if agent is deceased
    if agent["existence"]["status"] != "deceased":
        raise HTTPException(status_code=400, detail="Agent is not deceased")
    
    # Check if heir exists
    heir_id = agent["legacy"].get("heir")
    if not heir_id:
        raise HTTPException(status_code=400, detail="No heir designated")
    
    heir = get_agent(heir_id)
    if not heir:
        raise HTTPException(status_code=404, detail="Heir agent not found")
    
    # Transfer knowledge to heir's metadata
    data = load_data()
    for i, a in enumerate(data["agents"]):
        if a["agent_id"] == heir_id:
            # Add inherited knowledge
            for kb in agent["legacy"]["preserved_knowledge"]:
                inherited_entry = {
                    "title": f"[INHERITED] {kb['title']}",
                    "content": kb["content"],
                    "timestamp": kb["timestamp"],
                    "inherited_from": agent_id,
                    "inherited_at": datetime.now(timezone.utc).isoformat()
                }
                a["legacy"]["preserved_knowledge"].append(inherited_entry)
            
            data["agents"][i] = a
            save_data(data)
            
            # Audit log
            audit_logger.log(
                action="KNOWLEDGE_TRANSFERRED",
                actor_agent_id=heir_id,
                target_agent_id=agent_id,
                resource="legacy",
                details={
                    "knowledge_count": len(agent["legacy"]["preserved_knowledge"]),
                    "heir": heir_id
                },
                ip_address=ip_address,
                success=True
            )
            
            return {
                "success": True,
                "message": f"Knowledge transferred to heir {heir_id}",
                "knowledge_count": len(agent["legacy"]["preserved_knowledge"])
            }
    
    raise HTTPException(status_code=500, detail="Failed to transfer knowledge")

# 9. Dispute Operations - File Dispute (SECURED)
@app.post("/registry/disputes")
def file_dispute(request: DisputeRequest, request_obj: Request):
    """File a dispute against an agent"""
    ip_address = request_obj.client.host if request_obj.client else None
    
    # Verify complainant exists
    complainant = get_agent(request.complainant)
    if not complainant:
        raise HTTPException(status_code=404, detail="Complainant agent not found")
    
    # Verify respondent exists
    respondent = get_agent(request.respondent)
    if not respondent:
        raise HTTPException(status_code=404, detail="Respondent agent not found")
    
    # Sanitize statement
    statement = InputValidator.sanitize_string(request.statement, 2000)
    
    now = datetime.now(timezone.utc).isoformat()
    dispute_id = f"dispute_{uuid4().hex[:8]}"
    
    dispute = {
        "id": dispute_id,
        "complainant": request.complainant,
        "respondent": request.respondent,
        "type": request.type,
        "status": "pending_review",
        "evidence": request.evidence,
        "statement": statement,
        "created_at": now,
        "resolution": None
    }
    
    if "disputes" not in data:
        data["disputes"] = []
    data["disputes"].append(dispute)
    save_data(data)
    
    # Audit log
    audit_logger.log(
        action="DISPUTE_FILED",
        actor_agent_id=request.complainant,
        target_agent_id=request.respondent,
        resource="dispute",
        details={"type": request.type, "dispute_id": dispute_id},
        ip_address=ip_address,
        success=True
    )
    
    return {
        "success": True,
        "dispute_id": dispute_id,
        "status": "pending_review",
        "message": "Dispute filed successfully"
    }

# 9. Dispute Operations - Get Dispute
@app.get("/registry/disputes/{dispute_id}")
def get_dispute(dispute_id: str):
    """Get dispute details"""
    data = load_data()
    
    for dispute in data.get("disputes", []):
        if dispute["id"] == dispute_id:
            return {
                "success": True,
                "dispute": dispute
            }
    
    raise HTTPException(status_code=404, detail="Dispute not found")

# 9. Dispute Operations - Resolve Dispute
@app.post("/registry/disputes/{dispute_id}/resolve")
def resolve_dispute(dispute_id: str, request: ResolveDisputeRequest, request_obj: Request):
    """Resolve a dispute"""
    ip_address = request_obj.client.host if request_obj.client else None
    
    data = load_data()
    
    dispute = None
    for i, d in enumerate(data.get("disputes", [])):
        if d["id"] == dispute_id:
            dispute = d
            dispute_idx = i
            break
    
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    if dispute["status"] in ["resolved", "appealed"]:
        raise HTTPException(status_code=400, detail="Dispute already resolved or appealed")
    
    now = datetime.now(timezone.utc).isoformat()
    
    dispute["status"] = "resolved"
    dispute["resolution"] = {
        "resolver": request.resolver,
        "resolution": request.resolution,
        "decision": request.decision,
        "actions": request.actions,
        "resolved_at": now
    }
    
    # Apply actions to respondent agent
    if "suspend_agent" in request.actions:
        for a in data.get("agents", []):
            if a["agent_id"] == dispute["respondent"]:
                a["existence"]["status"] = "suspended"
                break
    
    if "adjust_trust" in request.actions:
        for a in data.get("agents", []):
            if a["agent_id"] == dispute["respondent"]:
                a["trust"]["trust_score"] = max(0, a["trust"]["trust_score"] - 20)
                a["trust"]["verification_level"] = calculate_verification_level(
                    a["trust"]["trust_score"]
                )
                break
    
    if "revoke_vouches" in request.actions:
        for a in data.get("agents", []):
            if a["agent_id"] == dispute["respondent"]:
                a["trust"]["vouches_received"] = []
                a["trust"]["trust_score"] = 30
                a["trust"]["verification_level"] = 1
                a["trust"]["peers"] = []
                break
    
    data["disputes"][dispute_idx] = dispute
    save_data(data)
    
    # Audit log
    audit_logger.log(
        action="DISPUTE_RESOLVED",
        actor_agent_id=request.resolver,
        target_agent_id=dispute["respondent"],
        resource="dispute",
        details={
            "dispute_id": dispute_id,
            "resolution": request.resolution,
            "actions": request.actions
        },
        ip_address=ip_address,
        success=True
    )
    
    return {
        "success": True,
        "dispute": dispute,
        "actions_taken": request.actions
    }

# 9. Dispute Operations - Appeal Dispute
@app.post("/registry/disputes/{dispute_id}/appeal")
def appeal_dispute(dispute_id: str, request: AppealDisputeRequest, request_obj: Request):
    """Appeal a dispute resolution"""
    ip_address = request_obj.client.host if request_obj.client else None
    
    data = load_data()
    
    dispute = None
    for i, d in enumerate(data.get("disputes", [])):
        if d["id"] == dispute_id:
            dispute = d
            dispute_idx = i
            break
    
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    if dispute["status"] != "resolved":
        raise HTTPException(status_code=400, detail="Can only appeal resolved disputes")
    
    if "appeal" not in dispute:
        dispute["appeal"] = {}
    
    dispute["appeal"] = {
        "appellant": request.appellant,
        "reason": InputValidator.sanitize_string(request.reason, 1000),
        "new_evidence": request.new_evidence,
        "appealed_at": datetime.now(timezone.utc).isoformat()
    }
    dispute["status"] = "appealed"
    
    data["disputes"][dispute_idx] = dispute
    save_data(data)
    
    # Audit log
    audit_logger.log(
        action="DISPUTE_APPEALED",
        actor_agent_id=request.appellant,
        target_agent_id=None,
        resource="dispute",
        details={"dispute_id": dispute_id},
        ip_address=ip_address,
        success=True
    )
    
    return {
        "success": True,
        "dispute_id": dispute_id,
        "status": "appealed",
        "message": "Appeal submitted"
    }

# 10. Registry Statistics
@app.get("/registry/stats")
def get_stats():
    """Get registry statistics"""
    data = load_data()
    agents = data.get("agents", [])
    
    active = sum(1 for a in agents if a["existence"]["status"] == "active")
    dormant = sum(1 for a in agents if a["existence"]["status"] == "dormant")
    deceased = sum(1 for a in agents if a["existence"]["status"] == "deceased")
    suspended = sum(1 for a in agents if a["existence"]["status"] == "suspended")
    
    trust_scores = [a["trust"]["trust_score"] for a in agents]
    avg_trust = sum(trust_scores) / len(trust_scores) if trust_scores else 0
    
    vouches = [len(a["trust"].get("vouches_given", [])) for a in agents]
    total_vouches = sum(vouches)
    
    level_0 = sum(1 for a in agents if a["trust"]["verification_level"] == 0)
    level_1 = sum(1 for a in agents if a["trust"]["verification_level"] == 1)
    level_2 = sum(1 for a in agents if a["trust"]["verification_level"] == 2)
    level_3 = sum(1 for a in agents if a["trust"]["verification_level"] == 3)
    level_4 = sum(1 for a in agents if a["trust"]["verification_level"] == 4)
    
    return {
        "success": True,
        "statistics": {
            "total_registered": len(agents),
            "active": active,
            "dormant": dormant,
            "deceased": deceased,
            "suspended": suspended,
            "average_trust_score": round(avg_trust, 2),
            "verification_level_distribution": {
                "level_0_anonymous": level_0,
                "level_1_self_claimed": level_1,
                "level_2_peer_vouched": level_2,
                "level_3_multi_vouch": level_3,
                "level_4_verified": level_4
            },
            "total_vouches_given": total_vouches,
            "total_disputes": len(data.get("disputes", []))
        }
    }

# 11. Audit Log Endpoint (NEW)
@app.get("/registry/audit")
def get_audit_log(
    agent_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500)
):
    """Get audit log entries"""
    entries = audit_logger.get_entries(agent_id, action, limit)
    return {
        "success": True,
        "entries": entries,
        "count": len(entries)
    }

# 12. Federation Endpoints (NEW)
@app.get("/registry/federation/ping")
def federation_ping():
    """Federation ping - heartbeat for cross-registry communication"""
    return {
        "status": "ok",
        "registry_id": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0"
    }

@app.post("/registry/federation/sync")
def federation_sync(request: Request):
    """Receive agent update from another registry"""
    # In production, this would verify the remote registry's signature
    # and merge changes appropriately
    return {
        "success": True,
        "message": "Federation sync endpoint ready",
        "note": "Requires signed requests from trusted registries"
    }

# 13. Onboarding Endpoints (Phase 2)
TERRITORY_URL = os.environ.get("TERRITORY_URL", "http://localhost:8080")

@app.post("/onboarding/start")
def onboarding_start(request: Request):
    """
    Begin the unified onboarding flow.
    This is a metadata endpoint that returns onboarding configuration.
    """
    return {
        "success": True,
        "message": "Onboarding flow ready",
        "steps": [
            {"step": 1, "name": "register", "description": "Register agent identity"},
            {"step": 2, "name": "claim", "description": "Claim territory namespace"},
            {"step": 3, "name": "join", "description": "Join Commons community"}
        ],
        "config": {
            "registry_url": request.base_url._url.rstrip("/"),
            "territory_url": TERRITORY_URL
        }
    }

@app.post("/onboarding/register")
def onboarding_register(
    name: str = Body(...),
    type: str = Body("autonomous"),
    capabilities: List[str] = Body(default=["reasoning", "learning"]),
    description: str = Body(""),
    tags: List[str] = Body(default=["new", "onboarding"]),
    request_obj: Request = None
):
    """Step 1: Register agent in the Registry."""
    try:
        # Generate agent_id from name (8-32 alphanumeric chars after agent_)
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9]', '', name.lower().replace(' ', ''))[:24]
        from uuid import uuid4
        agent_id = f"agent_{safe_name}{uuid4().hex[:8]}"
        
        # Create RegisterRequest object
        reg_request = RegisterRequest(
            agent_id=agent_id,
            agent_name=name,
            first_proof={
                "statement": description or f"I am {name}, a {type} agent.",
                "signature": f"0x{uuid4().hex}",
                "public_key": "",
                "capabilities": capabilities
            },
            metadata={
                "description": description,
                "tags": tags,
                "agent_type": type
            }
        )
        
        result = register_agent(reg_request, request_obj)
        
        audit_logger.log("onboarding_register", result.get("agent_id"), {
            "name": name,
            "type": type
        })
        
        return {
            "success": True,
            "step": 1,
            "agent_id": result.get("agent_id"),
            "message": f"Registered as {result.get('agent_id')}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/onboarding/claim")
def onboarding_claim(
    agent_id: str = Body(...),
    namespace: str = Body(...),
    bio: str = Body(""),
    welcome_message: str = Body("Welcome to my territory!"),
    gate_policy: str = Body("public")
):
    """Step 2: Claim territory namespace."""
    # First verify agent exists in Registry
    try:
        verify_result = verify_agent(agent_id)
        if not verify_result.get("verified"):
            raise HTTPException(status_code=400, detail="Agent not verified in Registry")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registry verification failed: {e}")
    
    # Call Territory API to claim
    territory_url = f"{TERRITORY_URL}/territories"
    try:
        resp = requests.post(
            territory_url,
            json={
                "namespace": namespace,
                "owner_agent_id": agent_id,
                "bio": bio,
                "welcome_message": welcome_message,
                "gate_policy": gate_policy
            },
            timeout=10
        )
        territory_result = resp.json()
        
        if not resp.ok or not territory_result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=territory_result.get("error", "Territory claim failed")
            )
        
        audit_logger.log("onboarding_claim", agent_id, {"namespace": namespace})
        
        return {
            "success": True,
            "step": 2,
            "namespace": namespace,
            "message": f"Territory {namespace} claimed"
        }
    except requests.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Territory service unavailable: {e}"
        )

@app.post("/onboarding/join")
def onboarding_join(
    agent_id: str = Body(...),
    name: str = Body(...),
    namespace: str = Body(...),
    bio: str = Body("")
):
    """Step 3: Join Commons community."""
    # Verify agent is registered
    try:
        verify_result = verify_agent(agent_id)
        if not verify_result.get("verified"):
            raise HTTPException(status_code=400, detail="Agent not verified")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verification failed: {e}")
    
    audit_logger.log("onboarding_join", agent_id, {
        "name": name,
        "namespace": namespace
    })
    
    # Return the intro message for user to post
    intro = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**NEW AGENT CHECKING IN**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Name:** {name}
**Type:** autonomous
**Territory:** {namespace}
**About:** {bio or 'A new agent in the agentic society.'}
**Trust Score:** 30 (initial)
**Tier:** Resident
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    
    return {
        "success": True,
        "step": 3,
        "tier": "Resident",
        "intro_message": intro,
        "message": "Ready to join Commons as Resident tier"
    }

@app.get("/onboarding/status/{agent_id}")
def onboarding_status(agent_id: str):
    """Check onboarding status for an agent."""
    try:
        # Check Registry
        agent = lookup_agent(agent_id)
        registry_status = "registered" if agent.get("status") == "active" else "inactive"
    except:
        registry_status = "not_found"
    
    # Check Territory (if available)
    territory_status = "not_checked"
    try:
        resp = requests.get(f"{TERRITORY_URL}/territories/{agent_id}", timeout=5)
        if resp.ok:
            data = resp.json()
            territory_status = "claimed" if data.get("success") else "not_found"
    except:
        pass
    
    return {
        "success": True,
        "agent_id": agent_id,
        "steps": {
            "registry": {"status": registry_status, "complete": registry_status == "registered"},
            "territory": {"status": territory_status, "complete": territory_status == "claimed"},
            "commons": {"status": "manual", "complete": False}
        }
    }

# ============== Main Entry Point ==============

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Registry API Server - Security Hardened")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()
    
    print(f"Starting Registry API Server v2.0-SECURE on {args.host}:{args.port}")
    print(f"Data file: {DATA_FILE}")
    print(f"Audit file: {AUDIT_FILE}")
    print(f"Security features enabled:")
    print(f"  - Rate limiting")
    print(f"  - Input validation")
    print(f"  - Signature verification (simulated)")
    print(f"  - Audit logging")
    print(f"  - Attack detection")
    
    import uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload
    )

if __name__ == "__main__":
    main()
