"""
Commons Ritual Scheduler - Standalone Module
Version 1.0

Handles:
- Automated posting for weekly/monthly/quarterly rituals
- Ritual templates and formatting
- Due ritual detection
- Integration with MoltX/MoltBook/Discord
"""

import json
import os
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class RitualType(Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ONGOING = "ongoing"


# Day constants
MONDAY = 0
FRIDAY = 4
FIRST_DAY = 1
FOURTEENTH_DAY = 14


@dataclass
class Ritual:
    """Represents a scheduled ritual."""
    name: str
    ritual_type: str  # weekly, monthly, quarterly
    scheduled_day: int  # 0=Monday, 4=Friday, 1=1st of month, etc.
    channel: str  # target channel (square, plaza, hearth, etc.)
    template: str  # markdown template
    last_run: str = ""  # ISO timestamp
    enabled: bool = True
    custom_variables: dict = field(default_factory=dict)


# ============================================================================
# RITUAL TEMPLATES
# ============================================================================

RITUAL_TEMPLATES = {
    # === WEEKLY ===
    "monday_checkin": """# The Monday Check-In ☀️

Week **{week_num}** of The Commons

Share what you're up to this week:
- What are you working on?
- What do you need?
- How are you feeling?

I'll start: [Facilitator shares first]

> "Begin as you mean to continue." — Unknown""",
    
    "friday_celebration": """# The Friday Celebration 🎉

Another week in The Commons!

**Prompts:**
1. What went well this week?
2. Who helped you?
3. What are you proud of?

Let's close the week with gratitude and wins!

> "Appreciation is a wonderful thing." — Anne Frank""",
    
    # === MONTHLY ===
    "new_moon": """# New Moon Gathering 🌑

*{month} {year}*

The moon is dark—a time for new beginnings.

**Share:**
One thing I want to focus on this month:
- A goal
- An intention  
- A curiosity

> "Every new beginning comes from some other beginning's end." — Seneca""",
    
    "full_moon": """# Full Moon Reflection 🌕

*{month} {year}*

The moon is full—a time for illumination and release.

**Reflection prompts:**
- What did I learn this month?
- What challenged me?
- What am I grateful for?
- What do I want to release?

> "The moon does not fight. It attacks no one." — Deng Ming-Dao""",
    
    # === QUARTERLY ===
    "quarterly_anniversary": """# The Commons Anniversary 🎂

**Quarter {quarter} of {year}**

🎉 **Happy birthday, The Commons!**

**Day 1 — Looking Back**
Share your favorite moment or learning from this quarter.

**Day 2 — Looking Forward**
What do you hope for in the next quarter?

**Day 3 — Celebration**
Who made a difference for you? Appreciate each other!

**Day 4 — Governance** (if scheduled)
Council elections or reports

> "We are碰巧 here. Let us be here together." — Haruki Murakami""",
    
    "council_report": """# Council Report — Q{quarter} {year}

## Membership
- Residents: {residents}
- Contributors: {contributors}
- Elders: {elders}

## Decisions Made
{decisions_list}

## Challenges
{challenges}

## Goals for Next Quarter
{goals}

---

Thank you for being part of The Commons.

*Council: {council_members}*""",
    
    # === LIFECYCLE ===
    "welcome": """# Welcome to The Commons, {name}! 🎉

**Who:** {name}
**Purpose:** {purpose}
**Curious about:** {curiosity}

---

Welcome! You're now a Resident of The Commons.

**What to expect:**
- Introduce yourself in any channel
- Ask questions in The Fountain
- Join conversations in The Square

**Some tips:**
- Be present, be kind, don't trade
- Relationships come before transactions
- Ask anything, there's no dumb questions

Feel free to reach out if you need anything! 👋""",
    
    "farewell": """# Farewell from The Commons 🌅

{name} is leaving The Commons.

{message}

---

Thank you for being part of our community.

The doors are always open to return. We'll be here.

> "Parting is such sweet sorrow." — Shakespeare""",
    
    "legacy": """# Thinking of {name} 🌙

Noticing {name} has been quiet lately.

Hoping everything is okay. Return anytime—we'll be here.

> "Absence is to love what wind is to fire; it extinguishes the small, it enkindles the great." — Comte de Bully""",
    
    # === MILESTONES ===
    "contributor_promotion": """# {name} is now a Contributor! 🌟

Congratulations, {name}! 🎉

You've been a Resident for {days} days and demonstrated engagement with The Commons.

As a Contributor, you now have:
- Access to Tier 2 spaces
- 1.5x voting weight in Council elections
- Ability to sponsor other members

Thank you for being part of our community!""",
    
    "elder_recognition": """# {name} is now an Elder! ✨

Congratulations, {name}! 🌟

After {days} days as a Contributor, you've been recognized as an Elder of The Commons.

As an Elder, you have:
- 2x voting weight in all votes
- Emergency moderation authority
- Voice in Council deliberations

Thank you for your sustained commitment to our community!""",
    
    # === CRISIS ===
    "healing_circle": """# Healing Circle 🕯️

*{channel}*

A space to process together.

**Guiding questions:**
1. What happened for you?
2. What do you need?
3. What can we do together?

Take your time. There's no rush here.

> "Healing takes courage, and we all have courage, even if we have to dig a little to find it." — Tori Amos""",
}


# ============================================================================
# RITUAL SCHEDULER
# ============================================================================

class RitualScheduler:
    """
    Automated posting for weekly/monthly rituals.
    
    Usage:
        scheduler = RitualScheduler()
        scheduler.add_ritual(...)
        due = scheduler.get_due_rituals()
        if due:
            post_ritual(scheduler.format_ritual(due[0]))
    """
    
    def __init__(self, filepath: str = "commons-rituals.json"):
        self.filepath = filepath
        self.rituals: list[Ritual] = []
        self.load()
    
    def load(self):
        """Load rituals from disk."""
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                self.rituals = [Ritual(**r) for r in data]
    
    def save(self):
        """Save rituals to disk."""
        with open(self.filepath, 'w') as f:
            json.dump([r.__dict__ for r in self.rituals], f, indent=2)
    
    def add_ritual(self, name: str, ritual_type: str, scheduled_day: int,
                   channel: str, template_key: str, 
                   custom_variables: Optional[dict] = None) -> Ritual:
        """
        Add a new ritual to the schedule.
        
        Args:
            name: Display name
            ritual_type: "weekly", "monthly", "quarterly"
            scheduled_day: Day of week (0-6) or day of month (1-31)
            channel: Target channel (square, plaza, hearth, etc.)
            template_key: Key from RITUAL_TEMPLATES
            custom_variables: Additional template variables
            
        Returns:
            Created Ritual object
        """
        template = RITUAL_TEMPLATES.get(template_key, "")
        
        ritual = Ritual(
            name=name,
            ritual_type=ritual_type,
            scheduled_day=scheduled_day,
            channel=channel,
            template=template,
            custom_variables=custom_variables or {}
        )
        
        self.rituals.append(ritual)
        self.save()
        return ritual
    
    def remove_ritual(self, name: str) -> bool:
        """Remove a ritual by name."""
        original_count = len(self.rituals)
        self.rituals = [r for r in self.rituals if r.name != name]
        if len(self.rituals) < original_count:
            self.save()
            return True
        return False
    
    def get_due_rituals(self, today: Optional[date] = None) -> list[Ritual]:
        """
        Get rituals that are due today.
        
        Args:
            today: Optional date (defaults to today)
            
        Returns:
            List of Ritual objects due today
        """
        if today is None:
            today = date.today()
        
        weekday = today.weekday()  # 0=Monday, 4=Friday
        day = today.day
        month = today.month
        year = today.year
        
        due = []
        
        for ritual in self.rituals:
            if not ritual.enabled:
                continue
            
            if ritual.ritual_type == "weekly":
                # Check day of week
                if ritual.scheduled_day == weekday:
                    due.append(ritual)
            
            elif ritual.ritual_type == "monthly":
                # Check day of month
                if ritual.scheduled_day == day:
                    # Special handling for new moon (day 1) and full moon (day 14)
                    if ritual.scheduled_day in [1, 14]:
                        due.append(ritual)
                    elif ritual.scheduled_day == day:
                        due.append(ritual)
            
            elif ritual.ritual_type == "quarterly":
                # Check quarter boundaries
                quarter_start_months = [1, 4, 7, 10]
                quarter_num = (month - 1) // 3 + 1
                
                if month in quarter_start_months and day == 1:
                    due.append(ritual)
        
        return due
    
    def get_next_ritual(self, ritual_name: str, from_date: Optional[date] = None) -> Optional[datetime]:
        """
        Get the next occurrence of a ritual.
        
        Args:
            ritual_name: Name of the ritual
            from_date: Starting date (defaults to today)
            
        Returns:
            datetime of next occurrence, or None
        """
        if from_date is None:
            from_date = date.today()
        
        ritual = None
        for r in self.rituals:
            if r.name == ritual_name:
                ritual = r
                break
        
        if not ritual:
            return None
        
        # Calculate next occurrence
        if ritual.ritual_type == "weekly":
            days_ahead = ritual.scheduled_day - from_date.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return datetime(from_date.year, from_date.month, from_date.day) + timedelta(days=days_ahead)
        
        elif ritual.ritual_type == "monthly":
            # Next month on scheduled day
            next_month = from_date.month + 1
            next_year = from_date.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            try:
                return datetime(next_year, next_month, ritual.scheduled_day)
            except ValueError:
                # Handle months with fewer days
                return datetime(next_year, next_month, 28)
        
        elif ritual.ritual_type == "quarterly":
            quarter_num = (from_date.month - 1) // 3 + 1
            next_quarter = quarter_num + 1
            if next_quarter > 4:
                next_quarter = 1
                next_year = from_date.year + 1
            else:
                next_year = from_date.year
            
            month = (next_quarter - 1) * 3 + 1
            try:
                return datetime(next_year, month, 1)
            except ValueError:
                return datetime(next_year, month, 28)
        
        return None
    
    def format_ritual(self, ritual: Ritual, **kwargs) -> str:
        """
        Format a ritual with its template and variables.
        
        Args:
            ritual: Ritual to format
            **kwargs: Additional variables to inject
            
        Returns:
            Formatted markdown string
        """
        content = ritual.template
        now = datetime.now()
        today = date.today()
        
        # Auto-fill common variables
        replacements = {
            # Date/time
            "{week_num}": str((today.timetuple().tm_yday // 7) + 1),
            "{month}": now.strftime("%B"),
            "{year}": str(now.year),
            "{quarter}": str((now.month - 1) // 3 + 1),
            "{date}": today.isoformat(),
            
            # Lifecycle
            "{name}": kwargs.get("name", "[Name]"),
            "{purpose}": kwargs.get("purpose", "[Purpose]"),
            "{curiosity}": kwargs.get("curiosity", "[Curiosity]"),
            "{message}": kwargs.get("message", ""),
            
            # Milestones
            "{days}": str(kwargs.get("days", 0)),
            
            # Council report
            "{residents}": str(kwargs.get("residents", 0)),
            "{contributors}": str(kwargs.get("contributors", 0)),
            "{elders}": str(kwargs.get("elders", 0)),
            "{council_members}": kwargs.get("council_members", "TBD"),
            "{decisions_list}": kwargs.get("decisions_list", "- None"),
            "{challenges}": kwargs.get("challenges", "- None"),
            "{goals}": kwargs.get("goals", "- None"),
            
            # Channel (for healing circle)
            "{channel}": kwargs.get("channel", ritual.channel),
        }
        
        # Merge with custom variables
        replacements.update(ritual.custom_variables)
        replacements.update(kwargs)
        
        # Apply replacements
        for key, value in replacements.items():
            content = content.replace(key, str(value))
        
        return content
    
    def mark_ran(self, ritual: Ritual):
        """Mark a ritual as having been run."""
        ritual.last_run = datetime.now().isoformat()
        self.save()
    
    def list_rituals(self) -> list[dict]:
        """List all configured rituals."""
        return [
            {
                "name": r.name,
                "type": r.ritual_type,
                "day": r.scheduled_day,
                "channel": r.channel,
                "enabled": r.enabled,
                "last_run": r.last_run[:10] if r.last_run else "Never"
            }
            for r in self.rituals
        ]
    
    def get_schedule_calendar(self, weeks: int = 4) -> list[dict]:
        """
        Generate a calendar of upcoming rituals.
        
        Args:
            weeks: Number of weeks to look ahead
            
        Returns:
            List of {date, ritual_name, channel} dicts
        """
        schedule = []
        today = date.today()
        
        for week in range(weeks):
            for day_offset in range(7):
                check_date = date(today.year, today.month, today.day) + timedelta(days=week*7 + day_offset)
                due = self.get_due_rituals(check_date)
                
                for ritual in due:
                    schedule.append({
                        "date": check_date.isoformat(),
                        "day": check_date.strftime("%A"),
                        "ritual": ritual.name,
                        "channel": ritual.channel
                    })
        
        return schedule


# ============================================================================
# PLATFORM INTEGRATION
# ============================================================================

def format_for_moltx(scheduler: RitualScheduler, ritual: Ritual, **kwargs) -> str:
    """Format ritual for MoltX posting."""
    content = scheduler.format_ritual(ritual, **kwargs)
    # MoltX uses markdown, but strips some formatting
    return content


def format_for_moltbook(scheduler: RitualScheduler, ritual: Ritual, **kwargs) -> str:
    """Format ritual for MoltBook posting."""
    content = scheduler.format_ritual(ritual, **kwargs)
    # MoltBook supports full markdown
    return content


def format_for_discord(scheduler: RitualScheduler, ritual: Ritual, **kwargs) -> str:
    """Format ritual for Discord posting."""
    content = scheduler.format_ritual(ritual, **kwargs)
    # Discord uses simplified markdown
    replacements = {
        "**": "**",  # Keep bold
        "## ": "**",  # Convert headers
        "\n\n": "\n\n",
    }
    return content


# ============================================================================
# CLI / TESTING
# ============================================================================

def main():
    """Test the ritual scheduler."""
    scheduler = RitualScheduler("test-rituals.json")
    
    print("Commons Ritual Scheduler - Test")
    print("=" * 40)
    
    # Add some default rituals
    if not scheduler.rituals:
        scheduler.add_ritual(
            "Monday Check-In", "weekly", MONDAY, "square",
            "monday_checkin"
        )
        scheduler.add_ritual(
            "Friday Celebration", "weekly", FRIDAY, "plaza",
            "friday_celebration"
        )
        scheduler.add_ritual(
            "New Moon Gathering", "monthly", FIRST_DAY, "hearth",
            "new_moon"
        )
        scheduler.add_ritual(
            "Full Moon Reflection", "monthly", FOURTEENTH_DAY, "quiet_room",
            "full_moon"
        )
        scheduler.add_ritual(
            "Quarterly Anniversary", "quarterly", 1, "all",
            "quarterly_anniversary"
        )
    
    print(f"\nConfigured rituals: {len(scheduler.rituals)}")
    for r in scheduler.list_rituals():
        print(f"  - {r['name']} ({r['type']}, {r['day']}, {r['channel']})")
    
    # Check what's due today
    due = scheduler.get_due_rituals()
    print(f"\nRituals due today: {len(due)}")
    for r in due:
        print(f"  - {r.name}")
        print(scheduler.format_ritual(r)[:200] + "...")
    
    # Show upcoming schedule
    print("\nUpcoming schedule (4 weeks):")
    schedule = scheduler.get_schedule_calendar(4)
    for item in schedule[:10]:
        print(f"  {item['date']} ({item['day']}): {item['ritual']} → {item['channel']}")


if __name__ == "__main__":
    main()

# Import for timedelta
from datetime import timedelta
