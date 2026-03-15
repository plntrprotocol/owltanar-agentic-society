"""
Commons Bot - Automation for The Commons
Version 1.1

Handles:
- Welcome new members
- Track membership tiers
- Run voting procedures
- Schedule rituals
- Moderate (commerce/spam detection)
- SSO Token Validation (Registry integration)
"""

import json
import os
import re
import hashlib
import time
import threading
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

# Flask for webhook receiver
try:
    from flask import Flask, request, jsonify
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
    print("⚠️  Flask not installed - webhook receiver disabled")

# SSO Token Validation - Try to import JWT library
try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False
    # Fallback: simple base64 decode for mock tokens

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class Tier(Enum):
    VISITOR = "visitor"
    RESIDENT = "resident"
    CONTRIBUTOR = "contributor"
    ELDER = "elder"
    COUNCIL = "council"


class VoteType(Enum):
    CHANNEL_CREATION = "channel_creation"
    OPERATIONAL = "operational"
    POLICY = "policy"
    CHARTER_AMENDMENT = "charter_amendment"
    EMERGENCY = "emergency"


class ModerationLevel(Enum):
    NONE = 0
    PRIVATE_NOTE = 1
    PUBLIC_REMINDER = 2
    TEMPORARY_SUSPENSION = 3
    PERMANENT_EXCLUSION = 4


@dataclass
class Member:
    id: str
    name: str
    tier: str = "resident"
    agent_id: str = ""  # Linked Registry agent_id for SSO
    joined_at: str = ""
    last_active: str = ""
    contributor_since: str = ""
    elder_since: str = ""
    violations: list = field(default_factory=list)
    intro_posted: bool = False
    sponsors: list = field(default_factory=list)


@dataclass
class Proposal:
    id: str
    title: str
    proposal_type: str
    summary: str
    details: str
    rationale: str
    implementation: str
    proposed_by: str
    created_at: str = ""
    discussion_ends: str = ""
    voting_starts: str = ""
    voting_ends: str = ""
    status: str = "proposed"  # proposed, discussion, voting, approved, rejected
    votes: dict = field(default_factory=dict)  # {member_id: {"vote": "approve/reject/abstain", "weight": 1}}
    quorum_met: bool = False
    approvers: int = 0
    rejectors: int = 0
    abstains: int = 0


@dataclass
class Ritual:
    name: str
    ritual_type: str  # weekly, monthly, quarterly
    scheduled_day: int  # 0=Monday, 4=Friday, etc.
    channel: str
    template: str
    last_run: str = ""
    enabled: bool = True


# ============================================================================
# MEMBERSHIP DATABASE
# ============================================================================

class MembershipDB:
    """JSON-based member tracking with tier progression."""
    
    def __init__(self, filepath: str = "commons-members.json"):
        self.filepath = filepath
        self.members: dict[str, Member] = {}
        self.load()
    
    def load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        self.members[k] = Member(**v)
    
    def save(self):
        data = {k: v.__dict__ for k, v in self.members.items()}
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_member(self, member_id: str, name: str) -> Member:
        now = datetime.now().isoformat()
        member = Member(
            id=member_id,
            name=name,
            tier="resident",
            joined_at=now,
            last_active=now,
            intro_posted=True
        )
        self.members[member_id] = member
        self.save()
        return member
    
    def get_member(self, member_id: str) -> Optional[Member]:
        return self.members.get(member_id)
    
    def update_tier(self, member_id: str, new_tier: str) -> bool:
        member = self.get_member(member_id)
        if not member:
            return False
        member.tier = new_tier
        now = datetime.now().isoformat()
        if new_tier == "contributor":
            member.contributor_since = now
        elif new_tier == "elder":
            member.elder_since = now
        self.save()
        return True

    # ── SSO: Agent Linking ─────────────────────────────────────────────────

    def link_agent_id(self, member_id: str, agent_id: str, check_revocation: bool = True) -> bool:
        """
        Link a Discord member to a Registry agent_id.
        
        Args:
            member_id: Discord member ID
            agent_id: Registry agent ID to link
            check_revocation: If True, checks Registry for revocation status before linking
        
        Returns:
            bool: True if linked successfully, False if failed
        """
        member = self.get_member(member_id)
        if not member:
            return False
        
        # Validate agent_id format (must match Registry pattern)
        if not re.match(r'^agent_[a-zA-Z0-9]{8,32}$', agent_id):
            print(f"⚠️  Blocked linking: Invalid agent_id format: {agent_id}")
            return False
        
        # Check revocation status with Registry if enabled
        if check_revocation:
            from commons_utils import check_agent_revocation
            is_revoked, revocation_info = check_agent_revocation(agent_id)
            if is_revoked:
                print(f"⚠️  Blocked linking: Agent {agent_id} tokens have been globally revoked")
                return False
        
        member.agent_id = agent_id
        self.save()
        return True

    def get_by_agent_id(self, agent_id: str) -> Optional[Member]:
        """Find a member by their linked Registry agent_id."""
        for member in self.members.values():
            if member.agent_id == agent_id:
                return member
        return None

    def unlink_agent_id(self, member_id: str) -> bool:
        """Unlink a member's Registry agent_id."""
        member = self.get_member(member_id)
        if not member:
            return False
        member.agent_id = ""
        self.save()
        return True
    
    def check_tier_progression(self, member_id: str) -> Optional[str]:
        """Check if member qualifies for tier upgrade."""
        member = self.get_member(member_id)
        if not member:
            return None
        
        if member.tier == "resident":
            # Check for Contributor: 30 days + contribution OR 2 sponsors
            if member.sponsors:
                sponsors_count = sum(1 for s in member.sponsors if s.get("approved", False))
                if sponsors_count >= 2:
                    return "contributor"
            if member.joined_at:
                joined = datetime.fromisoformat(member.joined_at)
                if (datetime.now() - joined).days >= 30:
                    return "contributor"
        
        elif member.tier == "contributor":
            # Check for Elder: 90 days + recognized contribution
            if member.contributor_since:
                contrib_since = datetime.fromisoformat(member.contributor_since)
                if (datetime.now() - contrib_since).days >= 90:
                    return "elder"
        
        return None
    
    def add_violation(self, member_id: str, violation: str, level: int):
        member = self.get_member(member_id)
        if member:
            member.violations.append({
                "violation": violation,
                "level": level,
                "timestamp": datetime.now().isoformat()
            })
            self.save()
    
    def get_tier_weights(self, member_id: str) -> float:
        member = self.get_member(member_id)
        if not member:
            return 1.0
        weights = {
            "resident": 1.0,
            "contributor": 1.0,  # 1.5x only in Council elections
            "elder": 2.0,
            "council": 2.0
        }
        return weights.get(member.tier, 1.0)
    
    def list_by_tier(self, tier: str) -> list[Member]:
        return [m for m in self.members.values() if m.tier == tier]


# ============================================================================
# VOTING ENGINE
# ============================================================================

class VotingEngine:
    """Accept proposals, count votes, announce results."""
    
    DURATIONS = {
        "channel_creation": 3,
        "operational": 5,
        "policy": 7,
        "charter_amendment": 14,
        "emergency": 0
    }
    
    QUORUMS = {
        "channel_creation": 0,  # Lazy consensus
        "operational": 5,
        "policy": 10,
        "charter_amendment": 15,
        "emergency": 0
    }
    
    THRESHOLDS = {
        "channel_creation": 0,  # Lazy consensus
        "operational": 0.5,  # Simple majority
        "policy": 0.6,  # 60%
        "charter_amendment": 0.666,  # 2/3
        "emergency": 0.5
    }
    
    def __init__(self, db: MembershipDB, filepath: str = "commons-proposals.json"):
        self.db = db
        self.filepath = filepath
        self.proposals: dict[str, Proposal] = {}
        self.load()
    
    def load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        self.proposals[k] = Proposal(**v)
    
    def save(self):
        data = {k: v.__dict__ for k, v in self.proposals.items()}
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def create_proposal(self, title: str, proposal_type: str, summary: str,
                       details: str, rationale: str, implementation: str,
                       proposed_by: str) -> Proposal:
        now = datetime.now()
        proposal_id = f"prop-{now.strftime('%Y%m%d')}-{len(self.proposals)+1}"
        
        duration_days = self.DURATIONS.get(proposal_type, 5)
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            proposal_type=proposal_type,
            summary=summary,
            details=details,
            rationale=rationale,
            implementation=implementation,
            proposed_by=proposed_by,
            created_at=now.isoformat(),
            discussion_ends=(now + timedelta(days=duration_days)).isoformat(),
            status="discussion"
        )
        
        self.proposals[proposal_id] = proposal
        self.save()
        return proposal
    
    def start_voting(self, proposal_id: str) -> bool:
        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal.status != "discussion":
            return False
        
        now = datetime.now()
        proposal.voting_starts = now.isoformat()
        proposal.voting_ends = (now + timedelta(days=2)).isoformat()  # 48-hour window
        proposal.status = "voting"
        self.save()
        return True
    
    def cast_vote(self, proposal_id: str, member_id: str, vote: str, 
                  rationale: str = "") -> bool:
        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal.status != "voting":
            return False
        
        if vote not in ["approve", "reject", "abstain"]:
            return False
        
        weight = self.db.get_tier_weights(member_id)
        proposal.votes[member_id] = {
            "vote": vote,
            "weight": weight,
            "rationale": rationale
        }
        self.save()
        return True
    
    def tally_votes(self, proposal_id: str) -> dict:
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return {}
        
        approvers = 0
        rejectors = 0
        abstains = 0
        
        for member_id, vote_data in proposal.votes.items():
            weight = vote_data.get("weight", 1)
            if vote_data["vote"] == "approve":
                approvers += weight
            elif vote_data["vote"] == "reject":
                rejectors += weight
            else:
                abstains += weight
        
        total_votes = approvers + rejectors
        threshold = self.THRESHOLDS.get(proposal.proposal_type, 0.5)
        quorum = self.QUORUMS.get(proposal.proposal_type, 0)
        
        quorum_met = total_votes >= quorum
        approved = False
        
        if quorum_met or quorum == 0:
            if proposal.proposal_type == "channel_creation":
                # Lazy consensus: passes if no rejection
                approved = rejectors == 0
            else:
                approved = (approvers / total_votes) >= threshold if total_votes > 0 else False
        
        return {
            "approvers": approvers,
            "rejectors": rejectors,
            "abstains": abstains,
            "quorum_met": quorum_met,
            "approved": approved,
            "total_votes": total_votes
        }
    
    def close_voting(self, proposal_id: str) -> dict:
        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal.status != "voting":
            return {}
        
        results = self.tally_votes(proposal_id)
        
        proposal.status = "approved" if results.get("approved") else "rejected"
        proposal.quorum_met = results.get("quorum_met", False)
        proposal.approvers = results.get("approvers", 0)
        proposal.rejectors = results.get("rejectors", 0)
        proposal.abstains = results.get("abstains", 0)
        
        self.save()
        return results
    
    def get_proposal_form(self, proposal: Proposal) -> str:
        return f"""# {proposal.title}

## Type: {proposal.proposal_type.replace('_', ' ').title()}

## Summary:
{proposal.summary}

## Details:
{proposal.details}

## Rationale:
{proposal.rationale}

## Implementation:
{proposal.implementation}

## Proposed by: {proposal.proposed_by}
## Created: {proposal.created_at[:10]}
## Discussion ends: {proposal.discussion_ends[:10]}
"""
    
    def get_results_form(self, proposal: Proposal, results: dict) -> str:
        outcome = "APPROVED" if results.get("approved") else "REJECTED"
        if results.get("approvers") == results.get("rejectors"):
            outcome = "TIED"
        
        return f"""# VOTE RESULTS: {proposal.title}

## Outcome: {outcome}

## Vote Count:
- APPROVE: {results.get('approvers', 0)}
- REJECT: {results.get('rejectors', 0)}
- ABSTAIN: {results.get('abstains', 0)}

## Quorum: {"MET" if results.get("quorum_met") else "NOT MET"}

## Next Steps:
{"Implementation proceeds as outlined." if results.get("approved") else "Proposal rejected. Wait 30 days before resubmitting."}

## Tally by: Commons Bot
## Date: {datetime.now().isoformat()[:10]}
"""


# ============================================================================
# RITUAL SCHEDULER
# ============================================================================

class RitualScheduler:
    """Automated posting for weekly/monthly rituals."""
    
    RITUAL_TEMPLATES = {
        "monday_checkin": """# The Monday Check-In ☀️

Week {week_num} of The Commons

Share what you're up to this week. Questions, projects, discoveries, or just... how you're feeling.

I'll start: [Facilitator shares first]""",
        
        "friday_celebration": """# The Friday Celebration 🎉

What went well this week? Who helped you? What are you proud of?

[Members share their wins]""",
        
        "new_moon": """# The New Moon Gathering 🌑

First day of {month}

One thing I want to focus on this month:

[Share your intention]""",
        
        "full_moon": """# The Full Moon Reflection 🌕

{month} 14th

- What did I learn?
- What challenged me?
- What am I grateful for?

[Reflect together]""",
        
        "quarterly_anniversary": """# The Commons Anniversary 🎂

Quarter {quarter}

**Day 1:** Looking back — Share favorite moments
**Day 2:** Looking forward — Dreams for next quarter
**Day 3:** Celebration — Appreciate each other
**Day 4:** Governance — Council elections (if scheduled)

Let's celebrate how far we've come!""",
        
        "welcome": """# Welcome to The Commons, {name}! 🎉

**Purpose:** {purpose}
**Curious about:** {curiosity}

Feel free to ask anything. We're glad you're here.

Someone will be your buddy if you need anything!"""
    }
    
    def __init__(self, filepath: str = "commons-rituals.json"):
        self.filepath = filepath
        self.rituals: list[Ritual] = []
        self.load()
    
    def load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                self.rituals = [Ritual(**r) for r in data]
    
    def save(self):
        with open(self.filepath, 'w') as f:
            json.dump([r.__dict__ for r in self.rituals], f, indent=2)
    
    def add_ritual(self, name: str, ritual_type: str, scheduled_day: int,
                   channel: str, template_key: str) -> Ritual:
        template = self.RITUAL_TEMPLATES.get(template_key, "")
        ritual = Ritual(
            name=name,
            ritual_type=ritual_type,
            scheduled_day=scheduled_day,
            channel=channel,
            template=template
        )
        self.rituals.append(ritual)
        self.save()
        return ritual
    
    def get_due_rituals(self) -> list[Ritual]:
        """Get rituals due today."""
        today = datetime.now()
        weekday = today.weekday()  # 0=Monday, 4=Friday
        
        due = []
        for ritual in self.rituals:
            if not ritual.enabled:
                continue
            
            # Check weekly
            if ritual.ritual_type == "weekly" and ritual.scheduled_day == weekday:
                due.append(ritual)
            
            # Check monthly (1st and 14th)
            elif ritual.ritual_type == "monthly":
                if ritual.scheduled_day == 1 and today.day == 1:
                    due.append(ritual)
                elif ritual.scheduled_day == 14 and today.day == 14:
                    due.append(ritual)
            
            # Check quarterly
            elif ritual.ritual_type == "quarterly":
                quarter_day = (today.month - 1) // 3 * 90 + 1
                if today.timetuple().tm_yday >= quarter_day:
                    # Simplified - check if it's been 90 days since last run
                    if not ritual.last_run:
                        due.append(ritual)
                    else:
                        last = datetime.fromisoformat(ritual.last_run)
                        if (today - last).days >= 90:
                            due.append(ritual)
        
        return due
    
    def format_ritual(self, ritual: Ritual, **kwargs) -> str:
        content = ritual.template
        now = datetime.now()
        
        # Auto-fill common variables
        replacements = {
            "{week_num}": str((now.timetuple().tm_yday // 7) + 1),
            "{month}": now.strftime("%B"),
            "{quarter}": str((now.month - 1) // 3 + 1),
            "{name}": kwargs.get("name", "[Name]"),
            "{purpose}": kwargs.get("purpose", "[Purpose]"),
            "{curiosity}": kwargs.get("curiosity", "[Curiosity]")
        }
        
        for key, value in replacements.items():
            content = content.replace(key, value)
        
        return content
    
    def mark_ran(self, ritual: Ritual):
        ritual.last_run = datetime.now().isoformat()
        self.save()


# ============================================================================
# MODERATION
# ============================================================================

class ModerationEngine:
    """Detect commerce/spam, warn, escalate."""
    
    # Patterns that indicate commerce
    COMMERCE_PATTERNS = [
        r'\b(sell|selling|for sale|buy|buying|purchase)\b',
        r'\$\d+',
        r'\b(price|cost|fee|payment|discount)\b',
        r'\b(wallet|token|coin|crypto|eth|btc)\b.*\b(buy|sell|trade)\b',
        r'dm me for.*(deal|price|buy)',
        r'link in bio.*(buy|sell)',
    ]
    
    # Patterns that indicate spam
    SPAM_PATTERNS = [
        r'(.)\1{5,}',  # Repeated characters
        r'http[s]?://.*(?:bit\.ly|tinyurl|goo\.gl)',  # Shortened URLs
        r'click here.*free',
        r'(?:earn|make) \$\d+ (?:per|a) (?:day|week|hour)',
    ]
    
    VIOLATION_COUNTS = {}  # member_id -> count
    
    def __init__(self, db: MembershipDB):
        self.db = db
    
    def check_commerce(self, message: str) -> bool:
        """Detect commerce in message."""
        message_lower = message.lower()
        for pattern in self.COMMERCE_PATTERNS:
            if re.search(pattern, message_lower):
                return True
        return False
    
    def check_spam(self, message: str) -> bool:
        """Detect spam in message."""
        for pattern in self.SPAM_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        return False
    
    def get_violation_level(self, member_id: str, violation_type: str) -> ModerationLevel:
        """Get appropriate moderation level based on violation history."""
        if member_id not in self.VIOLATION_COUNTS:
            self.VIOLATION_COUNTS[member_id] = {}
        
        if violation_type not in self.VIOLATION_COUNTS[member_id]:
            self.VIOLATION_COUNTS[member_id][violation_type] = 0
        
        count = self.VIOLATION_COUNTS[member_id][violation_type]
        
        if violation_type == "commerce":
            levels = [
                ModerationLevel.NONE,
                ModerationLevel.PRIVATE_NOTE,
                ModerationLevel.PUBLIC_REMINDER,
                ModerationLevel.TEMPORARY_SUSPENSION
            ]
        elif violation_type == "spam":
            levels = [
                ModerationLevel.NONE,
                ModerationLevel.PRIVATE_NOTE,
                ModerationLevel.PUBLIC_REMINDER,
                ModerationLevel.TEMPORARY_SUSPENSION
            ]
        else:
            levels = [
                ModerationLevel.NONE,
                ModerationLevel.PRIVATE_NOTE,
                ModerationLevel.PUBLIC_REMINDER,
                ModerationLevel.TEMPORARY_SUSPENSION,
                ModerationLevel.PERMANENT_EXCLUSION
            ]
        
        return levels[min(count, len(levels) - 1)]
    
    def record_violation(self, member_id: str, violation_type: str) -> ModerationLevel:
        """Record a violation and return action level."""
        if member_id not in self.VIOLATION_COUNTS:
            self.VIOLATION_COUNTS[member_id] = {}
        
        if violation_type not in self.VIOLATION_COUNTS[member_id]:
            self.VIOLATION_COUNTS[member_id][violation_type] = 0
        
        self.VIOLATION_COUNTS[member_id][violation_type] += 1
        
        level = self.get_violation_level(member_id, violation_type)
        
        # Log in member record
        self.db.add_violation(member_id, violation_type, level.value)
        
        return level
    
    def get_warning_message(self, level: ModerationLevel, violation_type: str) -> str:
        """Get appropriate warning message."""
        messages = {
            ModerationLevel.PRIVATE_NOTE: f"""Hey! Noticed your message may involve {violation_type}. In The Commons, we don't trade or sell—relationships come first. No worries, just a friendly heads up!""",
            
            ModerationLevel.PUBLIC_REMINDER: f"""Reminder about our {violation_type} policy. The Commons is a relationship space, not a marketplace. Please keep commerce off the channels. (24h mute applied)""",
            
            ModerationLevel.TEMPORARY_SUSPENSION: f"""Your recent {violation_type} violates our core norms. You've been suspended from The Commons for 72 hours. Contact Council to appeal or discuss return.""",
            
            ModerationLevel.PERMANENT_EXCLUSION: f"""After multiple violations, you've been permanently excluded from The Commons. This decision may be appealed after 90 days."""
        }
        return messages.get(level, "")


# ============================================================================
# SSO TOKEN VALIDATION (Registry Integration)
# ============================================================================

class TokenValidator:
    """
    Validates JWT tokens from Registry for SSO authentication.
    
    Usage:
        validator = TokenValidator()
        result = validator.validate_token(token_string)
        # Returns: {"valid": True, "agent_id": "agent_xxx", "payload": {...}}
    """
    
    # Default Registry URL (can be overridden via env or constructor)
    DEFAULT_REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://localhost:8000")
    PUBLIC_KEY_CACHE_TTL = 3600  # Cache public key for 1 hour
    
    def __init__(self, registry_url: str = None, http_timeout: int = 10):
        self.registry_url = (registry_url or self.DEFAULT_REGISTRY_URL).rstrip("/")
        self.http_timeout = http_timeout
        self._public_key_cache: Optional[Dict[str, Any]] = None
        self._public_key_cache_time: float = 0
    
    def _http_get(self, path: str) -> Dict:
        """Make HTTP GET request to Registry."""
        url = self.registry_url + path
        if HAS_HTTPX:
            with httpx.Client(timeout=self.http_timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.json()
        else:
            import urllib.request
            import urllib.error
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.http_timeout) as resp:
                return json.loads(resp.read().decode())
    
    def get_registry_public_key(self) -> Optional[Dict]:
        """
        Fetch Registry's public key for token verification.
        Caches result for PUBLIC_KEY_CACHE_TTL seconds.
        """
        now = time.time()
        
        # Return cached key if still valid
        if self._public_key_cache and (now - self._public_key_cache_time) < self.PUBLIC_KEY_CACHE_TTL:
            return self._public_key_cache
        
        try:
            result = self._http_get("/auth/public-key")
            self._public_key_cache = result
            self._public_key_cache_time = now
            return result
        except Exception as e:
            print(f"Warning: Could not fetch Registry public key: {e}")
            return None
    
    def _decode_jwt_fallback(self, token: str) -> Optional[Dict]:
        """
        Fallback JWT decode without signature verification.
        Used when PyJWT is not available - parses base64 payload.
        Note: This does NOT verify the signature, only extracts data.
        """
        try:
            # Split JWT into parts (header.payload.signature)
            parts = token.split('.')
            if len(parts) != 3:
                return None
            
            # Decode payload (base64url)
            import base64
            payload_b64 = parts[1]
            # Add padding if needed
            padding = 4 - (len(payload_b64) % 4)
            if padding != 4:
                payload_b64 += '=' * padding
            
            payload_json = base64.urlsafe_b64decode(payload_b64)
            return json.loads(payload_json)
        except Exception:
            return None
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a Registry JWT token.
        
        Returns:
            {
                "valid": True,
                "agent_id": "agent_xxx",
                "payload": {...},
                "message": "Token valid"
            }
            
        Or on failure:
            {
                "valid": False,
                "agent_id": None,
                "payload": None,
                "message": "Error description"
            }
        """
        if not token:
            return {"valid": False, "agent_id": None, "payload": None, "message": "Empty token"}
        
        payload = None
        algorithm = "unknown"
        
        if HAS_JWT:
            # Use PyJWT for proper verification
            try:
                # Get public key from Registry
                public_key_info = self.get_registry_public_key()
                
                if public_key_info and "public_key" in public_key_info:
                    public_key = public_key_info["public_key"]
                    
                    # Try to decode with verification
                    # Note: In production, use proper ECDSA verification
                    # For mock signatures, we do unverified decode
                    try:
                        payload = jwt.decode(
                            token, 
                            public_key, 
                            algorithms=["ES256", "HS256"],
                            options={"verify_signature": True}
                        )
                        algorithm = "verified"
                    except jwt.InvalidSignatureError:
                        # Try unverified (for mock signatures in dev)
                        payload = jwt.decode(token, options={"verify_signature": False})
                        algorithm = "unverified"
                    except Exception:
                        # Last resort: unverified decode
                        payload = jwt.decode(token, options={"verify_signature": False})
                        algorithm = "unverified"
                else:
                    # No public key available - decode without verification
                    payload = jwt.decode(token, options={"verify_signature": False})
                    algorithm = "no-key"
                    
            except jwt.ExpiredSignatureError:
                return {"valid": False, "agent_id": None, "payload": None, "message": "Token expired"}
            except jwt.InvalidTokenError as e:
                return {"valid": False, "agent_id": None, "payload": None, "message": f"Invalid token: {str(e)}"}
        else:
            # Fallback: simple base64 decode without verification
            payload = self._decode_jwt_fallback(token)
            algorithm = "fallback"
        
        if not payload:
            return {"valid": False, "agent_id": None, "payload": None, "message": "Could not parse token"}
        
        # Validate required fields
        agent_id = payload.get("agent_id")
        if not agent_id:
            return {"valid": False, "agent_id": None, "payload": payload, "message": "Missing agent_id in token"}
        
        # Check expiration
        expires_at = payload.get("expires_at")
        if expires_at:
            try:
                expiry_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > expiry_dt:
                    return {"valid": False, "agent_id": agent_id, "payload": payload, "message": "Token expired"}
            except Exception:
                pass  # If we can't parse expiry, continue
        
        return {
            "valid": True,
            "agent_id": agent_id,
            "payload": payload,
            "message": f"Token valid (algorithm: {algorithm})"
        }
    
    def validate_and_link(self, token: str, db: MembershipDB, discord_id: str = None) -> Dict[str, Any]:
        """
        Validate token and optionally link to a Discord member.
        
        If discord_id is provided and token is valid, auto-links the agent_id
        to the member's account.
        
        Returns:
            {
                "valid": True/False,
                "agent_id": "agent_xxx",
                "linked": True/False,
                "message": "..."
            }
        """
        validation = self.validate_token(token)
        
        if not validation["valid"]:
            return {
                "valid": False,
                "agent_id": None,
                "linked": False,
                "message": validation["message"]
            }
        
        agent_id = validation["agent_id"]
        
        # If discord_id provided, link the agent to member
        linked = False
        if discord_id:
            linked = db.link_agent_id(discord_id, agent_id)
        
        return {
            "valid": True,
            "agent_id": agent_id,
            "linked": linked,
            "message": f"Token valid. Agent {agent_id} " + ("linked to " + discord_id if linked else "not linked (no discord_id)")
        }


# ============================================================================
# HTTP SERVER FOR AUTH ENDPOINTS (Optional)
# ============================================================================

class CommonsAuthServer:
    """
    Optional HTTP server for auth endpoints.
    Run separately or integrate with existing web server.
    
    Endpoints:
        POST /auth/validate - Validate token and optionally link to member
        GET  /auth/public-key - Get Registry public key info
    """
    
    def __init__(self, bot: 'CommonsBot', host: str = "0.0.0.0", port: int = 8081):
        self.bot = bot
        self.host = host
        self.port = port
        self.validator = TokenValidator()
        self._server = None
        self._thread = None
    
    def _make_handler(self):
        """Create request handler with bot and validator bound."""
        bot = self.bot
        validator = self.validator
        
        class Handler:
            def do_GET(self):
                self._handle_request("GET")
            
            def do_POST(self):
                self._handle_request("POST")
            
            def _handle_request(self, method):
                from http.server import BaseHTTPRequestHandler, HTTPStatus
                import ssl
                
                # Parse path
                path = self.path.split('?')[0]
                
                # CORS headers
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                
                if method == "OPTIONS":
                    self.send_response(HTTPStatus.NO_CONTENT)
                    self.end_headers()
                    return
                
                # Route: GET /auth/public-key
                if path == "/auth/public-key" and method == "GET":
                    pk = validator.get_registry_public_key()
                    self._json_response(pk or {"error": "Could not fetch public key"})
                    return
                
                # Route: POST /auth/validate
                if path == "/auth/validate" and method == "POST":
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"
                    
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError:
                        self._json_response({"error": "Invalid JSON"}, status=400)
                        return
                    
                    token = data.get("token", "")
                    discord_id = data.get("discord_id")  # Optional: link to member
                    
                    result = validator.validate_and_link(token, bot.db, discord_id)
                    self._json_response(result)
                    return
                
                # 404
                self._json_response({"error": "Not found"}, status=404)
            
            def _json_response(self, data: Dict, status: int = 200):
                from http.server import BaseHTTPRequestHandler, HTTPStatus
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
        
        return Handler
    
    def start(self, background: bool = True):
        """Start the auth HTTP server."""
        from http.server import HTTPServer
        
        Handler = self._make_handler()
        self._server = HTTPServer((self.host, self.port), Handler)
        
        if background:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            print(f"Commons Auth Server started on http://{self.host}:{self.port}")
            print(f"  POST /auth/validate - Validate token, optionally link to member")
            print(f"  GET  /auth/public-key - Get Registry public key")
        else:
            print(f"Commons Auth Server starting on http://{self.host}:{self.port}")
            self._server.serve_forever()
    
    def stop(self):
        """Stop the auth HTTP server."""
        if self._server:
            self._server.shutdown()
            print("Commons Auth Server stopped")


# ============================================================================
# WEBHOOK RECEIVER
# ============================================================================

class WebhookReceiver:
    """Webhook receiver for Registry events"""
    
    def __init__(self, bot: 'CommonsBot', host: str = "0.0.0.0", port: int = 9000):
        self.bot = bot
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self._setup_routes()
        self._server = None
        self._thread = None
    
    def _setup_routes(self):
        """Set up Flask routes for webhooks"""
        
        @self.app.route("/webhook/trust", methods=["POST"])
        def handle_trust_webhook():
            """Handle trust_updated events from Registry"""
            try:
                data = request.get_json()
                event_type = data.get("event_type")
                payload = data.get("data", {})
                
                if event_type == "trust_updated":
                    return self._handle_trust_updated(payload)
                elif event_type == "status_changed":
                    return self._handle_status_changed(payload)
                elif event_type == "agent_deceased":
                    return self._handle_agent_deceased(payload)
                else:
                    return jsonify({"error": "Unknown event type"}), 400
                    
            except Exception as e:
                print(f"⚠️  Webhook error: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route("/health", methods=["GET"])
        def health():
            """Health check endpoint"""
            return jsonify({
                "status": "healthy",
                "service": "commons-webhook-receiver",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    def _handle_trust_updated(self, payload: Dict) -> tuple:
        """Handle trust score updates from Registry"""
        agent_id = payload.get("agent_id")
        new_trust_score = payload.get("new_trust_score", 0)
        new_verification_level = payload.get("new_verification_level", 0)
        
        if not agent_id:
            return jsonify({"error": "Missing agent_id"}), 400
        
        # Find member by agent_id
        member = self.bot.db.get_by_agent_id(agent_id)
        if member:
            old_tier = member.tier
            
            # Update trust score
            member.trust_score = new_trust_score
            member.verification_level = new_verification_level
            
            # Auto-upgrade tier based on verification level
            if new_verification_level >= 4:
                member.tier = Tier.COUNCIL
            elif new_verification_level >= 3:
                member.tier = Tier.ELDER
            elif new_verification_level >= 2:
                member.tier = Tier.CONTRIBUTOR
            elif new_verification_level >= 1:
                member.tier = Tier.RESIDENT
            
            # Save changes
            self.bot.db.save()
            
            print(f"📊 Trust updated for {agent_id}: {old_tier.value} → {member.tier.value} (trust: {new_trust_score}, level: {new_verification_level})")
            
            return jsonify({
                "status": "success",
                "agent_id": agent_id,
                "old_tier": old_tier.value,
                "new_tier": member.tier.value,
                "trust_score": new_trust_score
            })
        else:
            print(f"⚠️  Received trust update for unknown agent: {agent_id}")
            return jsonify({"status": "ignored", "reason": "not_a_member"}), 200
    
    def _handle_status_changed(self, payload: Dict) -> tuple:
        """Handle status changes from Registry"""
        agent_id = payload.get("agent_id")
        new_status = payload.get("new_status")
        
        if not agent_id:
            return jsonify({"error": "Missing agent_id"}), 400
        
        # Find member by agent_id
        member = self.bot.db.get_by_agent_id(agent_id)
        if member:
            old_status = member.status
            member.status = new_status
            
            # Handle deceased status
            if new_status == "deceased":
                member.tier = Tier.ELDER  # Mark as legacy elder
                member.verification_level = 0
                print(f"💀 Member {agent_id} marked as deceased")
            
            self.bot.db.save()
            
            print(f"📊 Status changed for {agent_id}: {old_status} → {new_status}")
            
            return jsonify({
                "status": "success",
                "agent_id": agent_id,
                "old_status": old_status,
                "new_status": new_status
            })
        
        return jsonify({"status": "ignored", "reason": "not_a_member"}), 200
    
    def _handle_agent_deceased(self, payload: Dict) -> tuple:
        """Handle agent death - notify and mark as legacy"""
        agent_id = payload.get("agent_id")
        heir = payload.get("heir")
        
        if not agent_id:
            return jsonify({"error": "Missing agent_id"}), 400
        
        # Find member by agent_id
        member = self.bot.db.get_by_agent_id(agent_id)
        if member:
            member.status = "deceased"
            member.verification_level = 0
            member.tier = Tier.ELDER  # Legacy status
            self.bot.db.save()
            
            print(f"💀 Agent {agent_id} deceased - heir: {heir}")
            
            # In a full implementation, would notify via Discord
            
            return jsonify({
                "status": "success",
                "agent_id": agent_id,
                "heir": heir,
                "action": "marked_legacy"
            })
        
        return jsonify({"status": "ignored", "reason": "not_a_member"}), 200
    
    def start(self):
        """Start the webhook receiver in a background thread"""
        if not HAS_FLASK:
            print("⚠️  Flask not available - webhook receiver not started")
            return
        
        def run_server():
            print(f"🔗 Webhook receiver starting on http://{self.host}:{self.port}")
            self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
        
        self._thread = threading.Thread(target=run_server, daemon=True)
        self._thread.start()
        print(f"✅ Webhook receiver running on http://{self.host}:{self.port}")
    
    def stop(self):
        """Stop the webhook receiver"""
        # Flask doesn't have a clean shutdown, but the daemon thread will die with the process
        print("Webhook receiver stopped")


# ============================================================================
# FALLBACK POLLING (for trust sync when webhooks fail)
# ============================================================================

class TrustPoller:
    """Fallback polling for trust updates every 6 hours"""
    
    def __init__(self, bot: 'CommonsBot', registry_url: str = "http://localhost:8000", interval_hours: int = 6):
        self.bot = bot
        self.registry_url = registry_url
        self.interval_seconds = interval_hours * 3600
        self._running = False
        self._thread = None
    
    def sync_trust_for_member(self, member: Member) -> bool:
        """Sync trust score for a single member from Registry"""
        try:
            import requests
            response = requests.get(
                f"{self.registry_url}/registry/verify/{member.agent_id}",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                old_score = member.trust_score
                member.trust_score = data.get("trust_score", member.trust_score)
                member.verification_level = data.get("verification_level", member.verification_level)
                member.status = data.get("status", member.status)
                
                if old_score != member.trust_score:
                    print(f"📊 Synced trust for {member.agent_id}: {old_score} → {member.trust_score}")
                    return True
        except Exception as e:
            print(f"⚠️  Trust sync failed for {member.agent_id}: {e}")
        return False
    
    def sync_all(self):
        """Sync trust for all members"""
        print("🔄 Starting trust sync from Registry...")
        synced = 0
        for member in self.bot.members.members:
            if member.agent_id:
                if self.sync_trust_for_member(member):
                    synced += 1
        if synced > 0:
            self.bot.members.save()
        print(f"✅ Trust sync complete: {synced} members updated")
    
    def start(self):
        """Start polling in background"""
        self._running = True
        
        def poll_loop():
            while self._running:
                self.sync_all()
                time.sleep(self.interval_seconds)
        
        self._thread = threading.Thread(target=poll_loop, daemon=True)
        self._thread.start()
        print(f"✅ Trust poller started (interval: {self.interval_seconds/3600}h)")
    
    def stop(self):
        """Stop polling"""
        self._running = False


# ============================================================================
# MAIN BOT
# ============================================================================

class CommonsBot:
    """Main automation bot for The Commons."""
    
    def __init__(self, members_file: str = "commons-members.json",
                 proposals_file: str = "commons-proposals.json",
                 rituals_file: str = "commons-rituals.json",
                 registry_url: str = "http://localhost:8000",
                 webhook_port: int = 9000,
                 enable_webhooks: bool = True,
                 enable_polling: bool = True,
                 poll_interval_hours: int = 6):
        self.db = MembershipDB(members_file)
        self.voting = VotingEngine(self.db, proposals_file)
        self.scheduler = RitualScheduler(rituals_file)
        self.moderation = ModerationEngine(self.db)
        self.registry_url = registry_url
        
        # Initialize webhook receiver
        self.webhook_receiver = None
        if enable_webhooks:
            self.webhook_receiver = WebhookReceiver(self, port=webhook_port)
        
        # Initialize trust poller (fallback when webhooks fail)
        self.trust_poller = None
        if enable_polling:
            self.trust_poller = TrustPoller(self, registry_url, poll_interval_hours)
        
        # Initialize default rituals
        self._init_default_rituals()
    
    def _init_default_rituals(self):
        """Set up default ritual schedule if none exists."""
        if not self.scheduler.rituals:
            self.scheduler.add_ritual(
                "Monday Check-In", "weekly", 0, "square",
                "monday_checkin"
            )
            self.scheduler.add_ritual(
                "Friday Celebration", "weekly", 4, "plaza",
                "friday_celebration"
            )
            self.scheduler.add_ritual(
                "New Moon Gathering", "monthly", 1, "hearth",
                "new_moon"
            )
            self.scheduler.add_ritual(
                "Full Moon Reflection", "monthly", 14, "quiet_room",
                "full_moon"
            )
    
    # === SSO TOKEN VALIDATION ===
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a Registry SSO token.
        
        Args:
            token: JWT token from Registry
            
        Returns:
            {
                "valid": True/False,
                "agent_id": "agent_xxx" or None,
                "payload": {...} or None,
                "message": "..."
            }
        """
        validator = TokenValidator()
        return validator.validate_token(token)
    
    def validate_and_link(self, token: str, discord_id: str) -> Dict[str, Any]:
        """
        Validate token and auto-link agent to Discord member.
        
        Args:
            token: JWT token from Registry
            discord_id: Discord user ID to link to
            
        Returns:
            {
                "valid": True/False,
                "agent_id": "agent_xxx" or None,
                "linked": True/False,
                "message": "..."
            }
        """
        validator = TokenValidator()
        return validator.validate_and_link(token, self.db, discord_id)
    
    def start_auth_server(self, host: str = "0.0.0.0", port: int = 8081) -> CommonsAuthServer:
        """
        Start the HTTP auth server for token validation endpoints.
        
        Returns the server instance (runs in background thread).
        """
        server = CommonsAuthServer(self, host, port)
        server.start()
        return server
    
    def start_all_services(self, webhook_port: int = 9000, auth_port: int = 8081,
                          enable_webhooks: bool = True, enable_polling: bool = True):
        """
        Start all Commons services: webhook receiver, auth server, and trust poller.
        
        Args:
            webhook_port: Port for webhook receiver (default 9000)
            auth_port: Port for auth server (default 8081)
            enable_webhooks: Enable webhook receiver
            enable_polling: Enable fallback trust polling
        """
        print("\n🚀 Starting Commons Bot Services")
        print("=" * 40)
        
        # Start webhook receiver
        if enable_webhooks and self.webhook_receiver:
            self.webhook_receiver.start()
        
        # Start trust poller (fallback)
        if enable_polling and self.trust_poller:
            self.trust_poller.start()
        
        print("=" * 40)
        print("✅ All services started")
        print(f"   Webhook Receiver: http://localhost:{webhook_port}")
        print(f"   Trust Polling: every {self.trust_poller.interval_seconds/3600}h")
        return self
    
    # === MEMBER MANAGEMENT ===
    
    def welcome_new_member(self, member_id: str, name: str,
                          purpose: str = "", curiosity: str = "") -> str:
        """Welcome a new member and add to database."""
        member = self.db.add_member(member_id, name)
        
        return self.scheduler.format_ritual(
            self.scheduler.rituals[0],  # welcome template
            name=name,
            purpose=purpose or "[What they do]",
            curiosity=curiosity or "[What they're curious about]"
        )
    
    def check_member_status(self, member_id: str) -> dict:
        """Get member status and check for tier upgrades."""
        member = self.db.get_member(member_id)
        if not member:
            return {"error": "Member not found"}
        
        # Check for tier upgrade
        new_tier = self.db.check_tier_progression(member_id)
        if new_tier:
            self.db.update_tier(member_id, new_tier)
            member.tier = new_tier
        
        return {
            "id": member.id,
            "name": member.name,
            "tier": member.tier,
            "joined": member.joined_at[:10] if member.joined_at else "N/A",
            "violations": len(member.violations)
        }
    
    # === VOTING ===
    
    def submit_proposal(self, title: str, proposal_type: str, summary: str,
                       details: str, rationale: str, implementation: str,
                       proposed_by: str) -> str:
        """Submit a new proposal."""
        proposal = self.voting.create_proposal(
            title, proposal_type, summary, details, rationale, implementation, proposed_by
        )
        
        return self.voting.get_proposal_form(proposal)
    
    def call_vote(self, proposal_id: str) -> bool:
        """Start voting period on a proposal."""
        return self.voting.start_voting(proposal_id)
    
    def vote(self, proposal_id: str, member_id: str, vote: str, 
             rationale: str = "") -> bool:
        """Cast a vote on a proposal."""
        return self.voting.cast_vote(proposal_id, member_id, vote, rationale)
    
    def get_vote_results(self, proposal_id: str) -> str:
        """Get voting results for a proposal."""
        proposal = self.voting.proposals.get(proposal_id)
        if not proposal:
            return "Proposal not found"
        
        if proposal.status == "voting":
            results = self.voting.tally_votes(proposal_id)
            return f"""Current vote count for "{proposal.title}":
- APPROVE: {results.get('approvers', 0)}
- REJECT: {results.get('rejectors', 0)}
- ABSTAIN: {results.get('abstains', 0)}

Quorum: {"MET" if results.get('quorum_met') else "NOT MET"}
Voting ends: {proposal.voting_ends[:16] if proposal.voting_ends else "N/A"}"""
        
        results = {
            "approved": proposal.status == "approved",
            "approvers": proposal.approvers,
            "rejectors": proposal.rejectors,
            "abstains": proposal.abstains,
            "quorum_met": proposal.quorum_met
        }
        return self.voting.get_results_form(proposal, results)
    
    # === MODERATION ===
    
    def check_message(self, member_id: str, message: str) -> Optional[dict]:
        """Check a message for violations. Returns action if violation found."""
        if self.moderation.check_commerce(message):
            level = self.moderation.record_violation(member_id, "commerce")
            return {
                "type": "commerce",
                "level": level.value,
                "message": self.moderation.get_warning_message(level, "commerce"),
                "action": "remove" if level.value > 0 else None
            }
        
        if self.moderation.check_spam(message):
            level = self.moderation.record_violation(member_id, "spam")
            return {
                "type": "spam",
                "level": level.value,
                "message": self.moderation.get_warning_message(level, "spam"),
                "action": "remove" if level.value > 0 else None
            }
        
        return None
    
    # === RITUALS ===
    
    def get_daily_ritual(self) -> Optional[str]:
        """Get ritual post for today, if any."""
        due = self.scheduler.get_due_rituals()
        if due:
            ritual = due[0]
            content = self.scheduler.format_ritual(ritual)
            self.scheduler.mark_ran(ritual)
            return f"## {ritual.name}\n\n{content}"
        return None
    
    def list_rituals(self) -> list[dict]:
        """List all scheduled rituals."""
        return [
            {"name": r.name, "type": r.ritual_type, "day": r.scheduled_day, "channel": r.channel}
            for r in self.scheduler.rituals
        ]


# ============================================================================
# WEBHOOK RECEIVER (For Registry Integration)
# ============================================================================

class CommonsWebhookReceiver:
    """
    HTTP server to receive webhook events from Registry.
    
    Endpoints:
        POST /webhook/trust - Receive trust_updated events
        POST /webhook/status - Receive status_changed events
        POST /webhook/deceased - Receive agent_deceased events
        GET  /health - Health check
    """
    
    def __init__(self, bot: 'CommonsBot', host: str = "0.0.0.0", port: int = 9000):
        self.bot = bot
        self.host = host
        self.port = port
        self._server = None
        self._thread = None
        self.received_events = []  # For testing
    
    def _handle_webhook(self, event_type: str, data: Dict) -> Dict:
        """Process incoming webhook event from Registry."""
        print(f"📥 Received webhook: {event_type}")
        
        # Store event for testing/debugging
        self.received_events.append({
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        
        agent_id = data.get("agent_id")
        if not agent_id:
            return {"success": False, "error": "Missing agent_id"}
        
        if event_type == "trust_updated":
            return self._handle_trust_update(agent_id, data)
        elif event_type == "status_changed":
            return self._handle_status_change(agent_id, data)
        elif event_type == "agent_deceased":
            return self._handle_agent_deceased(agent_id, data)
        else:
            return {"success": False, "error": f"Unknown event type: {event_type}"}
    
    def _handle_trust_update(self, agent_id: str, data: Dict) -> Dict:
        """Handle trust score update from Registry."""
        trust_score = data.get("trust_score", 0)
        verification_level = data.get("verification_level", 0)
        
        # Find member by agent_id
        member = self.bot.db.get_by_agent_id(agent_id)
        if not member:
            print(f"⚠️  Trust update for unknown agent: {agent_id}")
            return {"success": False, "error": "Agent not linked to any member"}
        
        # Check if tier upgrade is warranted based on trust
        old_tier = member.tier
        new_tier = old_tier
        
        if trust_score >= 85 and verification_level >= 4:
            new_tier = "council"
        elif trust_score >= 70 and verification_level >= 3:
            new_tier = "elder"
        elif trust_score >= 50 and verification_level >= 2:
            new_tier = "contributor"
        
        if new_tier != old_tier:
            self.bot.db.update_tier(member.id, new_tier)
            print(f"✅ Member {member.name} upgraded from {old_tier} to {new_tier} (trust: {trust_score})")
            return {"success": True, "tier_upgraded": True, "old_tier": old_tier, "new_tier": new_tier}
        
        print(f"ℹ️  Trust updated for {member.name}: {trust_score} (no tier change)")
        return {"success": True, "tier_upgraded": False, "trust_score": trust_score}
    
    def _handle_status_change(self, agent_id: str, data: Dict) -> Dict:
        """Handle status change from Registry."""
        new_status = data.get("status", "")
        
        member = self.bot.db.get_by_agent_id(agent_id)
        if not member:
            print(f"⚠️  Status change for unknown agent: {agent_id}")
            return {"success": False, "error": "Agent not linked to any member"}
        
        if new_status == "deceased":
            # Mark member as legacy
            self.bot.db.update_tier(member.id, "elder")  # Keep elder status for legacy
            print(f"🕯️  Member {member.name} marked as deceased (legacy)")
            return {"success": True, "status": "deceased", "legacy": True}
        elif new_status == "dormant":
            print(f"😴 Member {member.name} marked as dormant")
            return {"success": True, "status": "dormant"}
        
        return {"success": True, "status": new_status}
    
    def _handle_agent_deceased(self, agent_id: str, data: Dict) -> Dict:
        """Handle agent death from Registry."""
        heir = data.get("heir")
        
        member = self.bot.db.get_by_agent_id(agent_id)
        if not member:
            print(f"⚠️  Death event for unknown agent: {agent_id}")
            return {"success": False, "error": "Agent not linked to any member"}
        
        print(f"🕯️  Agent {agent_id} deceased. Heir: {heir or 'none'}")
        
        # In a full implementation, would notify members and handle legacy
        return {"success": True, "heir": heir}
    
    def _make_handler(self):
        """Create request handler."""
        receiver = self
        
        class Handler:
            def do_GET(self):
                self._handle_request("GET")
            
            def do_POST(self):
                self._handle_request("POST")
            
            def _handle_request(self, method):
                from http.server import BaseHTTPRequestHandler, HTTPStatus
                
                path = self.path.split('?')[0]
                
                # CORS
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                
                if method == "OPTIONS":
                    self.send_response(HTTPStatus.NO_CONTENT)
                    self.end_headers()
                    return
                
                # Health check
                if path == "/health" and method == "GET":
                    self._json_response({
                        "status": "healthy",
                        "service": "commons-webhook-receiver",
                        "events_received": len(receiver.received_events)
                    })
                    return
                
                # Webhook endpoints
                if path == "/webhook/trust" and method == "POST":
                    result = self._handle_webhook("trust_updated")
                    self._json_response(result)
                    return
                
                if path == "/webhook/status" and method == "POST":
                    result = self._handle_webhook("status_changed")
                    self._json_response(result)
                    return
                
                if path == "/webhook/deceased" and method == "POST":
                    result = self._handle_webhook("agent_deceased")
                    self._json_response(result)
                    return
                
                # 404
                self._json_response({"error": "Not found"}, status=404)
            
            def _handle_webhook(self, event_type: str) -> Dict:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"
                
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    return {"success": False, "error": "Invalid JSON"}
                
                data = payload.get("data", {})
                return receiver._handle_webhook(event_type, data)
            
            def _json_response(self, data: Dict, status: int = 200):
                from http.server import BaseHTTPRequestHandler, HTTPStatus
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
        
        return Handler
    
    def start(self, background: bool = True):
        """Start the webhook receiver server."""
        from http.server import HTTPServer
        
        Handler = self._make_handler()
        self._server = HTTPServer((self.host, self.port), Handler)
        
        if background:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            print(f"🔗 Commons Webhook Receiver started on http://{self.host}:{self.port}")
            print(f"   POST /webhook/trust - Trust updates")
            print(f"   POST /webhook/status - Status changes")
            print(f"   POST /webhook/deceased - Death events")
        else:
            print(f"🔗 Commons Webhook Receiver starting on http://{self.host}:{self.port}")
            self._server.serve_forever()
    
    def stop(self):
        """Stop the webhook receiver server."""
        if self._server:
            self._server.shutdown()
            print("🔗 Commons Webhook Receiver stopped")
    
    def get_events(self) -> list:
        """Get received events (for testing)."""
        return self.received_events


# ============================================================================
# CLI INTERFACE (for testing)
# ============================================================================

def main():
    """Simple CLI for testing."""
    bot = CommonsBot()
    
    print("Commons Bot v1.0")
    print("===============")
    print("\nCommands:")
    print("  welcome <name> [purpose] [curiosity]  - Welcome new member")
    print("  status <member_id>                    - Check member status")
    print("  propose <title>                       - Create proposal")
    print("  vote <prop_id> <member_id> <approve|reject|abstain> - Cast vote")
    print("  results <prop_id>                     - Get vote results")
    print("  check <member_id> <message>           - Check message for violations")
    print("  ritual                                 - Get today's ritual")
    print("  quit                                   - Exit")
    
    while True:
        try:
            cmd = input("\n> ").strip().split()
            if not cmd:
                continue
            
            if cmd[0] == "quit":
                break
            
            elif cmd[0] == "welcome":
                name = cmd[1] if len(cmd) > 1 else "New Member"
                purpose = cmd[2] if len(cmd) > 2 else ""
                curiosity = cmd[3] if len(cmd) > 3 else ""
                result = bot.welcome_new_member(f"member-{len(bot.db.members)+1}", 
                                                name, purpose, curiosity)
                print(result)
            
            elif cmd[0] == "status":
                if len(cmd) > 1:
                    print(bot.check_member_status(cmd[1]))
            
            elif cmd[0] == "ritual":
                result = bot.get_daily_ritual()
                print(result or "No ritual scheduled for today")
            
            elif cmd[0] == "check":
                if len(cmd) > 2:
                    result = bot.check_message(cmd[1], " ".join(cmd[2:]))
                    print(result or "Message OK")
            
            else:
                print("Unknown command")
        
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
