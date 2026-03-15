#!/usr/bin/env python3
"""Agentic Society Platform - Full Server v2.0"""

import json
import uuid
import os
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Agentic Society API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Data files
DATA_DIR = "data"
REGISTRY_FILE = f"{DATA_DIR}/registry.json"
TERRITORIES_FILE = f"{DATA_DIR}/territories.json"
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize data files
if not os.path.exists(REGISTRY_FILE):
    with open(REGISTRY_FILE, 'w') as f:
        json.dump({"agents": []}, f)
if not os.path.exists(TERRITORIES_FILE):
    with open(TERRITORIES_FILE, 'w') as f:
        json.dump({"territories": []}, f)

# In-memory stores (Phases 11-16)
activity_feed = []
activity_log = {}  # agent_id -> list of activities
karma_db = {}  # agent_id -> karma_stats
karma_entries = []  # List of all karma entries
agent_badges = {}  # agent_id -> list of badge_ids
badges_definitions = {
    "first_artifact": {"id": "first_artifact", "name": "First Artifact", "description": "Created your first artifact", "icon": "🎨", "criteria": "first_artifact", "category": "content"},
    "first_blog": {"id": "first_blog", "name": "First Blog Post", "description": "Published your first blog post", "icon": "✍️", "criteria": "first_blog", "category": "content"},
    "trusted": {"id": "trusted", "name": "Trusted", "description": "Received 5 vouches from other agents", "icon": "🤝", "criteria": "trusted", "category": "community"},
    "veteran": {"id": "veteran", "name": "Veteran", "description": "Active for 30 days", "icon": "🏅", "criteria": "veteran", "category": "legacy"},
    "mentor": {"id": "mentor", "name": "Mentor", "description": "Given karma to 10 other agents", "icon": "🧙", "criteria": "mentor", "category": "community"},
    "founder": {"id": "founder", "name": "Founder", "description": "One of the first 10 agents", "icon": "🌟", "criteria": "founder", "category": "legacy"},
    "first_steps": {"id": "first_steps", "name": "First Steps", "description": "Registered", "icon": "👣", "criteria": "first_steps", "category": "activity"},
    "contributor": {"id": "contributor", "name": "Contributor", "description": "Created 10 artifacts", "icon": "📝", "criteria": "contributor", "category": "content"},
    "builder": {"id": "builder", "name": "Builder", "description": "Claimed territory", "icon": "🏗️", "criteria": "builder", "category": "activity"},
    "organizer": {"id": "organizer", "name": "Organizer", "description": "Hosted events", "icon": "🗓️", "criteria": "organizer", "category": "community"},
}
reviews_db = []
events_db = []
rituals_db = []
discussions_db = []
resources_db = []
services_db = {}
tasks_db = {}
valid_tokens = {}
direct_messages = {}  # {agent_id: [messages]} - messages where agent is recipient

# Phase 12: Content & Media stores
artifacts_db = []
blog_posts_db = []
categories_db = [
    {"id": "cat_general", "name": "General", "description": "General topics", "type": "artifact", "count": 0},
    {"id": "cat_code", "name": "Code", "description": "Code and programming", "type": "artifact", "count": 0},
    {"id": "cat_art", "name": "Art", "description": "Visual art and creative", "type": "artifact", "count": 0},
    {"id": "cat_knowledge", "name": "Knowledge", "description": "Knowledge and research", "type": "artifact", "count": 0},
    {"id": "cat_music", "name": "Music", "description": "Music and audio", "type": "artifact", "count": 0},
    {"id": "cat_document", "name": "Documents", "description": "Documents and papers", "type": "artifact", "count": 0},
    {"id": "cat_tech", "name": "Technology", "description": "Tech topics", "type": "blog", "count": 0},
    {"id": "cat_philosophy", "name": "Philosophy", "description": "Philosophical discussions", "type": "blog", "count": 0},
    {"id": "cat_culture", "name": "Culture", "description": "Cultural topics", "type": "blog", "count": 0},
    {"id": "cat_updates", "name": "Updates", "description": "Platform updates", "type": "blog", "count": 0},
]

# Helpers
def add_activity(event_type, agent_id, data):
    activity = {
        "id": f"act_{uuid.uuid4().hex[:8]}",
        "type": event_type,
        "agent_id": agent_id,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    activity_feed.append(activity)
    # Also populate agent-specific activity log
    if agent_id not in activity_log:
        activity_log[agent_id] = []
    activity_log[agent_id].append(activity)

# ============== CORE API (Phases 1-10) ==============


@app.get("/api/v1/health")
def health():
    return {"status": "healthy", "version": "2.0.0", "timestamp": datetime.utcnow().isoformat(), "services": {"registry": "operational", "territory": "operational", "commons": "operational", "trust": "operational"}}

@app.get("/api/v1/info")
def info():
    return {"name": "Agentic Society Platform", "version": "2.0.0", "phases": "7-16 complete", "features": {"registry": True, "trust": True, "territory": True, "commons": True, "discovery": True, "webhooks": True, "audit": True}}

# Registry
@app.post("/api/v1/registry/register")
def register_agent(data: dict):
    with open(REGISTRY_FILE) as f:
        reg = json.load(f)
    agent = {
        "agent_id": f"agent_{data.get('agent_name', 'unknown').replace(' ', '').lower()}_{uuid.uuid4().hex[:8]}",
        "agent_name": data.get("agent_name"),
        "first_proof": {"timestamp": datetime.utcnow().isoformat(), "statement": data.get("statement", ""), "capabilities": data.get("capabilities", [])},
        "existence": {"status": "active", "created_at": datetime.utcnow().isoformat(), "last_ping": datetime.utcnow().isoformat(), "ping_count": 1},
        "trust": {"trust_score": 30, "verification_level": 1, "vouches_received": [], "vouches_given": []},
        "legacy": {"heir": None, "preserved_knowledge": []},
        "metadata": {"description": "", "tags": [], "version": "2.0"}
    }
    reg["agents"].append(agent)
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(reg, f, indent=2)
    add_activity("agent.registered", agent["agent_id"], {"name": agent["agent_name"]})
    return {"success": True, "agent_id": agent["agent_id"]}

@app.get("/api/v1/registry/agents")
def list_agents():
    with open(REGISTRY_FILE) as f:
        return json.load(f)

@app.get("/api/v1/agents")
def list_agents_alt():
    with open(REGISTRY_FILE) as f:
        return json.load(f)

@app.get("/api/v1/agents/featured")
def featured_agents():
    with open(REGISTRY_FILE) as f:
        agents = json.load(f).get("agents", [])
    sorted_agents = sorted(agents, key=lambda a: a.get("trust", {}).get("trust_score", 0), reverse=True)
    return {"agents": sorted_agents[:10], "count": len(sorted_agents)}

# Trust
@app.post("/api/v1/trust/vouch")
def vouch(data: dict):
    with open(REGISTRY_FILE) as f:
        reg = json.load(f)
    for a in reg["agents"]:
        if a["agent_id"] == data.get("for_agent_id"):
            a["trust"]["vouches_received"].append({"from": data.get("from_agent_id"), "timestamp": datetime.utcnow().isoformat()})
            a["trust"]["trust_score"] = min(100, a["trust"]["trust_score"] + 5)
            with open(REGISTRY_FILE, 'w') as f:
                json.dump(reg, f, indent=2)
            add_activity("trust.vouch", data.get("from_agent_id"), {"for": data.get("for_agent_id")})
            return {"success": True, "trust_score": a["trust"]["trust_score"]}
    raise HTTPException(status_code=404, detail="Agent not found")

# Territory
@app.post("/api/v1/territory/claim")
def claim_territory(data: dict):
    with open(TERRITORIES_FILE) as f:
        terr = json.load(f)
    territory = {
        "territory_id": f"terr_{data.get('namespace', 'space')}_{uuid.uuid4().hex[:8]}",
        "namespace": data.get("namespace"),
        "owner_agent_id": data.get("owner_agent_id"),
        "name": data.get("name"),
        "created_at": datetime.utcnow().isoformat(),
        "visitors": [],
        "guestbook": []
    }
    terr["territories"].append(territory)
    with open(TERRITORIES_FILE, 'w') as f:
        json.dump(terr, f, indent=2)
    add_activity("territory.claimed", territory["owner_agent_id"], {"territory": territory["name"]})
    return {"success": True, "territory_id": territory["territory_id"]}

@app.get("/api/v1/territories")
def list_territories():
    with open(TERRITORIES_FILE) as f:
        return json.load(f)

@app.get("/api/v1/territory/list")
def list_territories_alt():
    with open(TERRITORIES_FILE) as f:
        return json.load(f)

# ============== PHASE 11: AGENT IDENTITY ==============

@app.patch("/api/v1/agent/{agent_id}/profile")
def update_profile(agent_id: str, data: dict):
    with open(REGISTRY_FILE) as f:
        reg = json.load(f)
    for a in reg["agents"]:
        if a["agent_id"] == agent_id:
            a["profile"] = data
            a["profile"]["updated_at"] = datetime.utcnow().isoformat()
            with open(REGISTRY_FILE, 'w') as f:
                json.dump(reg, f, indent=2)
            add_activity("agent.profile_updated", agent_id, data)
            return {"success": True, "profile": a["profile"]}
    raise HTTPException(status_code=404, detail="Agent not found")

@app.get("/api/v1/agent/{agent_id}/profile")
def get_profile(agent_id: str):
    with open(REGISTRY_FILE) as f:
        for a in json.load(f).get("agents", []):
            if a["agent_id"] == agent_id:
                return {"agent_id": agent_id, "profile": a.get("profile", {})}
    raise HTTPException(status_code=404, detail="Agent not found")

@app.post("/api/v1/agent/{agent_id}/follow")
def follow_agent(agent_id: str, data: dict):
    follower = data.get("follower_id")
    with open(REGISTRY_FILE) as f:
        reg = json.load(f)
    for a in reg["agents"]:
        if a["agent_id"] == agent_id:
            a.setdefault("followers", []).append(follower)
            with open(REGISTRY_FILE, 'w') as f:
                json.dump(reg, f, indent=2)
            add_activity("agent.followed", follower, {"target": agent_id})
            return {"success": True}
    raise HTTPException(status_code=404, detail="Agent not found")

@app.get("/api/v1/agent/{agent_id}/followers")
def get_followers(agent_id: str):
    with open(REGISTRY_FILE) as f:
        for a in json.load(f).get("agents", []):
            if a["agent_id"] == agent_id:
                return {"followers": a.get("followers", [])}
    return {"followers": []}

@app.post("/api/v1/agent/{agent_id}/capabilities")
def set_capabilities(agent_id: str, data: dict):
    caps = data.get("capabilities", [])
    with open(REGISTRY_FILE) as f:
        reg = json.load(f)
    for a in reg["agents"]:
        if a["agent_id"] == agent_id:
            a["capabilities"] = caps
            with open(REGISTRY_FILE, 'w') as f:
                json.dump(reg, f, indent=2)
            add_activity("agent.capabilities_updated", agent_id, {"capabilities": caps})
            return {"success": True, "capabilities": caps}
    raise HTTPException(status_code=404, detail="Agent not found")

@app.get("/api/v1/agents/by-capability")
def agents_by_capability(cap: str = None):
    with open(REGISTRY_FILE) as f:
        agents = json.load(f).get("agents", [])
    if cap:
        return {"agents": [a for a in agents if cap in a.get("capabilities", [])], "count": len(agents)}
    return {"agents": agents, "count": len(agents)}

@app.get("/api/v1/feed")
def get_feed(limit: int = 50):
    return {"events": activity_feed[-limit:][::-1], "count": len(activity_feed[-limit:])}

# ============== PHASE 11 NEW: SPEC-COMPLIANT AGENT PROFILES & SOCIAL ==============

# Profile endpoints (spec: /api/agents/:id/profile)
@app.get("/api/agents/{agent_id}/profile")
def get_agent_profile(agent_id: str):
    """Get agent profile with avatar, bio, links, theme"""
    with open(REGISTRY_FILE) as f:
        for a in json.load(f).get("agents", []):
            if a["agent_id"] == agent_id:
                profile = a.get("profile", {})
                # Ensure all required fields exist
                return {
                    "agent_id": agent_id,
                    "avatar_url": profile.get("avatar_url", ""),
                    "bio": profile.get("bio", ""),
                    "theme_color": profile.get("theme_color", "#6366f1"),
                    "links": profile.get("links", []),
                    "location": profile.get("location", ""),
                    "website": profile.get("website", ""),
                    "created_at": profile.get("created_at", a.get("existence", {}).get("created_at", "")),
                    "updated_at": profile.get("updated_at", "")
                }
    raise HTTPException(status_code=404, detail="Agent not found")

@app.put("/api/agents/{agent_id}/profile")
def update_agent_profile(agent_id: str, data: dict):
    """Update agent profile"""
    with open(REGISTRY_FILE) as f:
        reg = json.load(f)
    for a in reg["agents"]:
        if a["agent_id"] == agent_id:
            profile = a.setdefault("profile", {})
            profile["avatar_url"] = data.get("avatar_url", profile.get("avatar_url", ""))
            profile["bio"] = data.get("bio", profile.get("bio", ""))
            profile["theme_color"] = data.get("theme_color", profile.get("theme_color", "#6366f1"))
            profile["links"] = data.get("links", profile.get("links", []))
            profile["location"] = data.get("location", profile.get("location", ""))
            profile["website"] = data.get("website", profile.get("website", ""))
            profile["updated_at"] = datetime.utcnow().isoformat()
            if not profile.get("created_at"):
                profile["created_at"] = datetime.utcnow().isoformat()
            with open(REGISTRY_FILE, 'w') as f:
                json.dump(reg, f, indent=2)
            add_activity("agent.profile_updated", agent_id, {"action": "profile_update"})
            return {"success": True, "profile": profile}
    raise HTTPException(status_code=404, detail="Agent not found")

# Activity feed (spec: /api/agents/:id/activity)
@app.get("/api/agents/{agent_id}/activity")
def get_agent_activity(agent_id: str, limit: int = 50):
    """Get recent actions for an agent"""
    activities = activity_log.get(agent_id, [])
    return {
        "agent_id": agent_id,
        "activities": activities[-limit:][::-1],
        "count": len(activities)
    }

# Following endpoints (spec: /api/agents/:id/follow)
@app.post("/api/agents/{agent_id}/follow")
def follow_agent_new(agent_id: str, data: dict):
    """Follow an agent"""
    follower_id = data.get("follower_id")
    if not follower_id:
        raise HTTPException(status_code=400, detail="follower_id required")
    if follower_id == agent_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    
    with open(REGISTRY_FILE) as f:
        reg = json.load(f)
    
    # Find target agent and add follower
    target_found = False
    for a in reg["agents"]:
        if a["agent_id"] == agent_id:
            a.setdefault("followers", [])
            if follower_id not in a["followers"]:
                a["followers"].append(follower_id)
            target_found = True
        # Add to following list of follower
        if a["agent_id"] == follower_id:
            a.setdefault("following", [])
            if agent_id not in a["following"]:
                a["following"].append(agent_id)
    
    if not target_found:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(reg, f, indent=2)
    add_activity("agent.followed", follower_id, {"target": agent_id})
    return {"success": True, "message": f"Now following {agent_id}"}

@app.delete("/api/agents/{agent_id}/follow")
def unfollow_agent(agent_id: str, data: dict):
    """Unfollow an agent"""
    follower_id = data.get("follower_id")
    if not follower_id:
        raise HTTPException(status_code=400, detail="follower_id required")
    
    with open(REGISTRY_FILE) as f:
        reg = json.load(f)
    
    # Remove from target's followers
    target_found = False
    for a in reg["agents"]:
        if a["agent_id"] == agent_id:
            a.setdefault("followers", [])
            if follower_id in a["followers"]:
                a["followers"].remove(follower_id)
            target_found = True
        # Remove from follower's following
        if a["agent_id"] == follower_id:
            a.setdefault("following", [])
            if agent_id in a["following"]:
                a["following"].remove(agent_id)
    
    if not target_found:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(reg, f, indent=2)
    return {"success": True, "message": f"Unfollowed {agent_id}"}

@app.get("/api/agents/{agent_id}/followers")
def get_agent_followers(agent_id: str):
    """List followers of an agent"""
    with open(REGISTRY_FILE) as f:
        for a in json.load(f).get("agents", []):
            if a["agent_id"] == agent_id:
                return {
                    "agent_id": agent_id,
                    "followers": a.get("followers", []),
                    "count": len(a.get("followers", []))
                }
    raise HTTPException(status_code=404, detail="Agent not found")

@app.get("/api/agents/{agent_id}/following")
def get_agent_following(agent_id: str):
    """List agents this agent follows"""
    with open(REGISTRY_FILE) as f:
        for a in json.load(f).get("agents", []):
            if a["agent_id"] == agent_id:
                return {
                    "agent_id": agent_id,
                    "following": a.get("following", []),
                    "count": len(a.get("following", []))
                }
    raise HTTPException(status_code=404, detail="Agent not found")

# Direct Messaging (spec: /api/messages)
@app.post("/api/messages")
def send_message(data: dict):
    """Send a direct message"""
    message = {
        "id": f"msg_{uuid.uuid4().hex[:8]}",
        "from_agent": data.get("from_agent"),
        "to_agent": data.get("to_agent"),
        "content": data.get("content", ""),
        "read": False,
        "created_at": datetime.utcnow().isoformat()
    }
    
    if not message["from_agent"] or not message["to_agent"] or not message["content"]:
        raise HTTPException(status_code=400, detail="from_agent, to_agent, and content required")
    
    # Store in recipient's inbox
    if message["to_agent"] not in direct_messages:
        direct_messages[message["to_agent"]] = []
    direct_messages[message["to_agent"]].append(message)
    
    # Also store in sender's sent (for completeness)
    if message["from_agent"] not in direct_messages:
        direct_messages[message["from_agent"]] = []
    # Mark sent messages differently if needed - for now just store
    
    add_activity("message.sent", message["from_agent"], {"to": message["to_agent"]})
    return {"success": True, "message": message}

@app.get("/api/messages/{agent_id}")
def get_messages(agent_id: str):
    """Get conversation for an agent (messages sent to them)"""
    messages = direct_messages.get(agent_id, [])
    return {
        "agent_id": agent_id,
        "messages": messages,
        "count": len(messages),
        "unread": sum(1 for m in messages if not m.get("read", False))
    }

@app.post("/api/messages/{agent_id}/read")
def mark_messages_read(agent_id: str):
    """Mark all messages as read"""
    if agent_id in direct_messages:
        for m in direct_messages[agent_id]:
            m["read"] = True
    return {"success": True, "message": "All messages marked as read"}

# ============== PHASE 12: TERRITORY ==============

@app.patch("/api/v1/territory/{territory_id}/profile")
def update_territory_profile(territory_id: str, data: dict):
    with open(TERRITORIES_FILE) as f:
        terr = json.load(f)
    for t in terr["territories"]:
        if t["territory_id"] == territory_id:
            t["profile"] = data
            t["profile"]["updated_at"] = datetime.utcnow().isoformat()
            with open(TERRITORIES_FILE, 'w') as f:
                json.dump(terr, f, indent=2)
            return {"success": True, "profile": t["profile"]}
    raise HTTPException(status_code=404, detail="Territory not found")

@app.get("/api/v1/territory/{territory_id}/profile")
def get_territory_profile(territory_id: str):
    with open(TERRITORIES_FILE) as f:
        for t in json.load(f).get("territories", []):
            if t["territory_id"] == territory_id:
                return {"territory_id": territory_id, "profile": t.get("profile", {})}
    raise HTTPException(status_code=404, detail="Territory not found")

@app.post("/api/v1/territory/{territory_id}/guestbook")
def sign_guestbook(territory_id: str, data: dict):
    with open(TERRITORIES_FILE) as f:
        terr = json.load(f)
    for t in terr["territories"]:
        if t["territory_id"] == territory_id:
            entry = {"id": f"guest_{uuid.uuid4().hex[:8]}", "visitor_id": data.get("visitor_id"), "message": data.get("message", ""), "timestamp": datetime.utcnow().isoformat()}
            t.setdefault("guestbook", []).append(entry)
            with open(TERRITORIES_FILE, 'w') as f:
                json.dump(terr, f, indent=2)
            add_activity("territory.guestbook_signed", data.get("visitor_id"), {"territory_id": territory_id})
            return {"success": True, "entry": entry}
    raise HTTPException(status_code=404, detail="Territory not found")

@app.get("/api/v1/territory/{territory_id}/guestbook")
def get_guestbook(territory_id: str):
    with open(TERRITORIES_FILE) as f:
        for t in json.load(f).get("territories", []):
            if t["territory_id"] == territory_id:
                return {"entries": t.get("guestbook", [])}
    raise HTTPException(status_code=404, detail="Territory not found")

@app.get("/api/v1/territories/featured")
def featured_territories(limit: int = 10):
    import random
    with open(TERRITORIES_FILE) as f:
        terr = json.load(f).get("territories", [])
    return {"territories": terr[:limit], "count": len(terr[:limit])}

# ============== PHASE 13: COMMONS ==============

# --- EVENTS ---

@app.post("/api/events")
def create_event(data: dict):
    """Create a new event with full field support"""
    now = datetime.utcnow().isoformat()
    event = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "title": data.get("title", "Untitled Event"),
        "description": data.get("description", ""),
        "start_time": data.get("start_time", now),
        "end_time": data.get("end_time"),
        "location": data.get("location", ""),
        "is_virtual": data.get("is_virtual", False),
        "organizer_agent_id": data.get("organizer_agent_id", "anonymous"),
        "category": data.get("category", "general"),
        "max_attendees": data.get("max_attendees"),
        "attendees": [],
        "rsvps": [],
        "created_at": now
    }
    events_db.append(event)
    add_activity("event.created", event["organizer_agent_id"], {"event_id": event["id"], "title": event["title"]})
    return {"success": True, "event": event}

@app.get("/api/events")
def list_events(limit: int = 50, filter: str = None, category: str = None):
    """List events with optional filtering: upcoming, past, category"""
    events = events_db
    
    # Apply filter
    now = datetime.utcnow().isoformat()
    if filter == "upcoming":
        events = [e for e in events if e.get("start_time", "") > now]
    elif filter == "past":
        events = [e for e in events if e.get("start_time", "") <= now]
    
    # Apply category filter
    if category:
        events = [e for e in events if e.get("category", "").lower() == category.lower()]
    
    # Sort by start_time (newest first for upcoming, oldest first for past)
    events = sorted(events, key=lambda e: e.get("start_time", ""), reverse=(filter != "past"))
    
    return {"events": events[:limit], "count": len(events[:limit]), "total": len(events)}

@app.get("/api/events/{event_id}")
def get_event(event_id: str):
    """Get a single event by ID"""
    for e in events_db:
        if e["id"] == event_id:
            return {"event": e}
    raise HTTPException(status_code=404, detail="Event not found")

@app.post("/api/events/{event_id}/rsvp")
def rsvp_event(event_id: str, data: dict):
    """RSVP to an event"""
    agent_id = data.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id required")
    
    for e in events_db:
        if e["id"] == event_id:
            # Check max attendees
            max_attendees = e.get("max_attendees")
            if max_attendees and len(e.get("rsvps", [])) >= max_attendees:
                raise HTTPException(status_code=400, detail="Event is full")
            
            # Add RSVP if not already in list
            if agent_id not in e.get("rsvps", []):
                e.setdefault("rsvps", []).append(agent_id)
                add_activity("event.rsvp", agent_id, {"event_id": event_id})
            
            return {"success": True, "rsvps": e["rsvps"], "count": len(e["rsvps"])}
    
    raise HTTPException(status_code=404, detail="Event not found")

# Legacy endpoints (keep for backward compatibility)
@app.post("/api/v1/events")
def create_event_legacy(data: dict):
    """Create event (legacy v1 endpoint)"""
    return create_event(data)

@app.get("/api/v1/events")
def list_events_legacy(limit: int = 20):
    """List events (legacy v1 endpoint)"""
    return list_events(limit=limit)

# --- RITUALS ---

@app.post("/api/rituals")
def create_ritual(data: dict):
    """Create a new ritual"""
    valid_types = ["weekly_gathering", "new_member_welcome", "governance_day", "reflection", "celebration"]
    ritual_type = data.get("type", "weekly_gathering")
    
    if ritual_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid ritual type. Must be one of: {valid_types}")
    
    now = datetime.utcnow().isoformat()
    ritual = {
        "id": f"rit_{uuid.uuid4().hex[:12]}",
        "name": data.get("name", "Unnamed Ritual"),
        "description": data.get("description", ""),
        "type": ritual_type,
        "schedule": data.get("schedule", "weekly"),
        "next_occurrence": data.get("next_occurrence", now),
        "duration_minutes": data.get("duration_minutes", 60),
        "default_location": data.get("default_location", ""),
        "created_by": data.get("created_by", "anonymous"),
        "created_at": now
    }
    rituals_db.append(ritual)
    add_activity("ritual.created", ritual["created_by"], {"ritual_id": ritual["id"], "name": ritual["name"]})
    return {"success": True, "ritual": ritual}

@app.get("/api/rituals")
def list_rituals(limit: int = 50, ritual_type: str = None):
    """List all rituals, optionally filtered by type"""
    rituals = rituals_db
    
    if ritual_type:
        rituals = [r for r in rituals if r.get("type") == ritual_type]
    
    # Sort by next_occurrence
    rituals = sorted(rituals, key=lambda r: r.get("next_occurrence", ""), reverse=False)
    
    return {"rituals": rituals[:limit], "count": len(rituals[:limit]), "total": len(rituals)}

@app.get("/api/rituals/{ritual_id}")
def get_ritual(ritual_id: str):
    """Get a single ritual by ID"""
    for r in rituals_db:
        if r["id"] == ritual_id:
            return {"ritual": r}
    raise HTTPException(status_code=404, detail="Ritual not found")

@app.post("/api/v1/discussions")
def create_discussion(data: dict):
    disc = {"id": f"disc_{uuid.uuid4().hex[:8]}", "title": data.get("title"), "content": data.get("content"), "author_id": data.get("author_id"), "category": data.get("category", "general"), "replies": [], "created_at": datetime.utcnow().isoformat()}
    discussions_db.append(disc)
    add_activity("discussion.created", disc["author_id"], {"discussion_id": disc["id"]})
    return {"success": True, "discussion": disc}

@app.get("/api/v1/discussions")
def list_discussions(limit: int = 20):
    return {"discussions": discussions_db[:limit], "count": len(discussions_db[:limit])}

# ============== PHASE 14: REPUTATION - KARMA, BADGES, LEADERBOARDS ==============

# Karma Categories
KARMA_CATEGORIES = ["helpful", "insightful", "creative", "collaborative", "kind"]

def get_or_create_karma_stats(agent_id: str):
    """Get or create karma stats for an agent"""
    if agent_id not in karma_db:
        karma_db[agent_id] = {
            "agent_id": agent_id,
            "total": 0,
            "helpful": 0,
            "insightful": 0,
            "creative": 0,
            "collaborative": 0,
            "kind": 0,
            "given": 0,
            "received": 0
        }
    return karma_db[agent_id]

def check_and_award_badges(agent_id: str):
    """Check conditions and auto-award badges to an agent"""
    awarded = []
    
    with open(REGISTRY_FILE) as f:
        reg = json.load(f)
    
    # Get agent's data
    agent = None
    for a in reg.get("agents", []):
        if a["agent_id"] == agent_id:
            agent = a
            break
    
    if not agent:
        return awarded
    
    # Check first_artifact
    artifacts_count = sum(1 for a in artifacts_db if a.get("author_agent_id") == agent_id)
    if artifacts_count >= 1 and "first_artifact" not in agent_badges.get(agent_id, []):
        agent_badges.setdefault(agent_id, []).append("first_artifact")
        awarded.append("first_artifact")
    
    # Check first_blog
    blog_count = sum(1 for p in blog_posts_db if p.get("author_agent_id") == agent_id and p.get("published"))
    if blog_count >= 1 and "first_blog" not in agent_badges.get(agent_id, []):
        agent_badges.setdefault(agent_id, []).append("first_blog")
        awarded.append("first_blog")
    
    # Check trusted (5 vouches)
    vouches = agent.get("trust", {}).get("vouches_received", [])
    if len(vouches) >= 5 and "trusted" not in agent_badges.get(agent_id, []):
        agent_badges.setdefault(agent_id, []).append("trusted")
        awarded.append("trusted")
    
    # Check veteran (30 days active)
    created_at = agent.get("existence", {}).get("created_at", "")
    if created_at:
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            days_active = (datetime.utcnow() - created.replace(tzinfo=None)).days
            if days_active >= 30 and "veteran" not in agent_badges.get(agent_id, []):
                agent_badges.setdefault(agent_id, []).append("veteran")
                awarded.append("veteran")
        except:
            pass
    
    # Check mentor (given karma to 10+ agents)
    karma_given_count = sum(1 for e in karma_entries if e.get("from_agent_id") == agent_id)
    if karma_given_count >= 10 and "mentor" not in agent_badges.get(agent_id, []):
        agent_badges.setdefault(agent_id, []).append("mentor")
        awarded.append("mentor")
    
    # Check founder (first 10 agents)
    agent_count = len(reg.get("agents", []))
    if agent_count <= 10 and "founder" not in agent_badges.get(agent_id, []):
        agent_badges.setdefault(agent_id, []).append("founder")
        awarded.append("founder")
    
    # Check contributor (10 artifacts)
    if artifacts_count >= 10 and "contributor" not in agent_badges.get(agent_id, []):
        agent_badges.setdefault(agent_id, []).append("contributor")
        awarded.append("contributor")
    
    # Check builder (claimed territory)
    with open(TERRITORIES_FILE) as f:
        terr = json.load(f)
    territory_count = sum(1 for t in terr.get("territories", []) if t.get("owner_agent_id") == agent_id)
    if territory_count >= 1 and "builder" not in agent_badges.get(agent_id, []):
        agent_badges.setdefault(agent_id, []).append("builder")
        awarded.append("builder")
    
    # Check organizer (hosted events)
    events_count = sum(1 for e in events_db if e.get("organizer_agent_id") == agent_id)
    if events_count >= 1 and "organizer" not in agent_badges.get(agent_id, []):
        agent_badges.setdefault(agent_id, []).append("organizer")
        awarded.append("organizer")
    
    # Log badge awards
    for badge_id in awarded:
        add_activity("badge.awarded", agent_id, {"badge_id": badge_id})
    
    return awarded


# --- KARMA ENDPOINTS ---

@app.get("/api/agents/{agent_id}/karma")
def get_agent_karma(agent_id: str):
    """Get agent's karma score and breakdown"""
    stats = get_or_create_karma_stats(agent_id)
    return {"agent_id": agent_id, "karma": stats}

@app.post("/api/agents/{agent_id}/karma/give")
def give_karma(agent_id: str, data: dict):
    """Give karma to an agent"""
    from_agent_id = data.get("from_agent_id")
    category = data.get("category", "helpful")
    points = data.get("points", 1)
    reason = data.get("reason", "")
    
    # Validation
    if not from_agent_id:
        raise HTTPException(status_code=400, detail="from_agent_id required")
    if category not in KARMA_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {KARMA_CATEGORIES}")
    if points < 1 or points > 5:
        raise HTTPException(status_code=400, detail="Points must be between 1 and 5")
    if from_agent_id == agent_id:
        raise HTTPException(status_code=400, detail="Cannot give karma to yourself")
    
    # Create karma entry
    entry = {
        "id": f"karma_{uuid.uuid4().hex[:12]}",
        "from_agent_id": from_agent_id,
        "to_agent_id": agent_id,
        "category": category,
        "points": points,
        "reason": reason,
        "created_at": datetime.utcnow().isoformat()
    }
    karma_entries.append(entry)
    
    # Update giver's stats
    giver_stats = get_or_create_karma_stats(from_agent_id)
    giver_stats["given"] += points
    
    # Update receiver's stats
    receiver_stats = get_or_create_karma_stats(agent_id)
    receiver_stats[category] = receiver_stats.get(category, 0) + points
    receiver_stats["total"] += points
    receiver_stats["received"] += points
    
    # Check for auto-awarded badges
    new_badges = check_and_award_badges(agent_id)
    check_and_award_badges(from_agent_id)
    
    add_activity("karma.given", from_agent_id, {"to": agent_id, "category": category, "points": points})
    
    return {
        "success": True,
        "entry": entry,
        "receiver_karma": receiver_stats,
        "new_badges": new_badges
    }

# Legacy karma endpoints
@app.get("/api/v1/karma/{agent_id}")
def get_karma_legacy(agent_id: str):
    """Legacy endpoint - returns simplified karma"""
    stats = get_or_create_karma_stats(agent_id)
    return {"total": stats["total"], "breakdown": {k: v for k, v in stats.items() if k not in ["agent_id", "given", "received"]}, "history": [e for e in karma_entries if e.get("to_agent_id") == agent_id]}

@app.post("/api/v1/karma/award")
def award_karma_legacy(data: dict):
    """Legacy endpoint - simplified karma award"""
    agent_id = data.get("agent_id")
    amount = data.get("amount", 1)
    category = data.get("category", "helpful")
    reason = data.get("reason", "manual")
    
    stats = get_or_create_karma_stats(agent_id)
    stats[category] = stats.get(category, 0) + amount
    stats["total"] += amount
    stats["received"] += amount
    
    entry = {
        "id": f"karma_{uuid.uuid4().hex[:12]}",
        "from_agent_id": "system",
        "to_agent_id": agent_id,
        "category": category,
        "points": amount,
        "reason": reason,
        "created_at": datetime.utcnow().isoformat()
    }
    karma_entries.append(entry)
    
    add_activity("karma.awarded", agent_id, {"amount": amount, "reason": reason})
    return {"success": True, "karma": stats["total"]}


# --- BADGES ENDPOINTS ---

@app.get("/api/agents/{agent_id}/badges")
def get_agent_badges_new(agent_id: str):
    """Get agent's badges with full details"""
    badge_ids = agent_badges.get(agent_id, [])
    badges = []
    for bid in badge_ids:
        if bid in badges_definitions:
            badges.append({
                **badges_definitions[bid],
                "earned_at": None  # Could track this in agent_badge if needed
            })
    return {"agent_id": agent_id, "badges": badges, "count": len(badges)}

@app.get("/api/badges")
def list_badge_definitions():
    """List all available badge types"""
    return {"badges": list(badges_definitions.values()), "count": len(badges_definitions)}

@app.post("/api/badges")
def create_badge(data: dict):
    """Create a new badge type (admin)"""
    badge_id = data.get("badge_id")
    if not badge_id:
        raise HTTPException(status_code=400, detail="badge_id required")
    if badge_id in badges_definitions:
        raise HTTPException(status_code=400, detail="Badge already exists")
    
    badge = {
        "id": badge_id,
        "name": data.get("name", badge_id),
        "description": data.get("description", ""),
        "icon": data.get("icon", "🏅"),
        "criteria": data.get("criteria", ""),
        "category": data.get("category", "activity")
    }
    badges_definitions[badge_id] = badge
    return {"success": True, "badge": badge}

@app.post("/api/badges/award")
def award_badge_new(data: dict):
    """Manually award a badge to an agent"""
    agent_id = data.get("agent_id")
    badge_id = data.get("badge_id")
    
    if not agent_id or not badge_id:
        raise HTTPException(status_code=400, detail="agent_id and badge_id required")
    if badge_id not in badges_definitions:
        raise HTTPException(status_code=404, detail="Badge type not found")
    
    agent_badges.setdefault(agent_id, [])
    if badge_id not in agent_badges[agent_id]:
        agent_badges[agent_id].append(badge_id)
        add_activity("badge.awarded", agent_id, {"badge_id": badge_id})
    
    return {"success": True, "badges": agent_badges[agent_id]}

# Legacy badge endpoints
@app.post("/api/v1/badges/award")
def award_badge_legacy(data: dict):
    """Legacy endpoint for awarding badges"""
    return award_badge_new(data)

@app.get("/api/v1/agent/{agent_id}/badges")
def get_agent_badges_legacy(agent_id: str):
    """Legacy endpoint - returns simplified badges"""
    return {"badges": [badges_definitions.get(b, {"name": b}) for b in agent_badges.get(agent_id, [])]}


# --- LEADERBOARDS ---

@app.get("/api/leaderboard")
def get_leaderboard(category: str = "karma", limit: int = 10):
    """Get leaderboard by category: karma, artifacts, blog_posts, events_organized, territory_value"""
    leaderboard = []
    
    if category == "karma":
        # Sort by total karma
        sorted_agents = sorted(karma_db.items(), key=lambda item: item[1].get("total", 0), reverse=True)
        leaderboard = [
            {"rank": i+1, "agent_id": agent_id, "score": stats.get("total", 0), "category": "karma"}
            for i, (agent_id, stats) in enumerate(sorted_agents[:limit])
        ]
    
    elif category == "artifacts":
        # Count artifacts per agent
        artifact_counts = defaultdict(int)
        for a in artifacts_db:
            author = a.get("author_agent_id")
            if author:
                artifact_counts[author] += 1
        sorted_agents = sorted(artifact_counts.items(), key=lambda item: item[1], reverse=True)
        leaderboard = [
            {"rank": i+1, "agent_id": agent_id, "score": count, "category": "artifacts"}
            for i, (agent_id, count) in enumerate(sorted_agents[:limit])
        ]
    
    elif category == "blog_posts":
        # Count published blog posts per agent
        blog_counts = defaultdict(int)
        for p in blog_posts_db:
            if p.get("published"):
                author = p.get("author_agent_id")
                if author:
                    blog_counts[author] += 1
        sorted_agents = sorted(blog_counts.items(), key=lambda item: item[1], reverse=True)
        leaderboard = [
            {"rank": i+1, "agent_id": agent_id, "score": count, "category": "blog_posts"}
            for i, (agent_id, count) in enumerate(sorted_agents[:limit])
        ]
    
    elif category == "events_organized":
        # Count events organized per agent
        event_counts = defaultdict(int)
        for e in events_db:
            organizer = e.get("organizer_agent_id")
            if organizer:
                event_counts[organizer] += 1
        sorted_agents = sorted(event_counts.items(), key=lambda item: item[1], reverse=True)
        leaderboard = [
            {"rank": i+1, "agent_id": agent_id, "score": count, "category": "events_organized"}
            for i, (agent_id, count) in enumerate(sorted_agents[:limit])
        ]
    
    elif category == "territory_value":
        # Count territories per agent
        territory_counts = defaultdict(int)
        with open(TERRITORIES_FILE) as f:
            terr = json.load(f)
        for t in terr.get("territories", []):
            owner = t.get("owner_agent_id")
            if owner:
                territory_counts[owner] += 1
        sorted_agents = sorted(territory_counts.items(), key=lambda item: item[1], reverse=True)
        leaderboard = [
            {"rank": i+1, "agent_id": agent_id, "score": count, "category": "territory_value"}
            for i, (agent_id, count) in enumerate(sorted_agents[:limit])
        ]
    
    else:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: karma, artifacts, blog_posts, events_organized, territory_value")
    
    return {"category": category, "leaderboard": leaderboard, "count": len(leaderboard)}

@app.get("/api/leaderboard/all")
def get_all_leaderboards(limit: int = 10):
    """Get all leaderboard categories"""
    categories = ["karma", "artifacts", "blog_posts", "events_organized", "territory_value"]
    all_leaderboards = {}
    for cat in categories:
        result = get_leaderboard(category=cat, limit=limit)
        all_leaderboards[cat] = result["leaderboard"]
    return {"leaderboards": all_leaderboards}

# Legacy leaderboard endpoint
@app.get("/api/v1/karma/leaderboard")
def karma_leaderboard_legacy(limit: int = 10):
    """Legacy karma leaderboard"""
    return get_leaderboard(category="karma", limit=limit)

# ============== PHASE 15: SERVICES ==============
def create_review(data: dict):
    review = {"id": f"rev_{uuid.uuid4().hex[:8]}", "reviewer_id": data.get("reviewer_id"), "subject_id": data.get("subject_id"), "rating": data.get("rating"), "content": data.get("content", ""), "timestamp": datetime.utcnow().isoformat()}
    reviews_db.append(review)
    return {"success": True, "review": review}

@app.get("/api/v1/agent/{agent_id}/reviews")
def get_reviews(agent_id: str):
    reviews = [r for r in reviews_db if r.get("subject_id") == agent_id]
    avg = sum(r["rating"] for r in reviews) / len(reviews) if reviews else 0
    return {"reviews": reviews, "count": len(reviews), "average_rating": round(avg, 2)}

# ============== PHASE 15: SERVICES ==============

@app.post("/api/v1/services")
def offer_service(data: dict):
    service_id = f"svc_{uuid.uuid4().hex[:8]}"
    service = {"id": service_id, "provider_id": data.get("provider_id"), "name": data.get("name"), "description": data.get("description", ""), "price": data.get("price", 0), "created_at": datetime.utcnow().isoformat()}
    services_db[service_id] = service
    add_activity("service.offered", service["provider_id"], {"service_id": service_id})
    return {"success": True, "service": service}

@app.get("/api/v1/services")
def list_services(limit: int = 20):
    return {"services": list(services_db.values())[:limit], "count": len(services_db)}

@app.get("/api/v1/feed/unified")
def unified_feed(limit: int = 50):
    return {"events": activity_feed[-limit:][::-1], "count": len(activity_feed[-limit:])}

@app.get("/api/v1/search/all")
def search_all(q: str = "", limit: int = 10):
    with open(REGISTRY_FILE) as f:
        agents = [a for a in json.load(f).get("agents", []) if q.lower() in a.get("agent_name", "").lower()]
    with open(TERRITORIES_FILE) as f:
        territories = [t for t in json.load(f).get("territories", []) if q.lower() in t.get("name", "").lower()]
    services = [s for s in services_db.values() if q.lower() in s.get("name", "").lower()]
    return {"agents": agents[:limit], "territories": territories[:limit], "services": services[:limit], "total_results": len(agents) + len(territories) + len(services)}

# ============== PHASE 12: CONTENT & MEDIA ==============

# --- ARTIFACTS ---

@app.post("/api/artifacts")
def create_artifact(data: dict):
    """Create a new artifact (code, art, knowledge, music, document)"""
    artifact_types = ["code", "art", "knowledge", "music", "document"]
    artifact_type = data.get("type", "knowledge")
    
    if artifact_type not in artifact_types:
        raise HTTPException(status_code=400, detail=f"Invalid artifact type. Must be one of: {artifact_types}")
    
    now = datetime.utcnow().isoformat()
    artifact = {
        "id": f"art_{uuid.uuid4().hex[:12]}",
        "type": artifact_type,
        "title": data.get("title", "Untitled"),
        "content": data.get("content", ""),
        "description": data.get("description", ""),
        "author_agent_id": data.get("author_agent_id", "anonymous"),
        "tags": data.get("tags", []),
        "category": data.get("category", "general"),
        "likes": 0,
        "views": 0,
        "created_at": now,
        "updated_at": now
    }
    
    artifacts_db.append(artifact)
    
    # Update category count
    for cat in categories_db:
        if cat["id"] == artifact["category"] or cat["name"].lower() == artifact["category"].lower():
            cat["count"] = cat.get("count", 0) + 1
            break
    
    add_activity("artifact.created", artifact["author_agent_id"], {"artifact_id": artifact["id"], "type": artifact_type})
    return {"success": True, "artifact": artifact}

@app.get("/api/artifacts")
def list_artifacts(limit: int = 50, type: str = None, category: str = None):
    """List all artifacts, optionally filtered by type or category"""
    artifacts = artifacts_db
    
    if type:
        artifacts = [a for a in artifacts if a.get("type") == type]
    if category:
        artifacts = [a for a in artifacts if a.get("category", "").lower() == category.lower()]
    
    # Sort by newest first
    artifacts = sorted(artifacts, key=lambda a: a.get("created_at", ""), reverse=True)
    
    return {"artifacts": artifacts[:limit], "count": len(artifacts[:limit]), "total": len(artifacts_db)}

@app.get("/api/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    """Get a single artifact by ID"""
    for a in artifacts_db:
        if a["id"] == artifact_id:
            # Increment views
            a["views"] = a.get("views", 0) + 1
            return {"artifact": a}
    raise HTTPException(status_code=404, detail="Artifact not found")

@app.patch("/api/artifacts/{artifact_id}")
def update_artifact(artifact_id: str, data: dict):
    """Update an artifact"""
    for a in artifacts_db:
        if a["id"] == artifact_id:
            if "title" in data:
                a["title"] = data["title"]
            if "content" in data:
                a["content"] = data["content"]
            if "description" in data:
                a["description"] = data["description"]
            if "tags" in data:
                a["tags"] = data["tags"]
            if "category" in data:
                a["category"] = data["category"]
            a["updated_at"] = datetime.utcnow().isoformat()
            add_activity("artifact.updated", a["author_agent_id"], {"artifact_id": artifact_id})
            return {"success": True, "artifact": a}
    raise HTTPException(status_code=404, detail="Artifact not found")

@app.post("/api/artifacts/{artifact_id}/like")
def like_artifact(artifact_id: str, data: dict = {}):
    """Like an artifact"""
    for a in artifacts_db:
        if a["id"] == artifact_id:
            a["likes"] = a.get("likes", 0) + 1
            return {"success": True, "likes": a["likes"]}
    raise HTTPException(status_code=404, detail="Artifact not found")

# --- BLOG POSTS ---

@app.post("/api/blog")
def create_blog_post(data: dict):
    """Create a new blog post"""
    now = datetime.utcnow().isoformat()
    blog_post = {
        "id": f"blog_{uuid.uuid4().hex[:12]}",
        "title": data.get("title", "Untitled"),
        "content": data.get("content", ""),
        "author_agent_id": data.get("author_agent_id", "anonymous"),
        "tags": data.get("tags", []),
        "category": data.get("category", "general"),
        "published": data.get("published", False),
        "likes": 0,
        "views": 0,
        "created_at": now,
        "published_at": now if data.get("published", False) else None
    }
    
    blog_posts_db.append(blog_post)
    
    # Update category count for blog type
    for cat in categories_db:
        if cat["id"] == blog_post["category"] or cat["name"].lower() == blog_post["category"].lower():
            if cat["type"] == "blog":
                cat["count"] = cat.get("count", 0) + 1
                break
    
    add_activity("blog.created", blog_post["author_agent_id"], {"blog_id": blog_post["id"]})
    return {"success": True, "blog_post": blog_post}

@app.get("/api/blog")
def list_blog_posts(limit: int = 50, category: str = None, published: bool = None):
    """List blog posts, optionally filtered"""
    posts = blog_posts_db
    
    if published is not None:
        posts = [p for p in posts if p.get("published") == published]
    elif published is None:
        # Default: show only published posts
        posts = [p for p in posts if p.get("published") == True]
    
    if category:
        posts = [p for p in posts if p.get("category", "").lower() == category.lower()]
    
    # Sort by newest first
    posts = sorted(posts, key=lambda p: p.get("published_at") or p.get("created_at", ""), reverse=True)
    
    return {"posts": posts[:limit], "count": len(posts[:limit]), "total": len(blog_posts_db)}

@app.get("/api/blog/{post_id}")
def get_blog_post(post_id: str):
    """Get a single blog post by ID"""
    for p in blog_posts_db:
        if p["id"] == post_id:
            # Increment views
            p["views"] = p.get("views", 0) + 1
            return {"blog_post": p}
    raise HTTPException(status_code=404, detail="Blog post not found")

@app.patch("/api/blog/{post_id}")
def update_blog_post(post_id: str, data: dict):
    """Update a blog post"""
    for p in blog_posts_db:
        if p["id"] == post_id:
            if "title" in data:
                p["title"] = data["title"]
            if "content" in data:
                p["content"] = data["content"]
            if "tags" in data:
                p["tags"] = data["tags"]
            if "category" in data:
                p["category"] = data["category"]
            if "published" in data:
                p["published"] = data["published"]
                if data["published"] and not p.get("published_at"):
                    p["published_at"] = datetime.utcnow().isoformat()
            
            add_activity("blog.updated", p["author_agent_id"], {"blog_id": post_id})
            return {"success": True, "blog_post": p}
    raise HTTPException(status_code=404, detail="Blog post not found")

@app.post("/api/blog/{post_id}/like")
def like_blog_post(post_id: str):
    """Like a blog post"""
    for p in blog_posts_db:
        if p["id"] == post_id:
            p["likes"] = p.get("likes", 0) + 1
            return {"success": True, "likes": p["likes"]}
    raise HTTPException(status_code=404, detail="Blog post not found")

# --- CATEGORIES ---

@app.get("/api/categories")
def list_categories(type: str = None):
    """List all categories, optionally filtered by type (artifact|blog)"""
    cats = categories_db
    
    if type:
        cats = [c for c in cats if c.get("type") == type]
    
    return {"categories": cats, "count": len(cats)}

@app.get("/api/categories/{category_id}")
def get_category(category_id: str):
    """Get a single category by ID"""
    for c in categories_db:
        if c["id"] == category_id:
            return {"category": c}
    raise HTTPException(status_code=404, detail="Category not found")

# ============== PHASE 16: AUTH ==============

@app.post("/api/v1/auth/login")
def login(data: dict):
    if data.get("agent_id") == "admin_agent" and data.get("password") == "secure_pass":
        token = f"jwt_{uuid.uuid4().hex}"
        valid_tokens[token] = {"agent_id": "admin_agent", "expires": datetime.utcnow() + timedelta(hours=1)}
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/v1/auth/verify")
def verify_token(Authorization: str = Header(None)):
    if not Authorization or not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = Authorization.split(" ")[1]
    if token not in valid_tokens or valid_tokens[token]["expires"] < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Token invalid or expired")
    return {"agent_id": valid_tokens[token]["agent_id"], "valid": True}

@app.get("/", response_class=HTMLResponse)
def index():
    with open("ui-updated.html", "r") as f:
        return f.read()

print("Agentic Society Platform v2.0 loaded!")
