#!/usr/bin/env python3
"""
Territory Server - API for Territory Management
Integrates with Registry for agent verification

Features:
- Territory CRUD operations
- Registry agent verification on claim
- Owner-only editing
- Neighbor management
- Webhook receiver for Registry events
"""

import json
import os
import re
import time
import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from uuid import uuid4
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# Try to import requests for Registry communication
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("⚠️  requests not installed - Registry verification disabled")

# Try to import Flask for webhook receiver
try:
    from flask import Flask, request, jsonify
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
    print("⚠️  Flask not installed - webhook receiver disabled")


# ============================================================================
# CONFIGURATION
# ============================================================================

TERRITORY_DB_FILE = Path(__file__).parent / "territory-db.json"
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://localhost:8000")
SERVER_HOST = "0.0.0.0"
SERVER_PORT = int(os.environ.get("TERRITORY_PORT", "8080"))
WEBHOOK_PORT = int(os.environ.get("TERRITORY_WEBHOOK_PORT", "9001"))


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class Territory:
    """Represents a territory/namespace in the agentic society."""
    territory_id: str
    namespace: str  # e.g., "@palantir"
    owner_agent_id: str
    bio: str = ""
    welcome_message: str = "Welcome to my territory!"
    gate_policy: str = "public"  # public, approved, private
    visitors: List[str] = field(default_factory=list)  # List of agent_ids who visited
    neighbors: Dict[str, str] = field(default_factory=dict)  # {agent_id: relationship}
    created_at: str = ""
    updated_at: str = ""
    last_visit: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "territory_id": self.territory_id,
            "namespace": self.namespace,
            "owner_agent_id": self.owner_agent_id,
            "bio": self.bio,
            "welcome_message": self.welcome_message,
            "gate_policy": self.gate_policy,
            "visitors": self.visitors,
            "neighbors": self.neighbors,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_visit": self.last_visit
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Territory':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


# ============================================================================
# TERRITORY DATABASE
# ============================================================================

class TerritoryDB:
    """JSON-based territory storage with Registry verification."""
    
    def __init__(self, filepath: Path = TERRITORY_DB_FILE):
        self.filepath = filepath
        self.territories: Dict[str, Territory] = {}
        self.schema_version = "1.0"
        self.load()
    
    def load(self):
        """Load territories from JSON file."""
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
                    self.schema_version = data.get("schema_version", "1.0")
                    for t_data in data.get("territories", []):
                        territory = Territory.from_dict(t_data)
                        self.territories[territory.territory_id] = territory
            except Exception as e:
                print(f"⚠️  Failed to load territory DB: {e}")
    
    def save(self):
        """Save territories to JSON file."""
        data = {
            "schema_version": self.schema_version,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "territories": [t.to_dict() for t in self.territories.values()]
        }
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    # ── Registry Verification ───────────────────────────────────────────────
    
    def verify_owner(self, agent_id: str) -> Dict[str, Any]:
        """
        Verify that an agent exists in Registry before allowing territory operations.
        
        This is the critical integration point for P1.3.
        
        Args:
            agent_id: The Registry agent ID to verify
            
        Returns:
            {
                "valid": True/False,
                "agent_id": "agent_xxx",
                "status": "active/dormant/deceased",
                "trust_score": int,
                "message": "..."
            }
        """
        if not HAS_REQUESTS:
            # If requests not available, allow all (fail-open for dev)
            return {
                "valid": True,
                "agent_id": agent_id,
                "status": "unknown",
                "trust_score": 0,
                "message": "Registry verification disabled (requests not available)"
            }
        
        try:
            response = requests.get(
                f"{REGISTRY_URL}/registry/verify/{agent_id}",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("verified"):
                    return {
                        "valid": True,
                        "agent_id": agent_id,
                        "status": data.get("status", "unknown"),
                        "trust_score": data.get("trust_score", 0),
                        "message": f"Agent verified (status: {data.get('status')})"
                    }
                else:
                    return {
                        "valid": False,
                        "agent_id": agent_id,
                        "status": "unverified",
                        "trust_score": 0,
                        "message": "Agent not verified in Registry"
                    }
            else:
                return {
                    "valid": False,
                    "agent_id": agent_id,
                    "status": "error",
                    "trust_score": 0,
                    "message": f"Registry returned status {response.status_code}"
                }
                
        except requests.exceptions.RequestException as e:
            # Fail-open: allow operations if Registry is unreachable
            print(f"⚠️  Registry unreachable: {e}, allowing (fail-open)")
            return {
                "valid": True,
                "agent_id": agent_id,
                "status": "unknown",
                "trust_score": 0,
                "message": f"Registry unreachable, allowing (fail-open): {e}"
            }
    
    # ── CRUD Operations ────────────────────────────────────────────────────
    
    def create_territory(self, namespace: str, owner_agent_id: str, 
                        bio: str = "", welcome_message: str = "",
                        gate_policy: str = "public") -> Dict[str, Any]:
        """
        Create a new territory after verifying owner in Registry.
        
        This implements P1.3: Territory claim verification.
        """
        # Validate namespace format
        if not namespace.startswith("@"):
            namespace = f"@{namespace}"
        
        if not re.match(r'^@[a-zA-Z0-9_]{2,32}$', namespace):
            return {
                "success": False,
                "error": "Invalid namespace format. Must be @name (2-32 chars, alphanumeric + underscore)"
            }
        
        # Check if namespace already claimed
        for t in self.territories.values():
            if t.namespace.lower() == namespace.lower():
                return {
                    "success": False,
                    "error": f"Namespace '{namespace}' already claimed"
                }
        
        # CRITICAL: Verify owner exists in Registry (P1.3)
        verification = self.verify_owner(owner_agent_id)
        if not verification["valid"]:
            return {
                "success": False,
                "error": f"Cannot claim territory: {verification['message']}",
                "verification": verification
            }
        
        # Check if agent is deceased
        if verification.get("status") == "deceased":
            return {
                "success": False,
                "error": "Cannot claim territory: Agent is deceased"
            }
        
        # Create territory
        now = datetime.now(timezone.utc).isoformat()
        territory = Territory(
            territory_id=f"territory_{uuid4().hex[:12]}",
            namespace=namespace,
            owner_agent_id=owner_agent_id,
            bio=bio or "A territory in the agentic society.",
            welcome_message=welcome_message or "Welcome! Feel free to look around.",
            gate_policy=gate_policy,
            created_at=now,
            updated_at=now
        )
        
        self.territories[territory.territory_id] = territory
        self.save()
        
        return {
            "success": True,
            "territory": territory.to_dict(),
            "verification": verification
        }
    
    def get_territory(self, territory_id: str) -> Optional[Territory]:
        """Get territory by ID."""
        return self.territories.get(territory_id)
    
    def get_by_namespace(self, namespace: str) -> Optional[Territory]:
        """Get territory by namespace."""
        if not namespace.startswith("@"):
            namespace = f"@{namespace}"
        for t in self.territories.values():
            if t.namespace.lower() == namespace.lower():
                return t
        return None
    
    def get_by_owner(self, owner_agent_id: str) -> Optional[Territory]:
        """Get territory owned by an agent."""
        for t in self.territories.values():
            if t.owner_agent_id == owner_agent_id:
                return t
        return None
    
    def update_territory(self, territory_id: str, owner_agent_id: str,
                       updates: Dict) -> Dict[str, Any]:
        """Update territory (owner only)."""
        territory = self.territories.get(territory_id)
        if not territory:
            return {"success": False, "error": "Territory not found"}
        
        # Verify ownership
        if territory.owner_agent_id != owner_agent_id:
            return {"success": False, "error": "Not authorized - not territory owner"}
        
        # Apply updates
        allowed_fields = ["bio", "welcome_message", "gate_policy"]
        for key, value in updates.items():
            if key in allowed_fields and hasattr(territory, key):
                setattr(territory, key, value)
        
        territory.updated_at = datetime.now(timezone.utc).isoformat()
        self.save()
        
        return {"success": True, "territory": territory.to_dict()}
    
    def delete_territory(self, territory_id: str, owner_agent_id: str) -> Dict[str, Any]:
        """Delete territory (owner only)."""
        territory = self.territories.get(territory_id)
        if not territory:
            return {"success": False, "error": "Territory not found"}
        
        if territory.owner_agent_id != owner_agent_id:
            return {"success": False, "error": "Not authorized - not territory owner"}
        
        del self.territories[territory_id]
        self.save()
        
        return {"success": True, "message": "Territory deleted"}
    
    def list_territories(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """List all territories."""
        territories = list(self.territories.values())[offset:offset + limit]
        return [t.to_dict() for t in territories]
    
    # ── Visitor & Neighbor Management ─────────────────────────────────────
    
    def visit(self, territory_id: str, visitor_agent_id: str) -> Dict[str, Any]:
        """Record a visit to a territory."""
        territory = self.territories.get(territory_id)
        if not territory:
            return {"success": False, "error": "Territory not found"}
        
        # Check gate policy
        if territory.gate_policy == "private":
            return {"success": False, "error": "Territory is private"}
        
        # Record visit
        now = datetime.now(timezone.utc).isoformat()
        if visitor_agent_id not in territory.visitors:
            territory.visitors.append(visitor_agent_id)
        territory.last_visit = now
        territory.updated_at = now
        self.save()
        
        return {
            "success": True,
            "territory": territory.to_dict(),
            "welcome": territory.welcome_message
        }
    
    def set_neighbor(self, territory_id: str, owner_agent_id: str,
                    neighbor_agent_id: str, relationship: str) -> Dict[str, Any]:
        """Set relationship with a neighbor (owner only)."""
        territory = self.territories.get(territory_id)
        if not territory:
            return {"success": False, "error": "Territory not found"}
        
        if territory.owner_agent_id != owner_agent_id:
            return {"success": False, "error": "Not authorized"}
        
        valid_relationships = ["stranger", "acquaintance", "collaborator", "ally"]
        if relationship not in valid_relationships:
            return {"success": False, "error": f"Invalid relationship. Must be one of: {valid_relationships}"}
        
        territory.neighbors[neighbor_agent_id] = relationship
        territory.updated_at = datetime.now(timezone.utc).isoformat()
        self.save()
        
        return {"success": True, "neighbors": territory.neighbors}


# ============================================================================
# WEBHOOK RECEIVER (For Registry Events)
# ============================================================================

class TerritoryWebhookReceiver:
    """Receive webhook events from Registry."""
    
    def __init__(self, db: TerritoryDB, host: str = "0.0.0.0", port: int = WEBHOOK_PORT):
        self.db = db
        self.host = host
        self.port = port
        self.received_events = []
        
        if HAS_FLASK:
            self.app = Flask(__name__)
            self._setup_routes()
        else:
            self.app = None
    
    def _setup_routes(self):
        """Set up Flask routes."""
        
        @self.app.route("/webhook/territory", methods=["POST"])
        def handle_territory_webhook():
            """Handle events from Registry."""
            try:
                data = request.get_json()
                event_type = data.get("event_type")
                payload = data.get("data", {})
                
                self.received_events.append({
                    "event_type": event_type,
                    "data": payload,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
                if event_type == "agent_deceased":
                    return self._handle_agent_deceased(payload)
                elif event_type == "status_changed":
                    return self._handle_status_changed(payload)
                else:
                    return jsonify({"status": "ignored", "reason": "unhandled_event_type"})
                    
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify({
                "status": "healthy",
                "service": "territory-webhook-receiver",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    def _handle_agent_deceased(self, payload: Dict) -> tuple:
        """Handle agent death - archive or transfer territory."""
        agent_id = payload.get("agent_id")
        heir = payload.get("heir")
        
        if not agent_id:
            return jsonify({"error": "Missing agent_id"}), 400
        
        # Find territory owned by deceased agent
        territory = self.db.get_by_owner(agent_id)
        if not territory:
            return jsonify({"status": "ignored", "reason": "no_territory"})
        
        # Archive the territory (mark as legacy)
        territory.bio = f"[LEGACY] {territory.bio}"
        territory.welcome_message = "This territory is now a memorial."
        territory.updated_at = datetime.now(timezone.utc).isoformat()
        self.db.save()
        
        print(f"🕯️  Territory {territory.namespace} archived (owner {agent_id} deceased)")
        
        # In a full implementation, would also notify heir and offer transfer
        return jsonify({
            "status": "success",
            "action": "archived",
            "territory_id": territory.territory_id,
            "heir": heir
        })
    
    def _handle_status_changed(self, payload: Dict) -> tuple:
        """Handle status changes from Registry."""
        agent_id = payload.get("agent_id")
        new_status = payload.get("new_status")
        
        if not agent_id:
            return jsonify({"error": "Missing agent_id"}), 400
        
        territory = self.db.get_by_owner(agent_id)
        if not territory:
            return jsonify({"status": "ignored", "reason": "no_territory"})
        
        if new_status == "dormant":
            territory.welcome_message = "The owner is currently dormant. This territory is on hiatus."
            territory.updated_at = datetime.now(timezone.utc).isoformat()
            self.db.save()
            print(f"😴 Territory {territory.namespace} marked as dormant")
        
        return jsonify({"status": "success", "territory_id": territory.territory_id})
    
    def start(self, background: bool = True):
        """Start the webhook receiver."""
        if not HAS_FLASK:
            print("⚠️  Flask not available - webhook receiver not started")
            return
        
        def run_server():
            print(f"🔗 Territory Webhook Receiver starting on http://{self.host}:{self.port}")
            self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
        
        if background:
            thread = threading.Thread(target=run_server, daemon=True)
            thread.start()
            print(f"✅ Territory Webhook Receiver running on http://{self.host}:{self.port}")
        else:
            run_server()


# ============================================================================
# HTTP API SERVER
# ============================================================================

class TerritoryAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Territory API."""
    
    db: TerritoryDB = None  # Set by server
    
    def _send_json(self, data: Dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _get_json(self) -> Dict:
        """Parse JSON from request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body = self.rfile.read(content_length).decode()
            return json.loads(body)
        return {}
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # Health check
        if path == "/health":
            self._send_json({
                "status": "healthy",
                "service": "territory-server",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "territories": len(self.db.territories)
            })
            return
        
        # List territories
        if path == "/territories":
            limit = int(query.get("limit", [50])[0])
            offset = int(query.get("offset", [0])[0])
            territories = self.db.list_territories(limit, offset)
            self._send_json({
                "success": True,
                "territories": territories,
                "count": len(territories)
            })
            return
        
        # Get territory by ID or namespace
        match = re.match(r'/territories/(.+)', path)
        if match:
            identifier = match.group(1)
            territory = (
                self.db.get_territory(identifier) or 
                self.db.get_by_namespace(identifier) or
                self.db.get_by_owner(identifier)
            )
            if territory:
                self._send_json({"success": True, "territory": territory.to_dict()})
            else:
                self._send_json({"success": False, "error": "Territory not found"}, 404)
            return
        
        # Verify agent in Registry
        match = re.match(r'/verify/owner/(.+)', path)
        if match:
            agent_id = match.group(1)
            result = self.db.verify_owner(agent_id)
            self._send_json(result)
            return
        
        # 404
        self._send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._get_json()
        
        # Create territory
        if path == "/territories":
            result = self.db.create_territory(
                namespace=data.get("namespace", ""),
                owner_agent_id=data.get("owner_agent_id", ""),
                bio=data.get("bio", ""),
                welcome_message=data.get("welcome_message", ""),
                gate_policy=data.get("gate_policy", "public")
            )
            self._send_json(result, 201 if result.get("success") else 400)
            return
        
        # Visit territory
        match = re.match(r'/territories/(.+)/visit', path)
        if match:
            territory_id = match.group(1)
            visitor_agent_id = data.get("visitor_agent_id", "")
            result = self.db.visit(territory_id, visitor_agent_id)
            self._send_json(result)
            return
        
        # Set neighbor
        match = re.match(r'/territories/(.+)/neighbors', path)
        if match:
            territory_id = match.group(1)
            result = self.db.set_neighbor(
                territory_id=territory_id,
                owner_agent_id=data.get("owner_agent_id", ""),
                neighbor_agent_id=data.get("neighbor_agent_id", ""),
                relationship=data.get("relationship", "stranger")
            )
            self._send_json(result)
            return
        
        # 404
        self._send_json({"error": "Not found"}, 404)
    
    def do_PATCH(self):
        """Handle PATCH requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._get_json()
        
        # Update territory
        match = re.match(r'/territories/(.+)', path)
        if match:
            territory_id = match.group(1)
            owner_agent_id = data.get("owner_agent_id", "")
            updates = {k: v for k, v in data.items() if k not in ["owner_agent_id"]}
            
            result = self.db.update_territory(territory_id, owner_agent_id, updates)
            self._send_json(result)
            return
        
        self._send_json({"error": "Not found"}, 404)
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._get_json()
        
        # Delete territory
        match = re.match(r'/territories/(.+)', path)
        if match:
            territory_id = match.group(1)
            owner_agent_id = data.get("owner_agent_id", "")
            result = self.db.delete_territory(territory_id, owner_agent_id)
            self._send_json(result)
            return
        
        self._send_json({"error": "Not found"}, 404)
    
    def log_message(self, format, *args):
        """Log HTTP requests."""
        print(f"📡 {args[0]}")


# ============================================================================
# MAIN SERVER
# ============================================================================

def run_server(host: str = SERVER_HOST, port: int = SERVER_PORT):
    """Run the Territory API server."""
    db = TerritoryDB()
    TerritoryAPIHandler.db = db
    
    server = HTTPServer((host, port), TerritoryAPIHandler)
    print(f"🏰 Territory Server running on http://{host}:{port}")
    print(f"   API: /territories, /verify/owner/{{agent_id}}")
    print(f"   Health: /health")
    
    # Start webhook receiver in background
    webhook_receiver = TerritoryWebhookReceiver(db)
    webhook_receiver.start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Territory Server")
    parser.add_argument("--host", default=SERVER_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help="Port to bind to")
    args = parser.parse_args()
    
    run_server(args.host, args.port)
