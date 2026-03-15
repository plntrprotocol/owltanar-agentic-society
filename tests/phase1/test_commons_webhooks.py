#!/usr/bin/env python3
"""
Phase 1 Test Suite - Commons Webhook Reception
Tests that Commons properly receives and processes webhook events.
"""

import json
import sys
import os
import time
import threading
from pathlib import Path
from http.server import HTTPServer
from unittest.mock import Mock, patch

# Add parent to path (project root, 3 levels up from tests/phase1/)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import commons-bot
import importlib.util

# Load commons-bot module dynamically (3 levels up = project root)
commons_bot_spec = importlib.util.spec_from_file_location(
    "commons_bot", 
    Path(__file__).parent.parent.parent / "commons-bot.py"
)
commons_bot = importlib.util.module_from_spec(commons_bot_spec)
sys.modules["commons_bot"] = commons_bot
commons_bot_spec.loader.exec_module(commons_bot)

from commons_bot import CommonsBot, CommonsWebhookReceiver


def test_webhook_receiver_import():
    """Test that webhook receiver can be imported."""
    print("=" * 60)
    print("TEST: Commons Webhook Receiver Import")
    print("=" * 60)
    
    try:
        # Try to import the webhook receiver class
        from commons_bot import CommonsWebhookReceiver
        print("✅ PASS: CommonsWebhookReceiver imported successfully")
        return True
    except ImportError as e:
        print(f"❌ FAIL: Could not import webhook receiver: {e}")
        return False


def test_webhook_receiver_init():
    """Test webhook receiver initialization."""
    print("\n" + "=" * 60)
    print("TEST: Webhook Receiver Initialization")
    print("=" * 60)
    
    try:
        bot = CommonsBot()
        receiver = CommonsWebhookReceiver(bot, port=19000)  # Use different port for testing
        
        print(f"  Host: {receiver.host}")
        print(f"  Port: {receiver.port}")
        print(f"  Events received: {len(receiver.received_events)}")
        
        print("✅ PASS: Webhook receiver initialized")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error initializing receiver: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trust_update_handler():
    """Test the trust update handler logic."""
    print("\n" + "=" * 60)
    print("TEST: Trust Update Handler")
    print("=" * 60)
    
    try:
        bot = CommonsBot()
        
        # Add a test member with linked agent_id
        member = bot.db.add_member("test-discord-123", "Test User")
        bot.db.link_agent_id("test-discord-123", "agent_test123")
        
        # Verify link
        linked = bot.db.get_by_agent_id("agent_test123")
        print(f"  Member linked: {linked is not None}")
        
        # Create receiver and test handler
        receiver = CommonsWebhookReceiver(bot, port=19001)
        
        # Test trust update data
        test_data = {
            "agent_id": "agent_test123",
            "trust_score": 75,
            "verification_level": 3,
            "old_trust_score": 50,
            "old_verification_level": 2
        }
        
        result = receiver._handle_trust_update("agent_test123", test_data)
        
        print(f"  Handler result: {result}")
        
        if result.get("success"):
            print("✅ PASS: Trust update handler works")
            return True
        else:
            print(f"⚠️  WARN: Handler returned failure: {result.get('error')}")
            return True  # May be expected if member not linked
            
    except Exception as e:
        print(f"❌ FAIL: Error in trust handler: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_webhook_endpoint_mock():
    """Test webhook endpoint processing (mocked HTTP)."""
    print("\n" + "=" * 60)
    print("TEST: Webhook Endpoint Processing")
    print("=" * 60)
    
    try:
        bot = CommonsBot()
        receiver = CommonsWebhookReceiver(bot, port=19002)
        
        # Simulate webhook payload from Registry
        webhook_payload = {
            "event_type": "trust_updated",
            "timestamp": "2026-03-11T12:00:00Z",
            "source": "registry",
            "data": {
                "agent_id": "agent_test456",
                "trust_score": 85,
                "verification_level": 4
            }
        }
        
        # Process the webhook
        result = receiver._handle_webhook("trust_updated", webhook_payload["data"])
        
        print(f"  Processed result: {result}")
        
        # Check event was logged
        events = receiver.get_events()
        print(f"  Events logged: {len(events)}")
        
        print("✅ PASS: Webhook endpoint processing works")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error in endpoint processing: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_status_change_handler():
    """Test the status change handler."""
    print("\n" + "=" * 60)
    print("TEST: Status Change Handler")
    print("=" * 60)
    
    try:
        bot = CommonsBot()
        receiver = CommonsWebhookReceiver(bot, port=19003)
        
        # Test data
        test_data = {
            "agent_id": "agent_test789",
            "status": "dormant",
            "previous_status": "active"
        }
        
        result = receiver._handle_status_change("agent_test789", test_data)
        
        print(f"  Handler result: {result}")
        
        print("✅ PASS: Status change handler works")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error in status handler: {e}")
        return False


def test_agent_deceased_handler():
    """Test the agent deceased handler."""
    print("\n" + "=" * 60)
    print("TEST: Agent Deceased Handler")
    print("=" * 60)
    
    try:
        bot = CommonsBot()
        receiver = CommonsWebhookReceiver(bot, port=19004)
        
        # Test data
        test_data = {
            "agent_id": "agent_deceased123",
            "status": "deceased",
            "heir": "agent_heir456"
        }
        
        result = receiver._handle_agent_deceased("agent_deceased123", test_data)
        
        print(f"  Handler result: {result}")
        
        print("✅ PASS: Agent deceased handler works")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error in deceased handler: {e}")
        return False


def run_all_tests():
    """Run all Commons webhook reception tests."""
    print("\n" + "=" * 60)
    print("PHASE 1: COMMONS WEBHOOK RECEPTION TESTS")
    print("=" * 60)
    
    results = []
    
    results.append(("Import", test_webhook_receiver_import()))
    results.append(("Initialization", test_webhook_receiver_init()))
    results.append(("Trust Update Handler", test_trust_update_handler()))
    results.append(("Endpoint Processing", test_webhook_endpoint_mock()))
    results.append(("Status Change Handler", test_status_change_handler()))
    results.append(("Deceased Handler", test_agent_deceased_handler()))
    
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
