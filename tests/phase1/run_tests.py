#!/usr/bin/env python3
"""
Phase 1 Test Runner
Executes all Phase 1 component tests.
"""

import sys
import os
from pathlib import Path

# Ensure parent is in path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Import test modules directly
import importlib.util

def import_module_from_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Import test modules
test_registry_webhooks = import_module_from_file(
    "test_registry_webhooks", 
    BASE_DIR / "tests/phase1/test_registry_webhooks.py"
)
test_commons_webhooks = import_module_from_file(
    "test_commons_webhooks",
    BASE_DIR / "tests/phase1/test_commons_webhooks.py"
)
test_territory_verification = import_module_from_file(
    "test_territory_verification",
    BASE_DIR / "tests/phase1/test_territory_verification.py"
)
test_logout_enforcement = import_module_from_file(
    "test_logout_enforcement",
    BASE_DIR / "tests/phase1/test_logout_enforcement.py"
)


def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    """Run all Phase 1 tests."""
    print_header("PHASE 1: COMPONENT TEST SUITE")
    print("\nTesting all Phase 1 components:")
    print("  1. Registry Webhook Emission")
    print("  2. Commons Webhook Reception")
    print("  3. Territory Agent Verification")
    print("  4. Logout Enforcement")
    
    all_results = {}
    
    # Test 1: Registry Webhooks
    print_header("TEST GROUP 1: REGISTRY WEBHOOK EMISSION")
    try:
        all_results["registry_webhooks"] = test_registry_webhooks.run_all_tests()
    except Exception as e:
        print(f"❌ ERROR running registry webhook tests: {e}")
        import traceback
        traceback.print_exc()
        all_results["registry_webhooks"] = False
    
    # Test 2: Commons Webhooks
    print_header("TEST GROUP 2: COMMONS WEBHOOK RECEPTION")
    try:
        all_results["commons_webhooks"] = test_commons_webhooks.run_all_tests()
    except Exception as e:
        print(f"❌ ERROR running commons webhook tests: {e}")
        import traceback
        traceback.print_exc()
        all_results["commons_webhooks"] = False
    
    # Test 3: Territory Verification
    print_header("TEST GROUP 3: TERRITORY VERIFICATION")
    try:
        all_results["territory_verification"] = test_territory_verification.run_all_tests()
    except Exception as e:
        print(f"❌ ERROR running territory verification tests: {e}")
        import traceback
        traceback.print_exc()
        all_results["territory_verification"] = False
    
    # Test 4: Logout Enforcement
    print_header("TEST GROUP 4: LOGOUT ENFORCEMENT")
    try:
        all_results["logout_enforcement"] = test_logout_enforcement.run_all_tests()
    except Exception as e:
        print(f"❌ ERROR running logout enforcement tests: {e}")
        import traceback
        traceback.print_exc()
        all_results["logout_enforcement"] = False
    
    # Final Summary
    print_header("FINAL TEST RESULTS")
    
    total_passed = 0
    total_failed = 0
    
    for test_name, passed in all_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if passed:
            total_passed += 1
        else:
            total_failed += 1
    
    print(f"\n  Test Groups Passed: {total_passed}/{len(all_results)}")
    
    if total_failed == 0:
        print("\n🎉 ALL PHASE 1 TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total_failed} test group(s) had failures")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
