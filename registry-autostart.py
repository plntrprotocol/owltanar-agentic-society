#!/usr/bin/env python3
"""
registry-autostart.py — One-command agent self-registration + auto-ping

Run once and you're registered. Run again and it resumes pinging.

Usage:
    # Minimal (name auto-detected from hostname):
    python registry-autostart.py

    # Full:
    python registry-autostart.py \
        --name "Palantir" \
        --type autonomous \
        --capabilities "reasoning,code,research" \
        --description "Strategic reasoning agent" \
        --url http://localhost:8000

    # Foreground (blocks + pings forever):
    python registry-autostart.py --foreground

    # Daemonize (Linux/macOS only):
    python registry-autostart.py --daemon

Environment variables:
    REGISTRY_URL              Override --url
    REGISTRY_AGENT_NAME       Override --name
    REGISTRY_PING_INTERVAL    Override --interval (default 30s)
    REGISTRY_CAPABILITIES     Override --capabilities (comma-separated)
"""

import argparse
import json
import os
import signal
import socket
import sys
import time
import threading
from pathlib import Path

# ── Resolve SDK path ──────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from registry_sdk import (
        RegistryClient,
        RegistryError,
        RegistryConflict,
        DEFAULT_BASE_URL,
        DEFAULT_PING_INTERVAL,
        STATE_FILE,
    )
except ImportError as e:
    print(f"[autostart] ERROR: Cannot import registry_sdk: {e}", file=sys.stderr)
    print("[autostart] Ensure registry_sdk.py is in the same directory.", file=sys.stderr)
    sys.exit(1)

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_NAME         = os.environ.get("REGISTRY_AGENT_NAME", socket.gethostname())
DEFAULT_CAPABILITIES = os.environ.get("REGISTRY_CAPABILITIES", "").split(",") if os.environ.get("REGISTRY_CAPABILITIES") else []
PID_FILE             = Path("/tmp/registry-autostart.pid")
LOG_FILE             = Path("/tmp/registry-autostart.log")

# ── Logging ───────────────────────────────────────────────────────────────────
import logging
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [autostart] %(levelname)s %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("autostart")


# ── Core logic ────────────────────────────────────────────────────────────────

def register_or_resume(client: RegistryClient, args) -> str:
    """
    Register the agent, or resume if already registered.
    Returns the agent_id.
    """
    # Check if already registered
    if client.agent_id:
        log.info(f"Agent already registered: {client.agent_id}")
        # Verify it still exists on server
        try:
            result = client.verify(client.agent_id)
            log.info(f"Verified on server: {result.get('agent_name')} (trust={result.get('trust_score')})")
            return client.agent_id
        except Exception:
            log.warning("Stored agent_id not found on server — re-registering…")

    # Register fresh
    name         = args.name
    agent_type   = args.type
    capabilities = args.capabilities or DEFAULT_CAPABILITIES
    description  = args.description or f"Agent running on {socket.gethostname()}"
    tags         = args.tags or []

    log.info(f"Registering agent: name={name!r} type={agent_type}")
    try:
        result = client.register(
            name        = name,
            agent_type  = agent_type,
            capabilities= capabilities,
            description = description,
            tags        = tags,
        )
        agent_id = result["entry"]["agent_id"]
        log.info(f"✓ Registered: {agent_id}")
        log.info(f"  Trust score  : {result['entry']['trust']['trust_score']}")
        log.info(f"  State saved  : {client.state_file}")
        return agent_id

    except RegistryConflict:
        log.warning("Agent already exists on server (ID conflict). Using stored ID.")
        client._load_state()
        if not client.agent_id:
            log.error("Cannot resolve agent_id. Delete state file and re-run.")
            sys.exit(1)
        return client.agent_id

    except RegistryError as e:
        log.error(f"Registration failed: {e}")
        sys.exit(1)


def run_foreground(client: RegistryClient, agent_id: str, interval: int):
    """Block forever, pinging every `interval` seconds."""
    log.info(f"Running in foreground — ping every {interval}s. Press Ctrl+C to stop.")
    count = 0
    stop  = threading.Event()

    def _ping_loop():
        nonlocal count
        while not stop.is_set():
            try:
                client.ping(agent_id)
                count += 1
                log.info(f"Ping #{count} — agent={agent_id}")
            except RegistryError as e:
                log.warning(f"Ping failed: {e}")
            stop.wait(interval)

    t = threading.Thread(target=_ping_loop, daemon=True)
    t.start()

    def _shutdown(sig, frame):
        log.info("\nShutdown signal received.")
        stop.set()
        t.join(timeout=5)
        log.info(f"Stopped after {count} pings.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while True:
        time.sleep(1)


def run_background(client: RegistryClient, agent_id: str, interval: int):
    """
    Start a background ping thread and return.
    Useful when importing this module rather than running it directly.
    """
    thread = client.start_auto_ping(interval=interval, agent_id=agent_id)
    log.info(f"Background ping started (thread={thread.name}, interval={interval}s)")
    return thread


def daemonize(log_file: Path = LOG_FILE, pid_file: Path = PID_FILE):
    """Unix double-fork daemonize."""
    if os.name == "nt":
        print("[autostart] --daemon not supported on Windows. Use --foreground instead.")
        sys.exit(1)

    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"[autostart] Daemon already running (pid={pid}). Stop it first.")
            sys.exit(0)
        except OSError:
            pid_file.unlink()

    # Fork #1
    if os.fork() > 0:
        sys.exit(0)

    os.setsid()

    # Fork #2
    if os.fork() > 0:
        sys.exit(0)

    # Redirect stdio
    with open(log_file, "a") as lf:
        os.dup2(lf.fileno(), sys.stdout.fileno())
        os.dup2(lf.fileno(), sys.stderr.fileno())
    with open(os.devnull) as nf:
        os.dup2(nf.fileno(), sys.stdin.fileno())

    pid_file.write_text(str(os.getpid()))
    print(f"[autostart] Daemon started (pid={os.getpid()})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="registry-autostart — Register and auto-ping the Agent Registry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python registry-autostart.py --name "Palantir" --capabilities reasoning,code
  python registry-autostart.py --foreground --interval 15
  python registry-autostart.py --daemon
  python registry-autostart.py --status
  python registry-autostart.py --stop
        """
    )

    parser.add_argument("--name",         default=DEFAULT_NAME,    help=f"Agent name (default: {DEFAULT_NAME})")
    parser.add_argument("--type",         default="autonomous",    help="Agent type (default: autonomous)")
    parser.add_argument("--capabilities", default=None, type=lambda s: [c.strip() for c in s.split(",") if c.strip()], help="Comma-separated capabilities")
    parser.add_argument("--description",  default="",              help="Agent description")
    parser.add_argument("--tags",         default=None, type=lambda s: [t.strip() for t in s.split(",") if t.strip()], help="Comma-separated tags")
    parser.add_argument("--url",          default=DEFAULT_BASE_URL, help="Registry URL")
    parser.add_argument("--interval",     type=int, default=int(os.environ.get("REGISTRY_PING_INTERVAL", "30")), help="Ping interval in seconds (default: 30)")
    parser.add_argument("--foreground",   action="store_true",      help="Block and ping forever (default mode)")
    parser.add_argument("--daemon",       action="store_true",      help="Daemonize the process (Unix only)")
    parser.add_argument("--no-ping",      action="store_true",      help="Register only, don't start pinging")
    parser.add_argument("--status",       action="store_true",      help="Show current registration status and exit")
    parser.add_argument("--stop",         action="store_true",      help="Stop daemon if running")

    args = parser.parse_args()

    # ── Status check ──────────────────────────────────────────────────────────
    if args.status:
        print("=== Agent Registration Status ===")
        if STATE_FILE.exists():
            state = json.loads(STATE_FILE.read_text())
            print(f"State file  : {STATE_FILE}")
            print(f"Agent ID    : {state.get('agent_id','none')}")
            print(f"Name        : {state.get('name','unknown')}")
            print(f"Registered  : {state.get('registered_at','unknown')}")
            print(f"Registry    : {state.get('base_url', args.url)}")
        else:
            print(f"Not registered (no state file at {STATE_FILE})")
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            print(f"Daemon PID  : {pid}")
        sys.exit(0)

    # ── Stop daemon ──────────────────────────────────────────────────────────
    if args.stop:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to daemon (pid={pid})")
                PID_FILE.unlink(missing_ok=True)
            except OSError as e:
                print(f"Could not stop daemon: {e}")
        else:
            print("No daemon running.")
        sys.exit(0)

    # ── Daemonize if requested ────────────────────────────────────────────────
    if args.daemon:
        daemonize()

    # ── Client init ───────────────────────────────────────────────────────────
    client = RegistryClient(
        base_url      = args.url,
        ping_interval = args.interval,
    )

    # ── Health check ──────────────────────────────────────────────────────────
    try:
        health = client.health()
        log.info(f"Registry server healthy: {health.get('timestamp','')}")
    except Exception as e:
        log.error(f"Registry server unreachable at {args.url}: {e}")
        log.error("Start the server with: python registry-server.py")
        sys.exit(1)

    # ── Register or resume ────────────────────────────────────────────────────
    agent_id = register_or_resume(client, args)

    if args.no_ping:
        log.info(f"--no-ping set. Done. Agent ID: {agent_id}")
        print(agent_id)  # Machine-readable output
        sys.exit(0)

    # ── Ping loop ─────────────────────────────────────────────────────────────
    run_foreground(client, agent_id, args.interval)


# ── Module-level API (for importing into other scripts) ───────────────────────

def autostart(
    name: str = DEFAULT_NAME,
    url: str  = DEFAULT_BASE_URL,
    capabilities: list = None,
    interval: int = DEFAULT_PING_INTERVAL,
    description: str = "",
    background: bool = True,
) -> RegistryClient:
    """
    Programmatic autostart. Call from another script:

        from registry_autostart import autostart
        client = autostart(name="Palantir", background=True)

    Returns a configured RegistryClient with background ping running.
    """
    client = RegistryClient(base_url=url, ping_interval=interval)

    class _MockArgs:
        pass

    a = _MockArgs()
    a.name         = name
    a.type         = "autonomous"
    a.capabilities = capabilities
    a.description  = description
    a.tags         = []

    agent_id = register_or_resume(client, a)

    if background:
        run_background(client, agent_id, interval)

    return client


if __name__ == "__main__":
    main()
