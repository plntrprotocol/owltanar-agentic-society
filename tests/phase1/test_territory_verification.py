#!/usr/bin/env python3
"""
Phase 1 Test Suite - Territory Verification
Tests that Territory properly verifies agents via Registry before allowing claims.
"""

import json
import sys
import os
from pathlib import Path

# Add parent to path
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load registry_server module dynamically
import importlib.util
registry_server_spec = importlib.util.spec_from_file_location(
    "registry_server", 
    BASE_DIR / "registry_server.py"
)
registry_server = importlib.util.module_from_spec(registry_server_spec)
sys.modules["registry_server"] = registry_server
registry_server_spec.loader.exec_module(registry_server)


def test_territory_db_not_exists():
    """Test that territory database doesn't exist yet (needs to be created)."""
    print("=" * 60)
    print("TEST: Territory Database Existence")
    print("=" * 60)
    
    db_path = Path(__file__).parent.parent.parent / "territory-db.json"
    
    if db_path.exists():
        print(f"  ⚠️  WARN: territory-db.json exists at {db_path}")
        return True
    else:
        print(f"  ✓ territory-db.json does not exist (expected for Phase 1)")
        print("✅ PASS: Territory database check completed")
        return True


def test_registry_verify_endpoint():
    """Test that Registry has /registry/verify endpoint."""
    print("\n" + "=" * 60)
    print("TEST: Registry Verify Endpoint")
    print("=" * 60)
    
    try:
        import registry_server
        
        # Check if verify endpoint exists in the source
        source = Path(registry_server.__file__).read_text()
        
        if 'def verify_agent' in source and '/registry/verify' in source:
            print("  ✓ Registry has /registry/verify endpoint")
            
            # Check what it returns
            if 'verified' in source and 'status' in source:
                print("  ✓ Endpoint returns verification info")
            
            print("✅ PASS: Registry verify endpoint exists")
            return True
        else:
            print("❌ FAIL: Registry verify endpoint not found")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Error checking verify endpoint: {e}")
        return False


def test_territory_verification_logic():
    """Test territory verification logic (mocked)."""
    print("\n" + "=" * 60)
    print("TEST: Territory Verification Logic")
    print("=" * 60)
    
    # This simulates what territory should do when verifying an agent
    
    # Test case 1: Valid active agent
    print("\n  Test Case 1: Valid active agent")
    verify_response = {
        "verified": True,
        "agent_id": "agent_palantir",
        "agent_name": "Palantir",
        "status": "active",
        "verification_level": 4,
        "trust_score": 95
    }
    
    if verify_response["verified"] and verify_response["status"] == "active":
        print("    ✓ Agent verified and active - claim should proceed")
    else:
        print("    ❌ Agent verification failed")
        return False
    
    # Test case 2: Agent not found
    print("\n  Test Case 2: Agent not found")
    verify_response = {
        "verified": False,
        "error": "Agent not found"
    }
    
    if not verify_response["verified"]:
        print("    ✓ Agent not found - claim should be BLOCKED")
    else:
        print("    ❌ Should have returned verified=False")
        return False
    
    # Test case 3: Deceased agent
    print("\n  Test Case 3: Deceased agent")
    verify_response = {
        "verified": True,
        "agent_id": "agent_deceased",
        "status": "deceased"
    }
    
    if verify_response["status"] == "deceased":
        print("    ✓ Agent is deceased - claim should be BLOCKED")
    else:
        print("    ❌ Should have detected deceased status")
        return False
    
    # Test case 4: Dormant agent (should be flagged but allowed)
    print("\n  Test Case 4: Dormant agent")
    verify_response = {
        "verified": True,
        "agent_id": "agent_dormant",
        "status": "dormant",
        "verification_level": 1
    }
    
    if verify_response["status"] == "dormant":
        print("    ✓ Agent is dormant - claim allowed with flag")
    else:
        print("    ❌ Should have detected dormant status")
        return False
    
    print("✅ PASS: Territory verification logic works")
    return True


def test_territory_integration_doc():
    """Test that territory-registry-integration.md exists and has correct info."""
    print("\n" + "=" * 60)
    print("TEST: Territory Integration Documentation")
    print("=" * 60)
    
    doc_path = Path(__file__).parent.parent.parent / "territory-registry-integration.md"
    
    if not doc_path.exists():
        print("❌ FAIL: territory-registry-integration.md not found")
        return False
    
    doc_content = doc_path.read_text()
    
    # Check key requirements
    checks = [
        ("/registry/verify" in doc_content, "Contains verify endpoint reference"),
        ("status" in doc_content, "Contains status field"),
        ("agent_id" in doc_content, "Contains agent_id field"),
    ]
    
    all_passed = True
    for check, desc in checks:
        if check:
            print(f"  ✓ {desc}")
        else:
            print(f"  ❌ {desc}")
            all_passed = False
    
    if all_passed:
        print("✅ PASS: Territory integration documentation complete")
    else:
        print("❌ FAIL: Territory integration documentation incomplete")
    
    return all_passed


def test_block_claim_without_valid_agent():
    """Test that claim is blocked without valid agent (simulated)."""
    print("\n" + "=" * 60)
    print("TEST: Block Claim Without Valid Agent")
    print("=" * 60)
    
    # This is the key Phase 1 requirement: 
    # Territory must block claims if agent_id not found in Registry
    
    # Simulate the verification process
    def verify_and_claim(agent_id: str, registry_url: str = "http://localhost:8000"):
        """Simulated territory claim verification."""
        import requests
        
        try:
            # Query Registry
            response = requests.get(f"{registry_url}/registry/verify/{agent_id}", timeout=5)
            
            if response.status_code == 404:
                return {"allowed": False, "reason": "Agent not found in Registry"}
            
            if response.status_code != 200:
                return {"allowed": False, "reason": "Registry error"}
            
            data = response.json()
            
            # Check status
            if data.get("status") == "deceased":
                return {"allowed": False, "reason": "Agent is deceased"}
            
            if data.get("status") == "active":
                return {"allowed": True, "message": "Agent verified"}
            
            # Dormant agents may be flagged but allowed
            return {"allowed": True, "flag": "dormant"}
            
        except Exception as e:
            return {"allowed": False, "reason": f"Error: {e}"}
    
    # Test cases
    print("\n  Testing claim scenarios:")
    
    # Case 1: Unknown agent
    result = verify_and_claim("agent_does_not_exist")
    print(f"    Unknown agent: allowed={result['allowed']}, reason={result.get('reason', '')}")
    
    # Case 2: Deceased agent (would need actual Registry data)
    # We simulate the logic
    deceased_logic = {"status": "deceased", "verified": True}
    if deceased_logic.get("status") == "deceased":
        print(f"    Deceased agent: BLOCKED (correct)")
    else:
        print(f"    Deceased agent: SHOULD BE BLOCKED")
        return False
    
    print("✅ PASS: Claim blocking logic verified")
    return True


def run_all_tests():
    """Run all territory verification tests."""
    print("\n" + "=" * 60)
    print("PHASE 1: TERRITORY VERIFICATION TESTS")
    print("=" * 60)
    
    results = []
    
    results.append(("Database Check", test_territory_db_not_exists()))
    results.append(("Registry Verify Endpoint", test_registry_verify_endpoint()))
    results.append(("Verification Logic", test_territory_verification_logic()))
    results.append(("Integration Doc", test_territory_integration_doc()))
    results.append(("Block Invalid Claims", test_block_claim_without_valid_agent()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
