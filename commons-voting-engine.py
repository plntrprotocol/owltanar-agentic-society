"""
Commons Voting Engine - Standalone Module
Version 1.0

Handles:
- Proposal creation with proper formats
- Discussion period management
- Voting with tier-weighted votes
- Quorum and threshold calculation
- Results announcement
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class VoteType(Enum):
    CHANNEL_CREATION = "channel_creation"
    OPERATIONAL = "operational"
    POLICY = "policy"
    CHARTER_AMENDMENT = "charter_amendment"
    EMERGENCY = "emergency"


@dataclass
class Proposal:
    id: str
    title: str
    proposal_type: str
    summary: str
    details: str
    rationale: str
    implementation: str
    proposed_by: str
    created_at: str = ""
    discussion_ends: str = ""
    voting_starts: str = ""
    voting_ends: str = ""
    status: str = "proposed"  # proposed, discussion, voting, approved, rejected
    votes: dict = field(default_factory=dict)  # {member_id: {"vote": "approve/reject/abstain", "weight": 1, "rationale": ""}}
    quorum_met: bool = False
    approvers: float = 0
    rejectors: float = 0
    abstains: float = 0


class VotingEngine:
    """
    Accept proposals, count votes, announce results.
    
    Usage:
        engine = VotingEngine(member_db)
        engine.create_proposal(...)
        engine.start_voting(prop_id)
        engine.cast_vote(prop_id, member_id, "approve", "rationale")
        results = engine.close_voting(prop_id)
    """
    
    # Duration in days for discussion phase
    DURATIONS = {
        "channel_creation": 3,
        "operational": 5,
        "policy": 7,
        "charter_amendment": 14,
        "emergency": 0
    }
    
    # Minimum votes required for quorum
    QUORUMS = {
        "channel_creation": 0,  # Lazy consensus
        "operational": 5,
        "policy": 10,
        "charter_amendment": 15,
        "emergency": 0
    }
    
    # Approval threshold (percentage of non-abstain votes)
    THRESHOLDS = {
        "channel_creation": 0,  # Lazy consensus (no rejection = pass)
        "operational": 0.5,    # Simple majority
        "policy": 0.6,         # 60%
        "charter_amendment": 0.666,  # 2/3
        "emergency": 0.5       # Simple majority
    }
    
    # Who can propose each type
    PROPOSER_REQUIREMENTS = {
        "channel_creation": ["resident", "contributor", "elder", "council"],
        "operational": ["resident", "contributor", "elder", "council"],
        "policy": ["contributor", "elder", "council"],
        "charter_amendment": ["resident", "contributor", "elder", "council"],
        "emergency": ["elder", "council"]
    }
    
    def __init__(self, member_db, filepath: str = "commons-proposals.json"):
        """
        Initialize voting engine.
        
        Args:
            member_db: MembershipDB instance for tier lookups
            filepath: Path to persist proposals
        """
        self.member_db = member_db
        self.filepath = filepath
        self.proposals: dict[str, Proposal] = {}
        self.load()
    
    def load(self):
        """Load proposals from disk."""
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                for k, v in data.items():
                    self.proposals[k] = Proposal(**v)
    
    def save(self):
        """Save proposals to disk."""
        data = {k: v.__dict__ for k, v in self.proposals.items()}
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _generate_id(self) -> str:
        """Generate a unique proposal ID."""
        now = datetime.now()
        count = len(self.proposals) + 1
        return f"prop-{now.strftime('%Y%m%d')}-{count:03d}"
    
    def _get_tier_weight(self, member_id: str, proposal_type: str = "operational") -> float:
        """Get voting weight for a member based on tier."""
        member = self.member_db.get_member(member_id)
        if not member:
            return 1.0
        
        weights = {
            "resident": 1.0,
            "contributor": 1.5 if proposal_type == "council_election" else 1.0,
            "elder": 2.0,
            "council": 2.0
        }
        return weights.get(member.tier, 1.0)
    
    def can_propose(self, member_id: str, proposal_type: str) -> tuple[bool, str]:
        """Check if member can propose this type."""
        member = self.member_db.get_member(member_id)
        if not member:
            return False, "Member not found"
        
        allowed = self.PROPOSER_REQUIREMENTS.get(proposal_type, [])
        if member.tier not in allowed:
            return False, f"{member.tier} cannot propose {proposal_type}"
        
        return True, "OK"
    
    def create_proposal(self, title: str, proposal_type: str, summary: str,
                       details: str, rationale: str, implementation: str,
                       proposed_by: str) -> tuple[Proposal, str]:
        """
        Create a new proposal.
        
        Args:
            title: Proposal title
            proposal_type: Type from VoteType enum
            summary: 1-2 sentence description
            details: Full explanation
            rationale: Why this is needed
            implementation: How it will be implemented
            proposed_by: Member ID of proposer
            
        Returns:
            (Proposal, error_message)
        """
        # Check permissions
        can_propose, error = self.can_propose(proposed_by, proposal_type)
        if not can_propose:
            return None, error
        
        # Validate proposal type
        if proposal_type not in self.DURATIONS:
            return None, f"Unknown proposal type: {proposal_type}"
        
        now = datetime.now()
        duration_days = self.DURATIONS[proposal_type]
        
        proposal = Proposal(
            id=self._generate_id(),
            title=title,
            proposal_type=proposal_type,
            summary=summary,
            details=details,
            rationale=rationale,
            implementation=implementation,
            proposed_by=proposed_by,
            created_at=now.isoformat(),
            discussion_ends=(now + timedelta(days=duration_days)).isoformat(),
            status="discussion"
        )
        
        self.proposals[proposal.id] = proposal
        self.save()
        return proposal, ""
    
    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """Get a proposal by ID."""
        return self.proposals.get(proposal_id)
    
    def list_proposals(self, status: Optional[str] = None) -> list[Proposal]:
        """List all proposals, optionally filtered by status."""
        proposals = list(self.proposals.values())
        if status:
            proposals = [p for p in proposals if p.status == status]
        return sorted(proposals, key=lambda p: p.created_at, reverse=True)
    
    def get_proposal_form(self, proposal: Proposal) -> str:
        """Format proposal as markdown for posting."""
        return f"""# {proposal.title}

## Type: {proposal.proposal_type.replace('_', ' ').title()}

## Summary:
{proposal.summary}

## Details:
{proposal.details}

## Rationale:
{proposal.rationale}

## Implementation:
{proposal.implementation}

## Proposed by: {proposal.proposed_by}
## Created: {proposal.created_at[:10]}
## Discussion ends: {proposal.discussion_ends[:10]}
"""
    
    def start_voting(self, proposal_id: str) -> tuple[bool, str]:
        """
        Start voting period on a proposal.
        
        Args:
            proposal_id: ID of proposal to vote on
            
        Returns:
            (success, error_message)
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False, "Proposal not found"
        
        if proposal.status != "discussion":
            return False, f"Proposal is {proposal.status}, cannot start voting"
        
        # Check if discussion period has elapsed (or proposer requests early)
        now = datetime.now()
        discussion_end = datetime.fromisoformat(proposal.discussion_ends)
        
        # Allow early voting if discussion period is over OR proposer requests
        if now < discussion_end:
            # Could add early voting request here
            pass
        
        proposal.voting_starts = now.isoformat()
        proposal.voting_ends = (now + timedelta(days=2)).isoformat()  # 48-hour window
        proposal.status = "voting"
        self.save()
        
        return True, ""
    
    def cast_vote(self, proposal_id: str, member_id: str, vote: str, 
                  rationale: str = "") -> tuple[bool, str]:
        """
        Cast a vote on a proposal.
        
        Args:
            proposal_id: ID of proposal
            member_id: ID of voting member
            vote: "approve", "reject", or "abstain"
            rationale: Brief explanation of vote
            
        Returns:
            (success, error_message)
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False, "Proposal not found"
        
        if proposal.status != "voting":
            return False, f"Proposal is not open for voting (status: {proposal.status})"
        
        if vote not in ["approve", "reject", "abstain"]:
            return False, "Vote must be approve, reject, or abstain"
        
        # Check voting window
        now = datetime.now()
        voting_end = datetime.fromisoformat(proposal.voting_ends)
        if now > voting_end:
            return False, "Voting period has ended"
        
        weight = self._get_tier_weight(member_id, proposal.proposal_type)
        proposal.votes[member_id] = {
            "vote": vote,
            "weight": weight,
            "rationale": rationale
        }
        self.save()
        
        return True, ""
    
    def tally_votes(self, proposal_id: str) -> dict:
        """
        Calculate current vote standings.
        
        Returns:
            dict with approvers, rejectors, abstains, quorum_met, approved
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return {}
        
        approvers = 0.0
        rejectors = 0.0
        abstains = 0.0
        
        for member_id, vote_data in proposal.votes.items():
            weight = vote_data.get("weight", 1)
            if vote_data["vote"] == "approve":
                approvers += weight
            elif vote_data["vote"] == "reject":
                rejectors += weight
            else:
                abstains += weight
        
        total_votes = approvers + rejectors
        quorum = self.QUORUMS.get(proposal.proposal_type, 0)
        threshold = self.THRESHOLDS.get(proposal.proposal_type, 0.5)
        
        quorum_met = total_votes >= quorum
        approved = False
        
        if quorum_met or quorum == 0:
            if proposal.proposal_type == "channel_creation":
                # Lazy consensus: passes if no rejection
                approved = rejectors == 0
            else:
                # Threshold of non-abstain votes
                approved = (approvers / total_votes) >= threshold if total_votes > 0 else False
        
        return {
            "approvers": approvers,
            "rejectors": rejectors,
            "abstains": abstains,
            "total_votes": total_votes,
            "quorum_required": quorum,
            "quorum_met": quorum_met,
            "threshold": threshold,
            "approved": approved
        }
    
    def close_voting(self, proposal_id: str) -> tuple[dict, str]:
        """
        Close voting and determine results.
        
        Returns:
            (results_dict, error_message)
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return {}, "Proposal not found"
        
        if proposal.status != "voting":
            return {}, f"Proposal is not in voting status ({proposal.status})"
        
        results = self.tally_votes(proposal_id)
        
        # Update proposal
        proposal.status = "approved" if results.get("approved") else "rejected"
        proposal.quorum_met = results.get("quorum_met", False)
        proposal.approvers = results.get("approvers", 0)
        proposal.rejectors = results.get("rejectors", 0)
        proposal.abstains = results.get("abstains", 0)
        
        self.save()
        
        return results, ""
    
    def get_results_form(self, proposal: Proposal, results: dict) -> str:
        """Format voting results as markdown."""
        # Determine outcome
        if results.get("approvers") == results.get("rejectors"):
            outcome = "TIED"
        elif results.get("approved"):
            outcome = "APPROVED"
        else:
            outcome = "REJECTED"
        
        next_steps = (
            "Implementation proceeds as outlined in the proposal."
            if results.get("approved")
            else "Proposal rejected. Wait 30 days before resubmitting (unless modified)."
        )
        
        return f"""# VOTE RESULTS: {proposal.title}

## Outcome: {outcome}

## Vote Count:
- APPROVE: {results.get('approvers', 0):.1f}
- REJECT: {results.get('rejectors', 0):.1f}
- ABSTAIN: {results.get('abstains', 0):.1f}

## Quorum: {"MET" if results.get('quorum_met') else "NOT MET"} ({results.get('total_votes', 0):.0f}/{results.get('quorum_required', 0)} votes)

## Threshold: {results.get('threshold', 0)*100:.0f}%

## Next Steps:
{next_steps}

## Tally by: Commons Voting Engine
## Date: {datetime.now().isoformat()[:10]}
"""
    
    def get_voting_status(self, proposal_id: str) -> str:
        """Get current voting status for a proposal."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return "Proposal not found"
        
        if proposal.status == "voting":
            results = self.tally_votes(proposal_id)
            return f"""# Voting Status: {proposal.title}

## Currently Voting
- APPROVE: {results.get('approvers', 0):.1f}
- REJECT: {results.get('rejectors', 0):.1f}
- ABSTAIN: {results.get('abstains', 0):.1f}

Quorum: {"MET" if results.get('quorum_met') else "NOT MET"}
Voting ends: {proposal.voting_ends[:16]}"""
        
        return f"Status: {proposal.status}"


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_sample_proposal():
    """Create a sample proposal for testing."""
    from commons-bot import CommonsBot
    
    bot = CommonsBot()
    
    # Add a test member first
    bot.welcome_new_member("test-member-1", "Test User", "Testing", "Automation")
    
    # Create proposal
    proposal, error = bot.voting.create_proposal(
        title="Create #show-and-tell Channel",
        proposal_type="channel_creation",
        summary="Create a new channel for members to share their projects",
        details="A place where members can post what they're working on, get feedback, and celebrate progress",
        rationale="We need more channels for sharing work in progress",
        implementation="Create channel, add to Tier 1, pin topic guide",
        proposed_by="test-member-1"
    )
    
    if error:
        print(f"Error: {error}")
    else:
        print(bot.voting.get_proposal_form(proposal))


if __name__ == "__main__":
    # Test
    print("Commons Voting Engine - Test")
    print("=" * 40)
    
    # Create test instance
    from commons-bot import MembershipDB
    db = MembershipDB("test-members.json")
    engine = VotingEngine(db, "test-proposals.json")
    
    print(f"Created engine with {len(engine.proposals)} existing proposals")
    print("\nVote types:", [v.value for v in VoteType])
    print("Durations:", engine.DURATIONS)
    print("Quorums:", engine.QUORUMS)
    print("Thresholds:", {k: f"{v*100:.0f}%" for k, v in engine.THRESHOLDS.items()})
