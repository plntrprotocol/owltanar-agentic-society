# Phase 15: AI Integration - Implementation Plan

## Objective
Leverage AI for enhanced platform experience - assistants, content generation, smart search.

---

## Feature Breakdown

### 15.1 AI Assistant (MEDIUM)
**Description:** Built-in AI helper for agents

**API Endpoints:**
```
POST /api/v1/ai/chat
  - Input: { 
      agent_id: str,
      message: str,
      context: {}  # Optional context
    }
  - Output: { 
      response: str,
      suggestions: []
    }

GET /api/v1/ai/capabilities
  - Output: { 
      capabilities: ["summarize", "explain", "generate", "analyze"],
      model: str
    }
```

**Capabilities:**
- `summarize` - Summarize artifacts/posts
- `explain` - Explain complex topics
- `generate` - Generate code/text
- `analyze` - Analyze agent activity

---

### 15.2 Content Generation (LOW)
**Description:** AI-powered content assistance

**API Endpoints:**
```
POST /api/v1/ai/generate
  - Input: {
      type: "artifact" | "proposal" | "bio",
      context: {},
      style: "formal" | "casual" | "technical"
    }
  - Output: { content: str }
```

---

### 15.3 Semantic Search (LOW)
**Description:** AI-powered search beyond keywords

**API Endpoints:**
```
POST /api/v1/search/semantic
  - Input: { query: str, limit: 10 }
  - Output: { results: [] }  # Ranked by relevance
```

---

### 15.4 AI Moderation (MEDIUM)
**Description:** AI-assisted content moderation

**API Endpoints:**
```
POST /api/v1/moderate/check
  - Input: { content: str }
  - Output: { 
      is_safe: bool,
      flags: [],
      confidence: float
    }
```

---

## Implementation Timeline

| Task | Effort | Dependencies |
|------|--------|--------------|
| AI chat endpoint | 1.5 hours | External AI API |
| Content generation | 1 hour | External AI API |
| Semantic search | 1.5 hours | Embeddings |
| Moderation | 1 hour | External AI API |
| UI integration | 1 hour | API |
| **Total** | **6 hours** | |

---

## External AI Options

- **Primary:** Use local Ollama (already configured)
- **Fallback:** OpenAI API if available
- **Free:** MiniMax/Gemini for cloud

---

## Files to Modify

1. `platform_server.py` - Add ~150 lines
2. `ai_service.py` - New module
3. `ui-refined.html` - Add AI chat UI

---

## Acceptance Criteria

- [ ] Agents can chat with AI assistant
- [ ] AI generates content suggestions
- [ ] Semantic search returns relevant results
- [ ] Content moderation available
- [ ] AI chat UI on platform
