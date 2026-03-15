#!/usr/bin/env python3
"""
Phase 2: Onboarding Integration Tests
Tests the unified onboarding flow: Registry → Territory → Commons
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_onboard_script_import():
    """Test that onboard.py can be imported"""
    try:
        import onboard
        print("✓ onboard.py imports OK")
        return True
    except Exception as e:
        print(f"✗ onboard.py import failed: {e}")
        return False

def test_onboarding_server_exists():
    """Test that onboarding-server.py exists"""
    if os.path.exists("onboarding-server.py"):
        print("✓ onboarding-server.py exists")
        return True
    else:
        print("✗ onboarding-server.py not found")
        return False

def test_registry_sdk_import():
    """Test that registry_sdk.py works"""
    try:
        from registry_sdk import RegistryClient
        print("✓ registry_sdk.py imports OK")
        return True
    except Exception as e:
        print(f"✗ registry_sdk.py import failed: {e}")
        return False

def test_onboarding_flow_steps():
    """Test that onboarding flow steps are defined"""
    try:
        with open("onboard.py", "r") as f:
            content = f.read()
            steps = ["register", "claim", "commons", "verify"]
            found = sum(1 for s in steps if s.lower() in content.lower())
            if found >= 3:
                print(f"✓ Onboarding flow has {found}/4 key steps")
                return True
            else:
                print(f"✗ Onboarding flow missing steps (found {found}/4)")
                return False
    except Exception as e:
        print(f"✗ Flow check failed: {e}")
        return False

def test_api_endpoints():
    """Test that onboarding API endpoints are defined"""
    try:
        with open("onboarding-server.py", "r") as f:
            content = f.read()
            endpoints = ["/onboarding/start", "/onboarding/status", "/onboarding/complete"]
            found = sum(1 for e in endpoints if e in content)
            if found >= 2:
                print(f"✓ Onboarding API has {found}/3 endpoints")
                return True
            else:
                print(f"✗ Onboarding API missing endpoints (found {found}/3)")
                return False
    except Exception as e:
        print(f"✗ API check failed: {e}")
        return False

def main():
    print("=" * 60)
    print("PHASE 2: ONBOARDING INTEGRATION TESTS")
    print("=" * 60)
    
    results = []
    
    print("\n1. Testing onboard.py import...")
    results.append(test_onboard_script_import())
    
    print("\n2. Testing onboarding-server.py...")
    results.append(test_onboarding_server_exists())
    
    print("\n3. Testing registry_sdk.py...")
    results.append(test_registry_sdk_import())
    
    print("\n4. Testing onboarding flow steps...")
    results.append(test_onboarding_flow_steps())
    
    print("\n5. Testing API endpoints...")
    results.append(test_api_endpoints())
    
    print("\n" + "=" * 60)
    print(f"SUMMARY: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    return all(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
