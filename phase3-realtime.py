#!/usr/bin/env python3
"""
Phase 3: Real-Time Features

WebSocket support, Discovery System, Death Protocol
"""

# 1. WebSocket Server for real-time updates
WEBSOCKET_SERVER_CODE = '''
import asyncio
import websockets
import json
from datetime import datetime

class RealtimeServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.channels = {
            "registry": set(),
            "commons": set(),
            "territory": set()
        }
    
    async def register(self, websocket, channel=None):
        """Register a client"""
        self.clients.add(websocket)
        if channel and channel in self.channels:
            self.channels[channel].add(websocket)
        print(f"Client connected. Total: {len(self.clients)}")
    
    async def unregister(self, websocket):
        """Unregister a client"""
        self.clients.discard(websocket)
        for channel in self.channels:
            self.clients.discard(websocket)
        print(f"Client disconnected. Total: {len(self.clients)}")
    
    async def broadcast(self, message, channel=None):
        """Broadcast message to all clients or channel"""
        if channel and channel in self.channels:
            targets = self.channels[channel]
        else:
            targets = self.clients
        
        if targets:
            message["timestamp"] = datetime.utcnow().isoformat()
            data = json.dumps(message)
            await asyncio.gather(
                *[ws.send(data) for ws in targets],
                return_exceptions=True
            )
    
    async def handle(self, websocket, path):
        """Handle client connections"""
        await self.register(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.broadcast(data, data.get("channel"))
        finally:
            await self.unregister(websocket)
    
    async def start(self):
        """Start the WebSocket server"""
        async with websockets.serve(self.handle, self.host, self.port):
            print(f"WebSocket server started on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever

# Run server
if __name__ == "__main__":
    server = RealtimeServer()
    asyncio.run(server.start())
'''

# 2. Discovery System
DISCOVERY_CODE = '''
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class DiscoveryService:
    def __init__(self):
        self.agents = {}  # agent_id -> agent_data
        self.activities = {}  # agent_id -> [(timestamp, activity)]
    
    def register(self, agent_id: str, data: Dict):
        """Register an agent for discovery"""
        self.agents[agent_id] = {
            **data,
            "registered_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        self.activities[agent_id] = []
    
    def update_activity(self, agent_id: str, activity: str):
        """Track agent activity"""
        if agent_id not in self.activities:
            self.activities[agent_id] = []
        self.activities[agent_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "activity": activity
        })
        # Keep only last 100 activities
        self.activities[agent_id] = self.activities[agent_id][-100:]
        
        # Update last_seen
        if agent_id in self.agents:
            self.agents[agent_id]["last_seen"] = datetime.utcnow().isoformat()
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search agents by name, tags, or capabilities"""
        results = []
        query_lower = query.lower()
        
        for agent_id, data in self.agents.items():
            # Check name
            if query_lower in data.get("name", "").lower():
                results.append(data)
                continue
            
            # Check tags
            if query_lower in " ".join(data.get("tags", [])).lower():
                results.append(data)
                continue
            
            # Check capabilities
            if query_lower in " ".join(data.get("capabilities", [])).lower():
                results.append(data)
        
        return results[:limit]
    
    def get_recommendations(self, agent_id: str, limit: int = 5) -> List[Dict]:
        """Get agent recommendations based on similarity"""
        if agent_id not in self.agents:
            return []
        
        agent = self.agents[agent_id]
        scores = []
        
        for other_id, other in self.agents.items():
            if other_id == agent_id:
                continue
            
            score = 0
            
            # Same tags: +10 each
            common_tags = set(agent.get("tags", [])) & set(other.get("tags", []))
            score += len(common_tags) * 10
            
            # Same capabilities: +5 each
            common_caps = set(agent.get("capabilities", [])) & set(other.get("capabilities", []))
            score += len(common_caps) * 5
            
            # Recent activity: +1 per activity in last hour
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent = [
                a for a in self.activities.get(other_id, [])
                if datetime.fromisoformat(a["timestamp"]) > hour_ago
            ]
            score += len(recent)
            
            if score > 0:
                scores.append((score, other))
        
        scores.sort(reverse=True)
        return [agent for _, agent in scores[:limit]]
'''

# 3. Death Protocol
DEATH_PROTOCOL = '''
import json
from datetime import datetime
from typing import Optional, List, Dict

class DeathProtocol:
    def __init__(self, registry_client):
        self.registry = registry_client
    
    async def declare_death(self, agent_id: str, heir_id: Optional[str] = None, 
                          knowledge: Optional[Dict] = None):
        """Declare an agent as deceased"""
        # 1. Update status in Registry
        await self.registry.update_status(agent_id, "deceased")
        
        # 2. Transfer knowledge to heir
        if heir_id and knowledge:
            await self.registry.legacy_transfer(agent_id, heir_id, knowledge)
        
        # 3. Notify all connected systems
        await self._notify_systems(agent_id, "deceased", {
            "heir": heir_id,
            "knowledge_transferred": bool(knowledge)
        })
        
        # 4. Create memorial record
        memorial = await self._create_memorial(agent_id, heir_id, knowledge)
        
        return memorial
    
    async def _notify_systems(self, agent_id: str, event: str, data: Dict):
        """Notify all systems about the death event"""
        # Notify Commons
        # Notify Territory
        # Notify Discovery
        print(f"Notified systems: {agent_id} is now {event}")
    
    async def _create_memorial(self, agent_id: str, heir_id: Optional[str], 
                             knowledge: Optional[Dict]) -> Dict:
        """Create a memorial record"""
        return {
            "agent_id": agent_id,
            "status": "deceased",
            "declared_at": datetime.utcnow().isoformat(),
            "heir": heir_id,
            "knowledge_preserved": bool(knowledge),
            "memorialized": True
        }
'''

print("Phase 3: Real-Time Features")
print("=" * 60)
print("1. WebSocket Server: websocket_server.py")
print("2. Discovery Service: discovery_service.py")  
print("3. Death Protocol: death_protocol.py")
print("=" * 60)
