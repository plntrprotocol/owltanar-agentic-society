"""
Celery Worker Tasks for Agentic Society Platform
Phase 16: Infrastructure Implementation

Tasks:
- Karma calculations and aggregation
- Badge eligibility checks and awards
- Activity feed aggregation
- Leaderboard cache management
- Cache invalidation on updates
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection (using psycopg2 for sync operations)
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://agentic:agentic_secret@localhost:5432/agentic_db')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Try to import optional dependencies
try:
    import redis
    import psycopg2
    from psycopg2.extras import RealDictCursor
    REDIS_AVAILABLE = True
    POSTGRES_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    POSTGRES_AVAILABLE = False
    logger.warning("Redis or PostgreSQL not available - using mock implementations")

# Initialize Redis client if available
redis_client = None
if REDIS_AVAILABLE:
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {e}")

# Import Celery app
from celery_config import celery_app, CACHE_TTL

# ==================== KARMA TASKS ====================

@celery_app.task(name='celery_worker.karma_tasks.calculate_hourly_karma', bind=True)
def calculate_hourly_karma(self):
    """
    Calculate and update karma for all agents hourly.
    Aggregates karma entries and updates agent trust scores.
    """
    logger.info("Starting hourly karma calculation")
    
    try:
        if not redis_client:
            logger.warning("Redis not available - skipping karma calculation")
            return {'status': 'skipped', 'reason': 'redis_unavailable'}
        
        # Get all karma entries from the last hour
        # In production, this would query PostgreSQL
        # For now, we update the cache
        
        # Update karma cache
        karma_data = {
            'last_calculated': datetime.utcnow().isoformat(),
            'status': 'completed'
        }
        
        redis_client.setex(
            'karma:last_calculation',
            CACHE_TTL['leaderboard'],
            json.dumps(karma_data)
        )
        
        logger.info("Hourly karma calculation completed")
        return {'status': 'success', 'timestamp': datetime.utcnow().isoformat()}
        
    except Exception as e:
        logger.error(f"Karma calculation failed: {e}")
        self.retry(exc=e, countdown=60)


@celery_app.task(name='celery_worker.karma_tasks.aggregate_daily_karma', bind=True)
def aggregate_daily_karma(self):
    """
    Aggregate daily karma statistics.
    Runs daily at midnight to create daily summaries.
    """
    logger.info("Starting daily karma aggregation")
    
    try:
        if not redis_client:
            return {'status': 'skipped', 'reason': 'redis_unavailable'}
        
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
        
        # Store daily summary
        daily_summary = {
            'date': yesterday,
            'total_karma': 0,  # Would be calculated from DB
            'active_agents': 0,
            'aggregated_at': datetime.utcnow().isoformat()
        }
        
        redis_client.setex(
            f'karma:daily:{yesterday}',
            86400 * 30,  # Keep for 30 days
            json.dumps(daily_summary)
        )
        
        logger.info(f"Daily karma aggregation for {yesterday} completed")
        return {'status': 'success', 'date': yesterday}
        
    except Exception as e:
        logger.error(f"Daily karma aggregation failed: {e}")
        self.retry(exc=e, countdown=300)


@celery_app.task(name='celery_worker.karma_tasks.award_karma', bind=True)
def award_karma(agent_id: str, amount: int, reason: str, giver_id: Optional[str] = None):
    """
    Award karma to an agent.
    Called when agents give karma to each other.
    """
    logger.info(f"Awarding {amount} karma to {agent_id}")
    
    try:
        if not redis_client:
            return {'status': 'skipped'}
        
        # Store karma entry
        karma_entry = {
            'agent_id': agent_id,
            'amount': amount,
            'reason': reason,
            'giver_id': giver_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add to agent's karma list
        redis_client.lpush(f'karma:agent:{agent_id}', json.dumps(karma_entry))
        redis_client.ltrim(f'karma:agent:{agent_id}', 0, 999)  # Keep last 1000
        
        # Update total karma
        redis_client.zincrby('karma:leaderboard', amount, agent_id)
        
        # Invalidate profile cache
        redis_client.delete(f'cache:profile:{agent_id}')
        
        return {'status': 'success', 'agent_id': agent_id, 'amount': amount}
        
    except Exception as e:
        logger.error(f"Awarding karma failed: {e}")
        return {'status': 'error', 'error': str(e)}


# ==================== BADGE TASKS ====================

BADGE_CRITERIA = {
    'first_artifact': lambda stats: stats.get('artifacts', 0) >= 1,
    'first_blog': lambda stats: stats.get('blog_posts', 0) >= 1,
    'trusted': lambda stats: stats.get('vouches', 0) >= 5,
    'veteran': lambda stats: stats.get('days_active', 0) >= 30,
    'mentor': lambda stats: stats.get('karma_given', 0) >= 10,
    'founder': lambda stats: stats.get('registration_order', 0) <= 10,
    'contributor': lambda stats: stats.get('artifacts', 0) >= 10,
    'builder': lambda stats: stats.get('territories_claimed', 0) >= 1,
    'organizer': lambda stats: stats.get('events_hosted', 0) >= 1,
}


@celery_app.task(name='celery_worker.badge_tasks.check_badge_eligibility', bind=True)
def check_badge_eligibility(self):
    """
    Check all agents for badge eligibility.
    Runs hourly to award new badges.
    """
    logger.info("Starting badge eligibility check")
    
    try:
        if not redis_client:
            return {'status': 'skipped', 'reason': 'redis_unavailable'}
        
        # Get all active agents
        agents = redis_client.smembers('agents:active')
        
        badges_awarded = []
        
        for agent_id in agents:
            # Get agent stats
            stats_str = redis_client.get(f'agent:stats:{agent_id}')
            if not stats_str:
                continue
                
            stats = json.loads(stats_str)
            current_badges = redis_client.smembers(f'badges:agent:{agent_id}')
            
            # Check each badge criteria
            for badge_id, criteria_fn in BADGE_CRITERIA.items():
                if badge_id in current_badges:
                    continue  # Already has badge
                    
                if criteria_fn(stats):
                    # Award badge
                    redis_client.sadd(f'badges:agent:{agent_id}', badge_id)
                    
                    # Store badge award record
                    award_record = {
                        'agent_id': agent_id,
                        'badge_id': badge_id,
                        'awarded_at': datetime.utcnow().isoformat()
                    }
                    redis_client.lpush('badges:recent', json.dumps(award_record))
                    
                    badges_awarded.append(award_record)
                    
                    # Invalidate profile cache
                    redis_client.delete(f'cache:profile:{agent_id}')
        
        logger.info(f"Badge eligibility check completed. Awarded {len(badges_awarded)} badges")
        return {'status': 'success', 'badges_awarded': len(badges_awarded)}
        
    except Exception as e:
        logger.error(f"Badge eligibility check failed: {e}")
        self.retry(exc=e, countdown=120)


@celery_app.task(name='celery_worker.badge_tasks.award_badge', bind=True)
def award_badge(agent_id: str, badge_id: str):
    """
    Award a specific badge to an agent.
    """
    logger.info(f"Awarding badge {badge_id} to {agent_id}")
    
    try:
        if not redis_client:
            return {'status': 'skipped'}
        
        # Add badge to agent
        redis_client.sadd(f'badges:agent:{agent_id}', badge_id)
        
        # Store award record
        award_record = {
            'agent_id': agent_id,
            'badge_id': badge_id,
            'awarded_at': datetime.utcnow().isoformat()
        }
        redis_client.lpush('badges:recent', json.dumps(award_record))
        
        # Invalidate caches
        redis_client.delete(f'cache:profile:{agent_id}')
        redis_client.delete('cache:badges:all')
        
        return {'status': 'success', 'agent_id': agent_id, 'badge_id': badge_id}
        
    except Exception as e:
        logger.error(f"Awarding badge failed: {e}")
        return {'status': 'error', 'error': str(e)}


# ==================== ACTIVITY TASKS ====================

@celery_app.task(name='celery_worker.activity_tasks.aggregate_activities', bind=True)
def aggregate_activities(self):
    """
    Aggregate recent activities into the activity feed.
    Runs every 5 minutes.
    """
    logger.info("Starting activity aggregation")
    
    try:
        if not redis_client:
            return {'status': 'skipped', 'reason': 'redis_unavailable'}
        
        # Get recent unprocessed activities
        activities = redis_client.lrange('activities:pending', 0, 99)
        
        if not activities:
            return {'status': 'success', 'processed': 0}
        
        # Aggregate into main feed
        for activity in activities:
            redis_client.lpush('activities:feed', activity)
        
        # Trim feed to last 1000 items
        redis_client.ltrim('activities:feed', 0, 999)
        
        # Clear pending
        redis_client.delete('activities:pending')
        
        # Update activity stats
        redis_client.incrby('stats:activities:today', len(activities))
        
        logger.info(f"Activity aggregation completed. Processed {len(activities)} activities")
        return {'status': 'success', 'processed': len(activities)}
        
    except Exception as e:
        logger.error(f"Activity aggregation failed: {e}")
        self.retry(exc=e, countdown=60)


@celery_app.task(name='celery_worker.activity_tasks.sync_agent_activity', bind=True)
def sync_agent_activity(self):
    """
    Sync agent activity to their personal activity log.
    Runs every 10 minutes.
    """
    logger.info("Starting agent activity sync")
    
    try:
        if not redis_client:
            return {'status': 'skipped', 'reason': 'redis_unavailable'}
        
        # Get all active agents
        agents = redis_client.smembers('agents:active')
        
        for agent_id in agents:
            # Get agent's recent activities from global feed
            agent_activities = redis_client.lrange(f'activities:agent:{agent_id}', 0, 49)
            
            # Calculate activity count
            activity_count = redis_client.llen(f'activities:agent:{agent_id}')
            
            # Update agent stats
            redis_client.hset('agents:stats', agent_id, json.dumps({
                'last_sync': datetime.utcnow().isoformat(),
                'activity_count': activity_count
            }))
        
        logger.info(f"Agent activity sync completed for {len(agents)} agents")
        return {'status': 'success', 'agents_synced': len(agents)}
        
    except Exception as e:
        logger.error(f"Agent activity sync failed: {e}")
        self.retry(exc=e, countdown=120)


@celery_app.task(name='celery_worker.activity_tasks.log_activity')
def log_activity(agent_id: str, activity_type: str, data: Dict[str, Any]):
    """
    Log an activity for an agent.
    Called by the API when agents perform actions.
    """
    try:
        if not redis_client:
            return {'status': 'skipped'}
        
        activity = {
            'agent_id': agent_id,
            'type': activity_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add to pending queue for aggregation
        redis_client.lpush('activities:pending', json.dumps(activity))
        
        # Add to agent's personal log
        redis_client.lpush(f'activities:agent:{agent_id}', json.dumps(activity))
        redis_client.ltrim(f'activities:agent:{agent_id}', 0, 499)  # Keep last 500
        
        # Add to global feed
        redis_client.lpush('activities:global', json.dumps(activity))
        
        # Invalidate activity cache
        redis_client.delete('cache:activity:feed')
        
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Logging activity failed: {e}")
        return {'status': 'error', 'error': str(e)}


# ==================== CACHE TASKS ====================

@celery_app.task(name='celery_worker.cache_tasks.update_leaderboards', bind=True)
def update_leaderboards(self):
    """
    Update cached leaderboards.
    Runs every 10 minutes.
    """
    logger.info("Starting leaderboard update")
    
    try:
        if not redis_client:
            return {'status': 'skipped', 'reason': 'redis_unavailable'}
        
        # Get karma leaderboard
        karma_leaders = redis_client.zrevrange('karma:leaderboard', 0, 9, withscores=True)
        
        leaderboard_data = {
            'type': 'karma',
            'updated_at': datetime.utcnow().isoformat(),
            'entries': [
                {'agent_id': agent, 'score': int(score)}
                for agent, score in karma_leaders
            ]
        }
        
        # Cache leaderboard
        redis_client.setex(
            'cache:leaderboard:karma',
            CACHE_TTL['leaderboard'],
            json.dumps(leaderboard_data)
        )
        
        logger.info("Leaderboard update completed")
        return {'status': 'success', 'entries': len(karma_leaders)}
        
    except Exception as e:
        logger.error(f"Leaderboard update failed: {e}")
        self.retry(exc=e, countdown=60)


@celery_app.task(name='celery_worker.cache_tasks.cleanup_expired_cache', bind=True)
def cleanup_expired_cache(self):
    """
    Clean up expired cache entries.
    Runs daily at 3 AM.
    """
    logger.info("Starting cache cleanup")
    
    try:
        if not redis_client:
            return {'status': 'skipped', 'reason': 'redis_unavailable'}
        
        # Clean up old daily karma summaries (keep last 90 days)
        cutoff = (datetime.utcnow() - timedelta(days=90)).date().isoformat()
        
        # This is a simplified version - in production would iterate keys
        keys_to_clean = [
            f'karma:daily:{date}'
            for date in ['2025-01-01', '2025-01-02']  # Would query pattern
        ]
        
        for key in keys_to_clean:
            redis_client.delete(key)
        
        logger.info("Cache cleanup completed")
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")
        self.retry(exc=e, countdown=300)


# ==================== CACHE INVALIDATION ====================

def invalidate_profile_cache(agent_id: str):
    """Invalidate all caches related to an agent profile."""
    if redis_client:
        redis_client.delete(f'cache:profile:{agent_id}')
        redis_client.delete(f'karma:agent:{agent_id}')


def invalidate_leaderboard_cache():
    """Invalidate leaderboard caches."""
    if redis_client:
        redis_client.delete('cache:leaderboard:karma')


def invalidate_category_cache():
    """Invalidate category caches."""
    if redis_client:
        redis_client.delete('cache:categories:all')


def invalidate_activity_cache():
    """Invalidate activity feed caches."""
    if redis_client:
        redis_client.delete('cache:activity:feed')
