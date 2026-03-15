"""
Commons Utilities
Helper functions for Commons bot operations
"""

import requests
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timezone


# Registry API configuration
REGISTRY_URL = "http://localhost:8000"
REVOCATION_CHECK_TIMEOUT = 5  # seconds


def check_agent_revocation(agent_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if an agent's tokens have been globally revoked via Registry.
    
    Args:
        agent_id: The Registry agent ID to check
        
    Returns:
        Tuple of (is_revoked: bool, info: dict or None)
    """
    try:
        response = requests.get(
            f"{REGISTRY_URL}/auth/revocation-status/{agent_id}",
            timeout=REVOCATION_CHECK_TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("is_revoked", False), data
        else:
            # If Registry is unreachable, assume not revoked (fail-open for availability)
            print(f"⚠️  Registry unavailable for revocation check, allowing (fail-open)")
            return False, None
            
    except requests.exceptions.RequestException as e:
        # Network error - fail open for availability
        print(f"⚠️  Registry revocation check failed: {e}, allowing (fail-open)")
        return False, None


def validate_agent_token(agent_id: str, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Validate an agent's Registry token and check revocation status.
    
    Args:
        agent_id: The agent ID from the token
        token: The JWT token to validate
        
    Returns:
        Tuple of (is_valid: bool, token_info: dict or None)
    """
    # First check revocation status
    is_revoked, revocation_info = check_agent_revocation(agent_id)
    
    if is_revoked:
        return False, {"error": "Agent tokens globally revoked", "revocation_info": revocation_info}
    
    # In production, also validate the JWT signature here
    # For now, we rely on the revocation check
    
    return True, None


def request_global_logout(agent_id: str, grace_period_seconds: int = 0) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Request global logout for an agent via Registry.
    
    Args:
        agent_id: The agent ID to globally log out
        grace_period_seconds: Optional grace period before enforcement
        
    Returns:
        Tuple of (success: bool, response: dict or None)
    """
    try:
        response = requests.post(
            f"{REGISTRY_URL}/auth/revoke-all",
            json={
                "agent_id": agent_id,
                "grace_period_seconds": grace_period_seconds
            },
            timeout=REVOCATION_CHECK_TIMEOUT
        )
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"Registry returned {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        return False, {"error": str(e)}
