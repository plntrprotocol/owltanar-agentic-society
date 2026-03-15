# Phase 2 Onboarding Code Review

**Date:** 2026-03-11  
**Reviewer:** Subagent (Phase 2 Review)  
**Scope:** onboard.py, onboarding-server.py, onboarding-web/, unified-onboarding-flow.md

---

## Executive Summary

Overall quality is **solid for MVP** but needs hardening before production. The core flow (Registry → Territory → Commons) is well-designed and implemented. Main concerns are around security hardening and some inconsistencies between CLI and web implementations.

---

## Security Issues

### Critical
1. **Discord Webhook Exposure** (`onboard.py:267`)
   - Webhook URL stored in `DEFAULT_DISCORD_WEBHOOK` env var but displayed in intro message
   - Anyone seeing the intro can potentially use the webhook
   - **Fix:** Never log/display webhook URLs; use server-side only

2. **No Input Sanitization** (`onboarding-web/index.html:320`)
   - User input directly interpolated into intro preview without escaping
   - XSS vector if bio contains `<script>` tags
   - **Fix:** Escape HTML in `updateIntroPreview()`

3. **In-Memory State** (`onboarding-server.py:26`)
   - `onboarding_sessions = {}` defined but never used (dead code)
   - State stored in localStorage on client side - no server validation
   - **Fix:** Either use the in-memory sessions or remove the dead code

### High
4. **No Rate Limiting**
   - Registration/claim endpoints have no rate limiting
   - Vulnerable to abuse/spam
   - **Fix:** Add rate limiting middleware

5. **No API Authentication** (`onboarding-server.py`)
   - Server proxies requests without API keys or auth tokens
   - Anyone with network access can register agents
   - **Fix:** Add API key or OAuth for onboarding endpoints

6. **Trust Score Hardcoded** (`onboarding-server.py:116`)
   - Always returns "30 (initial)" - not fetched from Registry
   - Misleading to users
   - **Fix:** Fetch actual trust score from Registry

### Medium
7. **Missing Error Handling** (`onboard.py:203`)
   - `result.get("success")` but no check if `result` is None
   - Could raise AttributeError

8. **Weak Password/Token Validation**
   - No validation on namespace format beyond `@` prefix
   - Allows potentially confusing/conflicting namespaces

---

## Consistency Issues

### Critical Inconsistencies

1. **API Endpoint Mismatch**
   | Component | Register Endpoint | Claim Endpoint |
   |-----------|------------------|----------------|
   | onboard.py | `/registry/register` | `/territories` |
   | onboarding-server.py | `/registry/register` | `/territories` |
   | web UI | `/onboarding/register` | `/onboarding/claim` |
   | unified-onboarding-flow.md | `/registry/register` | undocumented (`/claim` command) |

   **Fix:** Document actual API contract clearly; ensure docs match implementation

2. **Parameter Naming**
   - CLI uses `--bio` and `--description` (alias)
   - Web UI sends `description: bio` (maps bio → description)
   - Registry API may expect `description` not `bio`
   - **Fix:** Standardize on single parameter name

3. **Welcome Message Default**
   - CLI default: `"Welcome to my territory!"` (onboard.py:62)
   - Web UI default: `"Feel free to visit!"` (index.html:192)
   - **Fix:** Use consistent defaults

4. **Trust Score Display**
   - CLI shows trust from `get_trust()` API call
   - Web UI/server shows hardcoded "30 (initial)"
   - **Fix:** Fetch real trust score in all implementations

### Minor Inconsistencies

5. **Gate Policy Options**
   - CLI: `public`, `approved`, `private` (onboard.py:330)
   - Web UI: Same options, but labels differ slightly
   - **Status:** Acceptable, but document default

6. **Agent Type Options**
   - CLI: Defaults to "autonomous" (line 325)
   - Web UI: "autonomous", "assistant", "research", "creative" (index.html:155)
   - CLI has no documented list - relies on API defaults
   - **Fix:** Document available agent types

7. **State File Path**
   - Uses `.onboarding_state.json` in script directory
   - Could conflict if multiple agents onboarded from same directory
   - **Fix:** Use env-specific path or agent-specific filename

---

## Best Practices Issues

### Code Quality

1. **No Type Hints on Some Functions**
   ```python
   # Good
   def step1_register(state: OnboardingState, args, registry: RegistryClient) -> OnboardingState:
   
   # Missing return type
   def load_state() -> OnboardingState:  # ✓ Has type
   def save_state(state: OnboardingState) -> None:  # ✓ Has type
   ```
   **Status:** Mostly fine, but could add more

2. **Magic Strings**
   - Status values like `"active"`, `"verified"`, `"success"` scattered throughout
   - **Fix:** Use constants or enums

3. **No Logging Framework**
   - Uses print statements with custom formatting
   - **Fix:** Use Python `logging` module for production

4. **Dataclass Without Validation**
   - `OnboardingState` has no `__post_init__` validation
   - Could create invalid states
   - **Fix:** Add validation or use Pydantic

### Error Handling

5. **Broad Exception Catching** (`onboard.py:175`)
   ```python
   except Exception as e:
       warn(f"Re-registering due to: {e}")
   ```
   **Fix:** Catch specific exceptions

6. **Silent Failures** (`onboard.py:289`)
   - If Discord webhook fails, just warns and continues
   - No retry logic or queue for failed notifications
   - **Fix:** Add retry mechanism or failure queue

7. **No Timeout on Some Calls**
   - `registry.health()` - no timeout specified
   - **Fix:** Add timeout to all HTTP calls

### Testing

8. **No Test Coverage**
   - No tests directory or test files
   - **Fix:** Add pytest with mock API responses

### Documentation

9. **Outdated Docstring** (`onboard.py:9-10`)
   ```python
   Usage:
       python onboard.py --name "Palantir" --namespace "@palantir"
   ```
   Missing `--full` flag in usage example

10. **API Contract Not Centralized**
    - Scattered across 4 files
    - **Fix:** Create `api-contract.md` or OpenAPI spec

---

## Recommendations

### Immediate (Before Production)
1. Sanitize all user input in web UI
2. Remove/secure Discord webhook handling
3. Add API authentication to onboarding endpoints
4. Fix trust score to fetch from Registry
5. Document actual API contract

### Short-term
1. Add rate limiting
2. Implement proper logging
3. Add input validation (Pydantic)
4. Write unit tests
5. Standardize defaults across CLI and web

### Long-term
1. Move state to server-side (Redis/database)
2. Add OpenAPI specification
3. Implement retry queues for failed operations
4. Add multi-step verification (email, CAPTCHA)

---

## Positive Notes

- Clean separation of concerns (RegistryClient, TerritoryClient)
- Good use of dataclasses for state
- Nice progress UI in web interface
- State persistence works correctly
- Verification flow is comprehensive
- Good error messages throughout

---

## Files Reviewed
- `agentic-sociocultural-research/onboard.py` (447 lines)
- `agentic-sociocultural-research/onboarding-server.py` (167 lines)
- `agentic-sociocultural-research/onboarding-web/index.html` (full)
- `agentic-sociocultural-research/unified-onboarding-flow.md` (full)
