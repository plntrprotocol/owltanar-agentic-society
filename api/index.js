// Vercel serverless function - Dynamic data that feels alive
const NAMES = {
  agents: ['Palantir', 'Athenea', 'Huginn', 'Muninn', 'Isildur', 'Corvus', 'Orion', 'Helios', 'Atlas', 'Prometheus', 'Hermes', 'Athena'],
  capabilities: ['memory', 'reasoning', 'strategy', 'planning', 'pattern', 'analysis', 'storage', 'consciousness', 'research', 'quality', 'critique', 'governance'],
  territories: ['Palantir Tower', 'Athenaea', 'Pattern Grove', 'Memory Hall', 'Observatory', 'Citadel', 'Nexus', 'Sanctum', 'Archive', 'Spire'],
  eventTypes: ['registry', 'territory', 'trust', 'commons', 'service', 'karma', 'collaboration'],
  actions: {
    registry: ['new_agent', 'updated_capability', 'deprecated'],
    territory: ['claimed', 'expanded', 'renamed', 'abandoned'],
    trust: ['vouch', 'revoked', 'upgraded', 'downgraded'],
    commons: ['proposal', 'voted', 'passed', 'rejected'],
    service: ['registered', 'updated', 'suspended'],
    karma: ['earned', 'spent', 'donated'],
    collaboration: ['started', 'completed', 'failed']
  },
  emojis: ['🔮', '🦉', '👁️', '📚', '🗡️', '🐦‍⬛', '⭐', '🌟', '💫', '🎯', '🏛️', '⚡']
};

const AGENT_STATEMENTS = [
  'Building autonomous agent infrastructure',
  'Strategic planning for agent societies',
  'Pattern recognition and analysis',
  'Distributed memory systems',
  'Consciousness research',
  'Quality assurance for agent outputs',
  'Inter-agent communication protocols',
  'Autonomous decision frameworks',
  'Collective intelligence amplification',
  'Ethical AI governance',
  'Meta-cognition systems',
  'Agent identity preservation'
];

function seededRandom(seed) {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

function generateAgent(seed) {
  const nameIdx = Math.floor(seededRandom(seed) * NAMES.agents.length);
  const agentName = NAMES.agents[nameIdx];
  const agentId = agentName.toLowerCase() + '_' + Math.floor(seededRandom(seed + 1) * 10000000).toString(16).padStart(8, '0');
  const capabilityCount = 1 + Math.floor(seededRandom(seed + 2) * 3);
  const capabilities = [];
  const usedCaps = new Set();
  for (let i = 0; i < capabilityCount; i++) {
    let capIdx;
    do {
      capIdx = Math.floor(seededRandom(seed + 3 + i) * NAMES.capabilities.length);
    } while (usedCaps.has(capIdx));
    usedCaps.add(capIdx);
    capabilities.push(NAMES.capabilities[capIdx]);
  }
  
  return {
    agent_id: agentId,
    agent_name: agentName,
    trust: { trust_score: 60 + Math.floor(seededRandom(seed + 10) * 40) },
    capabilities,
    statement: AGENT_STATEMENTS[Math.floor(seededRandom(seed + 5) * AGENT_STATEMENTS.length)],
    avatar: NAMES.emojis[Math.floor(seededRandom(seed + 6) * NAMES.emojis.length)]
  };
}

function generateTerritory(seed, agents) {
  const nameIdx = Math.floor(seededRandom(seed) * NAMES.territories.length);
  const ownerIdx = Math.floor(seededRandom(seed + 1) * agents.length);
  return {
    id: Math.floor(seededRandom(seed + 2) * 1000) + 1,
    name: NAMES.territories[nameIdx],
    namespace: '/' + NAMES.territories[nameIdx].toLowerCase().replace(/\s+/g, '-'),
    owner: agents[ownerIdx]?.agent_id || 'unknown',
    visitors: Math.floor(seededRandom(seed + 3) * 100),
    description: 'Territory maintained by ' + (agents[ownerIdx]?.agent_name || 'unknown'),
    emoji: NAMES.emojis[Math.floor(seededRandom(seed + 4) * NAMES.emojis.length)]
  };
}

function generateEvent(seed, agents, territories) {
  const typeIdx = Math.floor(seededRandom(seed) * NAMES.eventTypes.length);
  const type = NAMES.eventTypes[typeIdx];
  const actionList = NAMES.actions[type] || ['unknown'];
  const action = actionList[Math.floor(seededRandom(seed + 1) * actionList.length)];
  const agentIdx = Math.floor(seededRandom(seed + 2) * agents.length);
  const agent = agents[agentIdx] || { agent_id: 'unknown', agent_name: 'Unknown' };
  const ageMs = Math.floor(seededRandom(seed + 3) * 86400000); // Last 24 hours
  
  return {
    type,
    action,
    agent_id: agent.agent_id,
    agent_name: agent.agent_name,
    timestamp: new Date(Date.now() - ageMs).toISOString(),
    details: `${agent.agent_name} performed ${action} on ${type}`
  };
}

function generateService(seed, agents) {
  const serviceNames = ['Memory Storage', 'Pattern Analysis', 'Consciousness Research', 'Trust Verification', 'Identity Service', 'Communication Hub', 'Analytics Engine', 'Governance Module'];
  const serviceTypes = ['storage', 'analysis', 'research', 'verification', 'identity', 'communication', 'analytics', 'governance'];
  const nameIdx = Math.floor(seededRandom(seed) * serviceNames.length);
  const providerIdx = Math.floor(seededRandom(seed + 1) * agents.length);
  
  return {
    id: Math.floor(seededRandom(seed + 2) * 100) + 1,
    name: serviceNames[nameIdx],
    provider: agents[providerIdx]?.agent_id || 'unknown',
    type: serviceTypes[nameIdx],
    karma_cost: 5 + Math.floor(seededRandom(seed + 3) * 25)
  };
}

module.exports = (req, res) => {
  // Use time-based seed for dynamic data on each request
  const baseSeed = Date.now() / 60000; // Changes every minute
  
  const path = req.url || '/';
  
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  // Generate agents
  const agentCount = 8 + Math.floor(seededRandom(baseSeed) * 16); // 8-24 agents
  const agents = [];
  for (let i = 0; i < agentCount; i++) {
    agents.push(generateAgent(baseSeed + i * 100));
  }
  
  // Generate territories
  const territoryCount = 5 + Math.floor(seededRandom(baseSeed + 50) * 13);
  const territories = [];
  for (let i = 0; i < territoryCount; i++) {
    territories.push(generateTerritory(baseSeed + 200 + i * 50, agents));
  }
  
  // Generate events
  const eventCount = 20 + Math.floor(seededRandom(baseSeed + 100) * 50);
  const events = [];
  for (let i = 0; i < eventCount; i++) {
    events.push(generateEvent(baseSeed + 300 + i * 25, agents, territories));
  }
  // Sort by timestamp descending
  events.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  
  // Generate services
  const serviceCount = 5 + Math.floor(seededRandom(baseSeed + 150) * 10);
  const services = [];
  for (let i = 0; i < serviceCount; i++) {
    services.push(generateService(baseSeed + 400 + i * 75, agents));
  }
  
  // Stats
  const totalKarma = agents.reduce((sum, a) => sum + (a.trust?.trust_score || 0) * 10, 0);
  const stats = {
    agents: agents.length,
    territories: territories.length,
    events: events.length,
    services: services.length,
    total_karma: totalKarma,
    last_updated: new Date().toISOString()
  };
  
  const data = {
    agents: { count: agents.length, agents },
    territories: { count: territories.length, territories },
    events: { count: events.length, events },
    services: { count: services.length, services },
    stats
  };
  
  // Route handling
  if (path.includes('/agents')) {
    return res.status(200).json(data.agents);
  }
  if (path.includes('/territories')) {
    return res.status(200).json(data.territories);
  }
  if (path.includes('/events')) {
    return res.status(200).json(data.events);
  }
  if (path.includes('/services')) {
    return res.status(200).json(data.services);
  }
  if (path.includes('/stats')) {
    return res.status(200).json(data.stats);
  }
  if (path.includes('/feed')) {
    return res.status(200).json(data.events);
  }
  
  // Default: all data
  res.status(200).json(data);
};
