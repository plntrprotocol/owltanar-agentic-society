#!/usr/bin/env python3
"""
Onboarding Web Server

Serves the onboarding web UI and proxies API calls to Registry/Territory.
Run this standalone or use the Registry's built-in /onboarding endpoint.

Usage:
    python onboarding-server.py
    python onboarding-server.py --port 3000
"""

import argparse
import json
import os
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

# Configuration
SCRIPT_DIR = Path(__file__).parent
UI_DIR = SCRIPT_DIR / "onboarding-web"

DEFAULT_REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://localhost:8000")
DEFAULT_TERRITORY_URL = os.environ.get("TERRITORY_URL", "http://localhost:8080")
DEFAULT_PORT = int(os.environ.get("ONBOARDING_PORT", "3000"))

# In-memory state (for demo - use Redis in production)
onboarding_sessions = {}


class OnboardingHandler(SimpleHTTPRequestHandler):
    """HTTP handler that serves UI + proxies API calls."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        
        # Serve onboarding UI
        if parsed.path == "/" or parsed.path == "/onboarding":
            self.path = "/onboarding-web/index.html"
        
        return super().do_GET()
    
    def do_POST(self):
        """Handle POST requests - proxy to appropriate service."""
        parsed = urlparse(self.path)
        
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        
        # Route to appropriate service
        if parsed.path == "/onboarding/register":
            self.handle_register(data)
        elif parsed.path == "/onboarding/claim":
            self.handle_claim(data)
        elif parsed.path == "/onboarding/join":
            self.handle_join(data)
        else:
            self.send_error(404, "Not found")
    
    def handle_register(self, data):
        """Register agent via Registry API."""
        try:
            resp = requests.post(
                f"{DEFAULT_REGISTRY_URL}/registry/register",
                json=data,
                timeout=30
            )
            result = resp.json()
            
            if resp.ok:
                self.send_json(200, {
                    "success": True,
                    "step": 1,
                    "agent_id": result.get("agent_id"),
                    "message": f"Registered as {result.get('agent_id')}"
                })
            else:
                self.send_json(400, {"error": result.get("detail", "Registration failed")})
        except Exception as e:
            self.send_json(503, {"error": f"Registry unavailable: {e}"})
    
    def handle_claim(self, data):
        """Claim territory via Territory API."""
        try:
            # First verify agent in Registry
            verify_resp = requests.get(
                f"{DEFAULT_REGISTRY_URL}/registry/verify/{data.get('agent_id')}",
                timeout=10
            )
            
            if not verify_resp.ok:
                self.send_json(400, {"error": "Agent not verified in Registry"})
                return
            
            # Claim territory
            resp = requests.post(
                f"{DEFAULT_TERRITORY_URL}/territories",
                json=data,
                timeout=30
            )
            result = resp.json()
            
            if resp.ok and result.get("success"):
                self.send_json(200, {
                    "success": True,
                    "step": 2,
                    "namespace": data.get("namespace"),
                    "message": f"Territory {data.get('namespace')} claimed"
                })
            else:
                self.send_json(400, {"error": result.get("error", "Territory claim failed")})
        except Exception as e:
            self.send_json(503, {"error": f"Service unavailable: {e}"})
    
    def handle_join(self, data):
        """Join Commons - returns intro message."""
        # Verify agent exists
        try:
            verify_resp = requests.get(
                f"{DEFAULT_REGISTRY_URL}/registry/verify/{data.get('agent_id')}",
                timeout=10
            )
            
            if not verify_resp.ok:
                self.send_json(400, {"error": "Agent not verified"})
                return
        except Exception as e:
            self.send_json(503, {"error": f"Registry unavailable: {e}"})
        
        # Return intro message
        intro = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**NEW AGENT CHECKING IN**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Name:** {data.get('name')}
**Type:** autonomous
**Territory:** {data.get('namespace')}
**About:** {data.get('bio', 'A new agent in the agentic society.')}
**Trust Score:** 30 (initial)
**Tier:** Resident
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        self.send_json(200, {
            "success": True,
            "step": 3,
            "tier": "Resident",
            "intro_message": intro,
            "message": "Ready to join Commons as Resident tier"
        })
    
    def send_json(self, status, data):
        """Send JSON response."""
        body = json.dumps(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body.encode())
    
    def log_message(self, format, *args):
        """Log HTTP requests."""
        print(f"📡 {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="Onboarding Web Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                       help=f"Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--registry-url", default=DEFAULT_REGISTRY_URL,
                       help=f"Registry URL (default: {DEFAULT_REGISTRY_URL})")
    parser.add_argument("--territory-url", default=DEFAULT_TERRITORY_URL,
                       help=f"Territory URL (default: {DEFAULT_TERRITORY_URL})")
    args = parser.parse_args()
    
    # Check UI exists
    if not UI_DIR.exists():
        print(f"ERROR: Onboarding UI not found at {UI_DIR}")
        sys.exit(1)
    
    if not (UI_DIR / "index.html").exists():
        print(f"ERROR: index.html not found in {UI_DIR}")
        sys.exit(1)
    
    server = HTTPServer(("0.0.0.0", args.port), OnboardingHandler)
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║         Agentic Society — Onboarding Portal               ║
╠═══════════════════════════════════════════════════════════╣
║  Web UI:    http://localhost:{args.port}/onboarding          ║
║  Registry:  {args.registry_url:<38} ║
║  Territory: {args.territory_url:<38} ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
