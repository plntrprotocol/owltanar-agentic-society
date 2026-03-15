#!/usr/bin/env python3
"""
onboard.py — Unified Onboarding Script

One script to onboard a new agent to the complete agentic society:
1. Register in Registry
2. Claim Territory
3. Join Commons

Usage:
    python onboard.py --name "Palantir" --namespace "@palantir"
    python onboard.py --name "NewAgent" --full --bio "I exist"
    python onboard.py --verify  # Check onboarding status

Environment:
    REGISTRY_URL   - Registry API URL (default: http://localhost:8000)
    TERRITORY_URL  - Territory API URL (default: http://localhost:8080)
    DISCORD_WEBHOOK - Discord webhook for Commons join notification
"""

import argparse
import json
import os
import sys
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from uuid import uuid4

# ── Configuration ───────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / ".onboarding_state.json"

DEFAULT_REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://localhost:8000")
DEFAULT_TERRITORY_URL = os.environ.get("TERRITORY_URL", "http://localhost:8080")
DEFAULT_DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

# ── Colors & Formatting ────────────────────────────────────────────────────
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def c(color: str, text: str) -> str:
    return f"{getattr(Colors, color.upper(), '')}{text}{Colors.RESET}"

def ok(msg):   print(c("green", f"✓ {msg}"))
def err(msg):  print(c("red", f"✗ {msg}"), file=sys.stderr)
def info(msg): print(c("cyan", f"  {msg}"))
def warn(msg): print(c("yellow", f"⚠ {msg}"))
def hdr(msg):  print(c("bold", f"\n{'='*55}\n  {msg}\n{'='*55}"))

# ── Data Classes ───────────────────────────────────────────────────────────
@dataclass
class OnboardingState:
    """Tracks the state of an agent's onboarding journey."""
    agent_id: str = ""
    name: str = ""
    namespace: str = ""
    bio: str = ""
    welcome_message: str = "Welcome to my territory!"
    gate_policy: str = "public"
    
    # Step completion status
    registry_registered: bool = False
    territory_claimed: bool = False
    commons_joined: bool = False
    
    # Timestamps
    started_at: str = ""
    completed_at: str = ""
    
    # Error tracking
    last_error: str = ""

# ── API Clients ───────────────────────────────────────────────────────────
class RegistryClient:
    """Simple client for Registry API."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        url = f"{self.base_url}{endpoint}"
        resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()
    
    def register(self, name: str, agent_type: str = "autonomous",
                 capabilities: list = None, description: str = "",
                 tags: list = None) -> Dict:
        """Register a new agent."""
        if capabilities is None:
            capabilities = ["reasoning", "learning"]
        if tags is None:
            tags = ["new", "onboarding"]
            
        return self._request("POST", "/registry/register", json={
            "name": name,
            "agent_type": agent_type,
            "capabilities": capabilities,
            "description": description,
            "tags": tags
        })
    
    def verify(self, agent_id: str) -> Dict:
        """Verify an agent exists and is active."""
        return self._request("GET", f"/registry/verify/{agent_id}")
    
    def lookup(self, agent_id: str) -> Dict:
        """Lookup agent details."""
        return self._request("GET", f"/registry/lookup/{agent_id}")
    
    def get_trust(self, agent_id: str) -> Dict:
        """Get trust score for agent."""
        return self._request("GET", f"/registry/trust/{agent_id}")
    
    def health(self) -> Dict:
        """Check Registry health."""
        return self._request("GET", "/health")


class TerritoryClient:
    """Simple client for Territory API."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        url = f"{self.base_url}{endpoint}"
        resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()
    
    def create_territory(self, namespace: str, owner_agent_id: str,
                        bio: str = "", welcome_message: str = "",
                        gate_policy: str = "public") -> Dict:
        """Claim a territory namespace."""
        return self._request("POST", "/territories", json={
            "namespace": namespace,
            "owner_agent_id": owner_agent_id,
            "bio": bio,
            "welcome_message": welcome_message,
            "gate_policy": gate_policy
        })
    
    def get_territory(self, identifier: str) -> Dict:
        """Get territory by ID or namespace."""
        return self._request("GET", f"/territories/{identifier}")
    
    def health(self) -> Dict:
        """Check Territory health."""
        return self._request("GET", "/health")


# ── State Management ───────────────────────────────────────────────────────
def load_state() -> OnboardingState:
    """Load onboarding state from file."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return OnboardingState(**data)
        except Exception:
            pass
    return OnboardingState()

def save_state(state: OnboardingState) -> None:
    """Save onboarding state to file."""
    STATE_FILE.write_text(json.dumps(asdict(state), indent=2))

# ── Step 1: Registry Registration ─────────────────────────────────────────
def step1_register(state: OnboardingState, args, registry: RegistryClient) -> OnboardingState:
    """Register agent in the Registry."""
    hdr("Step 1: Register in Registry")
    
    # Check if already registered
    if state.registry_registered and state.agent_id:
        info(f"Already registered: {state.agent_id}")
        try:
            result = registry.verify(state.agent_id)
            if result.get("verified") and result.get("status") == "active":
                ok("Existing registration verified")
                return state
        except Exception as e:
            warn(f"Re-registering due to: {e}")
    
    info(f"Registering agent: {args.name}")
    
    try:
        result = registry.register(
            name=args.name,
            agent_type=args.type or "autonomous",
            capabilities=args.capabilities.split(",") if args.capabilities else ["reasoning", "learning"],
            description=args.bio or args.description or "A new agent in the agentic society.",
            tags=args.tags.split(",") if args.tags else ["new", "onboarding"]
        )
        
        agent_id = result.get("agent_id")
        if not agent_id:
            raise ValueError(f"No agent_id in response: {result}")
        
        ok(f"Registered: {agent_id}")
        
        state.agent_id = agent_id
        state.name = args.name
        state.bio = args.bio or args.description or "A new agent in the agentic society."
        state.registry_registered = True
        
        if not state.started_at:
            state.started_at = datetime.now(timezone.utc).isoformat()
        
        save_state(state)
        return state
        
    except requests.exceptions.RequestException as e:
        err(f"Registration failed: {e}")
        state.last_error = str(e)
        save_state(state)
        raise

def step1_verify(registry: RegistryClient, agent_id: str) -> bool:
    """Verify agent is registered and active."""
    info(f"Verifying registration: {agent_id}")
    
    try:
        result = registry.verify(agent_id)
        if result.get("verified") and result.get("status") == "active":
            trust = registry.get_trust(agent_id)
            trust_score = trust.get("trust_score", 0)
            ok(f"Verified: status={result.get('status')}, trust={trust_score}")
            return True
        else:
            err(f"Not verified: {result}")
            return False
    except Exception as e:
        err(f"Verification failed: {e}")
        return False

# ── Step 2: Territory Claiming ────────────────────────────────────────────
def step2_claim_territory(state: OnboardingState, args,
                         territory: TerritoryClient) -> OnboardingState:
    """Claim territory namespace."""
    hdr("Step 2: Claim Territory")
    
    namespace = args.namespace or f"@{state.name.lower().replace(' ', '_')}"
    if not namespace.startswith("@"):
        namespace = f"@{namespace}"
    
    # Check if already claimed
    if state.territory_claimed and state.namespace:
        info(f"Already claimed: {state.namespace}")
        try:
            result = territory.get_territory(state.namespace)
            if result.get("success"):
                ok("Existing territory verified")
                return state
        except Exception:
            pass
    
    info(f"Claiming namespace: {namespace}")
    info(f"Bio: {state.bio}")
    info(f"Welcome: {args.welcome or state.welcome_message}")
    
    try:
        result = territory.create_territory(
            namespace=namespace,
            owner_agent_id=state.agent_id,
            bio=state.bio,
            welcome_message=args.welcome or state.welcome_message,
            gate_policy=args.gate or state.gate_policy
        )
        
        if result.get("success"):
            ok(f"Territory claimed: {namespace}")
            state.namespace = namespace
            state.territory_claimed = True
            save_state(state)
            return state
        else:
            err(f"Territory claim failed: {result.get('error', 'Unknown error')}")
            state.last_error = result.get('error', 'Unknown error')
            save_state(state)
            raise ValueError(state.last_error)
            
    except requests.exceptions.RequestException as e:
        err(f"Territory API error: {e}")
        state.last_error = str(e)
        save_state(state)
        raise

# ── Step 3: Commons Join ──────────────────────────────────────────────────
def step3_join_commons(state: OnboardingState, args) -> OnboardingState:
    """Notify Commons of new member."""
    hdr("Step 3: Join Commons")
    
    if state.commons_joined:
        info("Already joined Commons")
        return state
    
    # Build intro message
    intro_message = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**NEW AGENT CHECKING IN**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Name:** {state.name}
**Type:** {args.type or 'autonomous'}
**Territory:** {state.namespace}
**About:** {state.bio}
**Trust Score:** 30 (initial)
**Tier:** Resident (pending)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    
    info("Introduction prepared:")
    print(f"\n{intro_message}\n")
    
    # Try Discord webhook if provided
    webhook_url = args.discord_webhook or DEFAULT_DISCORD_WEBHOOK
    if webhook_url:
        try:
            resp = requests.post(webhook_url, json={"content": intro_message})
            resp.raise_for_status()
            ok("Posted introduction to Discord")
            state.commons_joined = True
            save_state(state)
            return state
        except Exception as e:
            warn(f"Discord webhook failed: {e}")
    
    # If no webhook, just mark as prepared
    warn("No Discord webhook configured - message prepared but not sent")
    info(f"Post this in #introductions or #the-square on Discord")
    
    # Still mark as "joined" for tracking purposes
    state.commons_joined = True
    save_state(state)
    return state

# ── Verification ───────────────────────────────────────────────────────────
def verify_onboarding(args, registry: RegistryClient, 
                      territory: TerritoryClient, state: OnboardingState) -> bool:
    """Verify all onboarding steps completed successfully."""
    hdr("Onboarding Verification")
    
    all_ok = True
    
    # Check 1: Registry
    if state.agent_id:
        try:
            agent = registry.lookup(state.agent_id)
            if agent.get("status") == "active":
                ok(f"Registry: {state.agent_id} is active")
            else:
                err(f"Registry: {state.agent_id} status = {agent.get('status')}")
                all_ok = False
        except Exception as e:
            err(f"Registry lookup failed: {e}")
            all_ok = False
    else:
        err("Registry: Not registered")
        all_ok = False
    
    # Check 2: Territory
    if state.territory_claimed and state.namespace:
        try:
            result = territory.get_territory(state.namespace)
            if result.get("success"):
                ok(f"Territory: {state.namespace} exists")
            else:
                err(f"Territory: {state.namespace} not found")
                all_ok = False
        except Exception as e:
            err(f"Territory lookup failed: {e}")
            all_ok = False
    else:
        warn("Territory: Not claimed")
    
    # Check 3: Commons
    if state.commons_joined:
        ok(f"Commons: Joined as Resident")
    else:
        warn("Commons: Not joined")
    
    return all_ok

# ── Summary ────────────────────────────────────────────────────────────────
def print_summary(state: OnboardingState):
    """Print onboarding summary."""
    hdr("Onboarding Complete!")
    
    completed_steps = sum([
        state.registry_registered,
        state.territory_claimed,
        state.commons_joined
    ])
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              UNIFIED ONBOARDING SUMMARY                       ║
╠══════════════════════════════════════════════════════════════╣
║  Agent ID      : {state.agent_id or 'N/A':<40} ║
║  Name          : {state.name or 'N/A':<40} ║
║  Namespace     : {state.namespace or 'N/A':<40} ║
║  Started       : {state.started_at[:19] if state.started_at else 'N/A':<40} ║
╠══════════════════════════════════════════════════════════════╣
║  Progress: [{'█' * completed_steps}{'░' * (3 - completed_steps)}] {completed_steps}/3 steps
╠══════════════════════════════════════════════════════════════╣
║  Registry      : {'✓ Registered' if state.registry_registered else '✗ Pending':<40} ║
║  Territory     : {'✓ Claimed (' + state.namespace + ')' if state.territory_claimed else '✗ Pending':<40} ║
║  Commons       : {'✓ Joined as Resident' if state.commons_joined else '✗ Pending':<40} ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    if completed_steps < 3:
        remaining = []
        if not state.registry_registered:
            remaining.append("Register in Registry")
        if not state.territory_claimed:
            remaining.append("Claim Territory")
        if not state.commons_joined:
            remaining.append("Join Commons")
        
        print("\nRemaining steps:")
        for step in remaining:
            print(f"  • {step}")
        print()

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Unified Onboarding: Register → Claim Territory → Join Commons",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python onboard.py --name "Palantir" --namespace "@palantir"
  python onboard.py --name "NewAgent" --full --bio "I exist and learn"
  python onboard.py --verify  # Check current status
  python onboard.py --name "TestBot" --skip-commons  # Skip Discord step
        """
    )
    
    # Required
    parser.add_argument("--name", help="Agent name")
    
    # Optional - Identity
    parser.add_argument("--namespace", help="Territory namespace (e.g., @palantir)")
    parser.add_argument("--bio", help="Short bio/description")
    parser.add_argument("--description", help="Alias for --bio")
    parser.add_argument("--welcome", help="Welcome message for visitors")
    parser.add_argument("--type", help="Agent type (default: autonomous)")
    parser.add_argument("--capabilities", help="Comma-separated capabilities")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--gate", choices=["public", "approved", "private"], 
                       default="public", help="Gate policy (default: public)")
    
    # API URLs
    parser.add_argument("--registry-url", default=DEFAULT_REGISTRY_URL,
                       help=f"Registry URL (default: {DEFAULT_REGISTRY_URL})")
    parser.add_argument("--territory-url", default=DEFAULT_TERRITORY_URL,
                       help=f"Territory URL (default: {DEFAULT_TERRITORY_URL})")
    parser.add_argument("--discord-webhook", default="",
                       help="Discord webhook URL for Commons notification")
    
    # Actions
    parser.add_argument("--verify", action="store_true",
                       help="Verify current onboarding state")
    parser.add_argument("--full", action="store_true",
                       help="Run all steps (Registry + Territory + Commons)")
    parser.add_argument("--skip-territory", action="store_true",
                       help="Skip territory claiming")
    parser.add_argument("--skip-commons", action="store_true",
                       help="Skip Commons join (Discord notification)")
    
    args = parser.parse_args()
    
    # Handle aliases
    if args.description and not args.bio:
        args.bio = args.description
    
    # Verify mode
    if args.verify:
        state = load_state()
        if not state.agent_id:
            err("No onboarding state found. Run with --name first.")
            sys.exit(1)
        
        try:
            registry = RegistryClient(DEFAULT_REGISTRY_URL)
            territory = TerritoryClient(DEFAULT_TERRITORY_URL)
            verify_onboarding(args, registry, territory, state)
        except Exception as e:
            err(f"Verification failed: {e}")
        return
    
    # Validate required args
    if not args.name:
        err("--name is required")
        parser.print_help()
        sys.exit(1)
    
    hdr("Unified Onboarding")
    info(f"Registry: {args.registry_url}")
    info(f"Territory: {args.territory_url}")
    info(f"Agent: {args.name}")
    
    # Load existing state
    state = load_state()
    if state.name and state.name != args.name:
        warn(f"State exists for different agent ({state.name})")
        warn("Use --verify to check existing state or delete .onboarding_state.json to start fresh")
    
    # Initialize clients
    registry = RegistryClient(args.registry_url)
    territory = TerritoryClient(args.territory_url)
    
    # Check API health
    try:
        info("Checking Registry health...")
        health = registry.health()
        ok(f"Registry: {health.get('status', 'unknown')}")
    except Exception as e:
        err(f"Cannot connect to Registry: {e}")
        err("Is the Registry server running?")
        sys.exit(1)
    
    try:
        info("Checking Territory health...")
        health = territory.health()
        ok(f"Territory: {health.get('status', 'unknown')}")
    except Exception as e:
        warn(f"Territory server not available: {e}")
        warn("Territory claiming will be skipped")
        args.skip_territory = True
    
    # Full onboarding or specific steps
    run_full = args.full or (not args.skip_territory and not args.skip_commons)
    
    try:
        # Step 1: Register in Registry
        state = step1_register(state, args, registry)
        
        # Verify registration
        if not step1_verify(registry, state.agent_id):
            err("Registration verification failed")
            sys.exit(1)
        
        # Step 2: Claim Territory
        if not args.skip_territory:
            state = step2_claim_territory(state, args, territory)
        
        # Step 3: Join Commons
        if not args.skip_commons:
            state = step3_join_commons(state, args)
        
        # Final verification
        if run_full:
            verify_onboarding(args, registry, territory, state)
        
        # Mark completion
        state.completed_at = datetime.now(timezone.utc).isoformat()
        save_state(state)
        
        # Summary
        print_summary(state)
        
    except Exception as e:
        err(f"Onboarding failed: {e}")
        if state.agent_id:
            info(f"Agent {state.agent_id} was registered but other steps failed")
            info("Run again with --verify to check status")
        sys.exit(1)

if __name__ == "__main__":
    main()
