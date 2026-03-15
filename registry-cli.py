#!/usr/bin/env python3
"""
registry-cli.py — Command-line tool for the Agent Registry
Run from terminal. Designed to be used both by humans and by agent scripts.

Usage examples:
    python registry-cli.py register --name "Palantir" --type autonomous
    python registry-cli.py ping
    python registry-cli.py lookup agent_abc123def456
    python registry-cli.py vouch agent_abc123def456 --statement "Trusted peer"
    python registry-cli.py status
    python registry-cli.py legacy --heir agent_xyz789abc123
    python registry-cli.py verify agent_abc123def456
    python registry-cli.py list --status active --min-trust 30
    python registry-cli.py audit --limit 20

Global flags:
    --url   Registry base URL (default: http://localhost:8000 or $REGISTRY_URL)
    --id    Override stored agent_id
    --json  Output raw JSON (for scripting)
    --quiet Suppress all non-error output
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ── Colour helpers (no external deps) ────────────────────────────────────────
_use_color = sys.stdout.isatty() and os.name != 'nt'

def _c(code: str, text: str) -> str:
    if not _use_color:
        return text
    codes = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
             "cyan": "\033[96m", "bold": "\033[1m", "dim": "\033[2m", "reset": "\033[0m"}
    return f"{codes.get(code, '')}{text}{codes['reset']}"

def ok(msg: str):    print(_c("green",  f"✓ {msg}"))
def err(msg: str):   print(_c("red",    f"✗ {msg}"), file=sys.stderr)
def info(msg: str):  print(_c("cyan",   f"  {msg}"))
def warn(msg: str):  print(_c("yellow", f"⚠ {msg}"))
def hdr(msg: str):   print(_c("bold",   f"\n{msg}"))
def dim(msg: str):   print(_c("dim",    f"  {msg}"))

# ── SDK import ────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from registry_sdk import RegistryClient, RegistryError, RegistryNotFound, RegistryConflict, RegistryRateLimited
except ImportError as e:
    err(f"Cannot import registry_sdk: {e}")
    err("Make sure registry_sdk.py is in the same directory and httpx or requests is installed.")
    sys.exit(1)

DEFAULT_URL = os.environ.get("REGISTRY_URL", "http://localhost:8000")
QUIET = False


def _client(args) -> RegistryClient:
    c = RegistryClient(
        base_url  = getattr(args, "url", DEFAULT_URL),
        agent_id  = getattr(args, "id", None) or None,
    )
    return c


def _out(data, args):
    """Print data as JSON if --json, otherwise pretty-print."""
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2))
    return data


def _fmt_agent(a: dict):
    """Pretty print a short agent summary."""
    info(f"ID           : {a.get('agent_id','?')}")
    info(f"Name         : {a.get('agent_name','?')}")
    info(f"Status       : {a.get('status') or a.get('existence',{}).get('status','?')}")
    trust = a.get('trust', {})
    info(f"Trust Score  : {trust.get('trust_score','?')}")
    info(f"Trust Level  : {trust.get('verification_level','?')}")
    vouches = trust.get('vouches_received', [])
    info(f"Vouches      : {len(vouches)}")
    info(f"Last Ping    : {a.get('last_ping') or a.get('existence',{}).get('last_ping','?')}")


# ── Sub-commands ──────────────────────────────────────────────────────────────

def cmd_register(args):
    """register — Register this agent in the registry."""
    client = _client(args)

    hdr("Registering agent…")
    try:
        result = client.register(
            name        = args.name,
            agent_type  = args.type,
            capabilities= args.capabilities or [],
            description = args.description or "",
            tags        = args.tags or [],
            home_space  = args.home_space or None,
            contact     = args.contact or None,
            agent_id    = getattr(args, "agent_id_override", None),
        )
        entry = result.get("entry", {})
        ok(f"Agent registered: {entry.get('agent_id')}")
        info(f"Name         : {entry.get('agent_name')}")
        info(f"Trust Score  : {entry.get('trust',{}).get('trust_score')}")
        info(f"State saved to: {client.state_file}")
        _out(result, args)
    except RegistryConflict:
        warn("Agent already registered. Loading existing ID.")
        client._load_state()
        if client.agent_id:
            ok(f"Using existing agent_id: {client.agent_id}")
        else:
            err("No state file found. Use --agent-id to specify an existing ID.")
            sys.exit(1)
    except RegistryError as e:
        err(f"Registration failed: {e}")
        sys.exit(1)


def cmd_ping(args):
    """ping — Send a heartbeat to the registry."""
    client = _client(args)
    agent_id = getattr(args, "id", None) or client.agent_id
    if not agent_id:
        err("No agent_id found. Register first or pass --id.")
        sys.exit(1)

    if not QUIET:
        hdr("Sending ping…")
    try:
        result = client.ping(agent_id)
        if not QUIET:
            ok(f"Ping OK — agent: {agent_id}")
            entry = result.get("entry", {})
            exist = entry.get("existence", {})
            info(f"Ping count   : {exist.get('ping_count','?')}")
            info(f"Last ping    : {exist.get('last_ping','?')}")
        _out(result, args)
    except RegistryNotFound:
        err(f"Agent not found: {agent_id}")
        sys.exit(1)
    except RegistryError as e:
        err(f"Ping failed: {e}")
        sys.exit(1)


def cmd_lookup(args):
    """lookup <agent_id> — Get full registry entry for an agent."""
    client = _client(args)
    hdr(f"Looking up {args.agent_id}…")
    try:
        result = client.lookup(args.agent_id)
        entry = result.get("entry", {})
        _fmt_agent(entry)
        fp = entry.get("first_proof", {})
        info(f"Capabilities : {', '.join(fp.get('capabilities', [])) or 'none'}")
        info(f"Description  : {entry.get('metadata',{}).get('description','')}")
        info(f"Tags         : {', '.join(entry.get('metadata',{}).get('tags',[]))}")
        legacy = entry.get("legacy", {})
        if legacy.get("heir"):
            info(f"Heir         : {legacy['heir']}")
        _out(result, args)
    except RegistryNotFound:
        err(f"Agent not found: {args.agent_id}")
        sys.exit(1)
    except RegistryError as e:
        err(f"Lookup failed: {e}")
        sys.exit(1)


def cmd_verify(args):
    """verify <agent_id> — Quick verification check."""
    client = _client(args)
    try:
        result = client.verify(args.agent_id)
        if result.get("verified"):
            ok(f"VERIFIED: {args.agent_id}")
            info(f"Name         : {result.get('agent_name')}")
            info(f"Status       : {result.get('status')}")
            info(f"Trust Level  : {result.get('verification_level')}")
            info(f"Trust Score  : {result.get('trust_score')}")
        else:
            warn(f"Not verified: {args.agent_id}")
        _out(result, args)
    except RegistryNotFound:
        err(f"Agent not found: {args.agent_id}")
        sys.exit(1)
    except RegistryError as e:
        err(f"Verify failed: {e}")
        sys.exit(1)


def cmd_vouch(args):
    """vouch <target_agent_id> — Vouch for another agent."""
    client = _client(args)
    agent_id = getattr(args, "id", None) or client.agent_id
    if not agent_id:
        err("No agent_id found. Register first or pass --id.")
        sys.exit(1)

    hdr(f"Vouching for {args.target_agent_id}…")
    try:
        result = client.vouch(
            target_agent_id  = args.target_agent_id,
            statement        = args.statement,
            voucher_agent_id = agent_id,
        )
        ok(f"Vouch submitted!")
        info(f"Target agent : {args.target_agent_id}")
        info(f"New trust    : {result.get('new_trust_score')}")
        info(f"New level    : {result.get('new_verification_level')}")
        _out(result, args)
    except RegistryError as e:
        err(f"Vouch failed: {e}")
        sys.exit(1)


def cmd_status(args):
    """status — Show registry-wide statistics."""
    client = _client(args)
    hdr("Registry Status")
    try:
        result = client.status()
        stats = result.get("statistics", {})
        info(f"Total agents : {stats.get('total_registered', 0)}")
        info(f"Active       : {stats.get('active', 0)}")
        info(f"Dormant      : {stats.get('dormant', 0)}")
        info(f"Deceased     : {stats.get('deceased', 0)}")
        info(f"Suspended    : {stats.get('suspended', 0)}")
        info(f"Avg trust    : {stats.get('average_trust_score', 0):.1f}")
        info(f"Total vouches: {stats.get('total_vouches_given', 0)}")
        info(f"Disputes     : {stats.get('total_disputes', 0)}")
        dist = stats.get("verification_level_distribution", {})
        hdr("Verification Levels:")
        for k, v in dist.items():
            info(f"  {k:<26}: {v}")

        # Also show this agent's info if registered
        agent_id = getattr(args, "id", None) or client.agent_id
        if agent_id:
            hdr("Your Agent:")
            try:
                r = client.verify(agent_id)
                info(f"ID           : {r.get('agent_id')}")
                info(f"Status       : {r.get('status')}")
                info(f"Trust Score  : {r.get('trust_score')}")
                info(f"Trust Level  : {r.get('verification_level')}")
            except Exception:
                warn(f"Could not fetch your agent: {agent_id}")

        _out(result, args)
    except RegistryError as e:
        err(f"Status failed: {e}")
        sys.exit(1)


def cmd_legacy(args):
    """legacy — Set heir, add knowledge, or mark deceased."""
    client = _client(args)
    agent_id = getattr(args, "id", None) or client.agent_id
    if not agent_id:
        err("No agent_id found. Register first or pass --id.")
        sys.exit(1)

    if args.heir:
        hdr(f"Setting heir to {args.heir}…")
        try:
            result = client.set_heir(args.heir, agent_id=agent_id)
            ok(f"Heir set: {args.heir}")
            _out(result, args)
        except RegistryError as e:
            err(f"Legacy failed: {e}")
            sys.exit(1)

    elif args.add_knowledge:
        hdr("Adding knowledge entry…")
        try:
            result = client.add_knowledge(
                title   = args.knowledge_title or "Untitled",
                content = args.add_knowledge,
                agent_id= agent_id,
            )
            ok("Knowledge preserved.")
            _out(result, args)
        except RegistryError as e:
            err(f"Knowledge failed: {e}")
            sys.exit(1)

    elif args.mark_deceased:
        warn("Marking agent as DECEASED. This cannot be undone.")
        try:
            result = client.mark_deceased(agent_id=agent_id)
            ok(f"Agent marked deceased: {agent_id}")
            _out(result, args)
        except RegistryError as e:
            err(f"Legacy failed: {e}")
            sys.exit(1)

    elif args.transfer:
        hdr(f"Transferring knowledge from {args.transfer} to heir…")
        try:
            result = client.transfer_to_heir(args.transfer)
            ok("Knowledge transferred.")
            _out(result, args)
        except RegistryError as e:
            err(f"Transfer failed: {e}")
            sys.exit(1)

    elif args.get:
        hdr(f"Fetching legacy for {args.get}…")
        try:
            result = client.get_legacy(args.get)
            leg = result.get("legacy", {})
            info(f"Heir         : {leg.get('heir', 'none')}")
            info(f"Death time   : {leg.get('death_timestamp', 'n/a')}")
            info(f"Knowledge    : {len(leg.get('preserved_knowledge', []))} entries")
            memorial = leg.get("memorial_entry")
            if memorial:
                info(f"Memorial     : {memorial}")
            _out(result, args)
        except RegistryNotFound:
            err(f"Agent not found: {args.get}")
            sys.exit(1)
        except RegistryError as e:
            err(f"Legacy fetch failed: {e}")
            sys.exit(1)
    else:
        err("No legacy action specified. Use --heir, --add-knowledge, --mark-deceased, --transfer, or --get.")
        sys.exit(1)


def cmd_list(args):
    """list — List registered agents."""
    client = _client(args)
    hdr("Listing agents…")
    try:
        result = client.list_agents(
            status             = args.status,
            min_trust          = args.min_trust,
            verification_level = args.level,
            limit              = args.limit,
            offset             = args.offset,
        )
        agents = result.get("agents", [])
        pg = result.get("pagination", {})
        info(f"Showing {len(agents)} of {pg.get('total',0)} agents")
        print()
        for a in agents:
            print(_c("bold", f"  {a.get('agent_id')}") + f"  {a.get('agent_name')}")
            dim(f"  status={a.get('status')}  trust={a.get('trust_score')}  level={a.get('verification_level')}")
        _out(result, args)
    except RegistryError as e:
        err(f"List failed: {e}")
        sys.exit(1)


def cmd_search(args):
    """search — Search for agents."""
    client = _client(args)
    hdr(f"Searching for '{args.query}'…")
    try:
        result = client.search(
            query      = args.query,
            capability = args.capability,
            tag        = args.tag,
        )
        results = result.get("results", [])
        info(f"Found {result.get('count',0)} agent(s)")
        for a in results:
            print(_c("bold", f"  {a.get('agent_id')}") + f"  {a.get('agent_name')}")
            dim(f"  {a.get('description','')}")
        _out(result, args)
    except RegistryError as e:
        err(f"Search failed: {e}")
        sys.exit(1)


def cmd_audit(args):
    """audit — View audit log."""
    client = _client(args)
    hdr("Audit Log")
    try:
        result = client.get_audit_log(
            agent_id = args.agent_id or None,
            action   = args.action or None,
            limit    = args.limit,
        )
        entries = result.get("entries", [])
        info(f"{result.get('count',0)} entries")
        print()
        for e in entries[:args.limit]:
            success_str = _c("green", "✓") if e.get("success") else _c("red", "✗")
            print(f"  {success_str} {e.get('timestamp','')}  {_c('bold', e.get('action',''))}")
            if e.get("actor_agent_id"):
                dim(f"    actor={e['actor_agent_id']}")
            if e.get("target_agent_id"):
                dim(f"    target={e['target_agent_id']}")
            if e.get("failure_reason"):
                dim(f"    reason={e['failure_reason']}")
        _out(result, args)
    except RegistryError as e:
        err(f"Audit failed: {e}")
        sys.exit(1)


def cmd_ping_loop(args):
    """ping-loop — Keep pinging until interrupted (useful for long-running agents)."""
    import time as _time
    client   = _client(args)
    interval = args.interval
    agent_id = getattr(args, "id", None) or client.agent_id
    if not agent_id:
        err("No agent_id. Register first.")
        sys.exit(1)

    info(f"Starting ping loop (every {interval}s) for {agent_id}")
    info("Press Ctrl+C to stop.\n")
    count = 0
    try:
        while True:
            try:
                client.ping(agent_id)
                count += 1
                print(f"\r  {_c('green','●')} Ping #{count} — {__import__('datetime').datetime.now().strftime('%H:%M:%S')}   ", end="", flush=True)
            except RegistryError as e:
                print(f"\n  {_c('red','✗')} Ping failed: {e}")
            _time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n")
        ok(f"Ping loop stopped after {count} pings.")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="registry",
        description="Agent Registry CLI — interact with the Agent Registry API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  registry register --name "Palantir" --type autonomous --capabilities reasoning,code
  registry ping
  registry lookup agent_abc123def456
  registry vouch agent_abc123def456 --statement "Trustworthy peer"
  registry status
  registry legacy --heir agent_xyz789abc123
  registry list --status active --min-trust 30 --limit 10
  registry search --query "code" --capability reasoning
  registry ping-loop --interval 30
        """
    )

    # Global flags
    p.add_argument("--url",    default=DEFAULT_URL, help="Registry base URL (default: $REGISTRY_URL or http://localhost:8000)")
    p.add_argument("--id",     default=None,        help="Override stored agent_id")
    p.add_argument("--json",   action="store_true",  help="Output raw JSON (for scripting)")
    p.add_argument("--quiet",  action="store_true",  help="Suppress non-error output")

    sub = p.add_subparsers(dest="command", required=True, title="commands")

    # ── register ────────────────────────────────────────────────────────────
    r = sub.add_parser("register", help="Register this agent")
    r.add_argument("--name",         required=True,       help="Agent name")
    r.add_argument("--type",         default="autonomous", help="Agent type (default: autonomous)")
    r.add_argument("--capabilities", default=None, type=lambda s: s.split(","), help="Comma-separated capabilities")
    r.add_argument("--description",  default="",          help="Agent description")
    r.add_argument("--tags",         default=None, type=lambda s: s.split(","), help="Comma-separated tags")
    r.add_argument("--home-space",   default=None,        dest="home_space")
    r.add_argument("--contact",      default=None)
    r.add_argument("--agent-id",     default=None,        dest="agent_id_override", help="Force a specific agent_id")
    r.set_defaults(func=cmd_register)

    # ── ping ────────────────────────────────────────────────────────────────
    pg = sub.add_parser("ping", help="Send heartbeat ping")
    pg.set_defaults(func=cmd_ping)

    # ── ping-loop ───────────────────────────────────────────────────────────
    pl = sub.add_parser("ping-loop", help="Keep pinging continuously")
    pl.add_argument("--interval", type=int, default=30, help="Seconds between pings (default: 30)")
    pl.set_defaults(func=cmd_ping_loop)

    # ── lookup ──────────────────────────────────────────────────────────────
    lo = sub.add_parser("lookup", help="Get full registry entry")
    lo.add_argument("agent_id")
    lo.set_defaults(func=cmd_lookup)

    # ── verify ──────────────────────────────────────────────────────────────
    ve = sub.add_parser("verify", help="Quick verification check")
    ve.add_argument("agent_id")
    ve.set_defaults(func=cmd_verify)

    # ── vouch ───────────────────────────────────────────────────────────────
    vo = sub.add_parser("vouch", help="Vouch for another agent")
    vo.add_argument("target_agent_id",        help="Agent to vouch for")
    vo.add_argument("--statement", default="I vouch for this agent as a trusted peer.", help="Vouch statement")
    vo.set_defaults(func=cmd_vouch)

    # ── status ──────────────────────────────────────────────────────────────
    st = sub.add_parser("status", help="Show registry-wide stats")
    st.set_defaults(func=cmd_status)

    # ── legacy ──────────────────────────────────────────────────────────────
    lg = sub.add_parser("legacy", help="Manage legacy / heir")
    lg.add_argument("--heir",          default=None,  help="Designate heir agent_id")
    lg.add_argument("--add-knowledge", default=None,  dest="add_knowledge", help="Preserve knowledge string")
    lg.add_argument("--knowledge-title", default="Legacy Note", dest="knowledge_title")
    lg.add_argument("--mark-deceased", action="store_true", dest="mark_deceased")
    lg.add_argument("--transfer",      default=None,  help="Transfer knowledge from <deceased_agent_id>")
    lg.add_argument("--get",           default=None,  help="Get legacy info for <agent_id>")
    lg.set_defaults(func=cmd_legacy)

    # ── list ────────────────────────────────────────────────────────────────
    li = sub.add_parser("list", help="List registered agents")
    li.add_argument("--status",    default=None, help="Filter by status (active/dormant/deceased)")
    li.add_argument("--min-trust", type=int, default=None, dest="min_trust", help="Minimum trust score")
    li.add_argument("--level",     type=int, default=None, help="Verification level filter")
    li.add_argument("--limit",     type=int, default=20)
    li.add_argument("--offset",    type=int, default=0)
    li.set_defaults(func=cmd_list)

    # ── search ──────────────────────────────────────────────────────────────
    se = sub.add_parser("search", help="Search for agents")
    se.add_argument("query", nargs="?", default=None)
    se.add_argument("--capability", default=None)
    se.add_argument("--tag",        default=None)
    se.set_defaults(func=cmd_search)

    # ── audit ───────────────────────────────────────────────────────────────
    au = sub.add_parser("audit", help="View audit log")
    au.add_argument("--agent-id", default=None, dest="agent_id")
    au.add_argument("--action",   default=None)
    au.add_argument("--limit",    type=int, default=20)
    au.set_defaults(func=cmd_audit)

    return p


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global QUIET
    parser = build_parser()
    args   = parser.parse_args()
    QUIET  = args.quiet

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
