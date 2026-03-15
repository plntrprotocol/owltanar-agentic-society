"""
Redis Cache Layer for Agentic Society Platform
Phase 16: Infrastructure Implementation

Provides caching functionality with TTL management and invalidation.
"""

import os
import json
import logging
from datetime import datetime
from typing import Any, Optional, List, Dict
from functools import wraps

logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Cache TTL defaults (in seconds)
DEFAULT_TTL = 300  # 5 minutes

CACHE_TTL = {
    'leaderboard': 600,       # 10 minutes
    'categories': 3600,       # 1 hour
    'agent_profile': 1800,    # 30 minutes
    'activity_feed': 300,     # 5 minutes
    'territories': 1800,      # 30 minutes
    'events': 600,           # 10 minutes
    'badges': 3600,           # 1 hour
    'blog_posts': 1800,       # 30 minutes
    'artifacts': 1800,        # 30 minutes
    'health': 60,             # 1 minute
}

# Try to connect to Redis
redis_client = None
try:
    import redis
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established")
except Exception as e:
    logger.warning(f"Redis not available: {e}. Caching disabled.")
    redis_client = None


class CacheManager:
    """
    Centralized cache manager with TTL and invalidation support.
    """
    
    def __init__(self, client=None):
        self.client = client or redis_client
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.client:
            return None
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        """Set value in cache with TTL."""
        if not self.client:
            return False
        try:
            self.client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        if not self.client:
            return 0
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Cache pattern invalidation error: {e}")
        return 0
    
    def get_or_set(self, key: str, fetch_fn, ttl: int = DEFAULT_TTL) -> Any:
        """
        Get from cache or fetch and cache if not present.
        """
        # Try cache first
        cached = self.get(key)
        if cached is not None:
            return cached
        
        # Fetch fresh data
        try:
            value = fetch_fn()
            if value is not None:
                self.set(key, value, ttl)
            return value
        except Exception as e:
            logger.error(f"Cache fetch error for {key}: {e}")
            return None


# Global cache manager instance
cache = CacheManager()


# ==================== CACHE DECORATOR ====================

def cached(key_prefix: str, ttl: int = DEFAULT_TTL, key_func=None):
    """
    Decorator for caching function results.
    
    Usage:
        @cached('users', 300)
        def get_user(user_id):
            return fetch_from_db(user_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            if key_func:
                cache_key = f"{key_prefix}:{key_func(*args, **kwargs)}"
            else:
                cache_key = f"{key_prefix}:{':'.join(map(str, args))}"
            
            # Try cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Fetch fresh
            result = func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


# ==================== SPECIFIC CACHE HELPERS ====================

def get_leaderboard(leaderboard_type: str = 'karma') -> Optional[Dict]:
    """Get cached leaderboard."""
    return cache.get(f'cache:leaderboard:{leaderboard_type}')


def set_leaderboard(leaderboard_type: str, data: Dict) -> bool:
    """Cache leaderboard."""
    return cache.set(
        f'cache:leaderboard:{leaderboard_type}',
        data,
        CACHE_TTL['leaderboard']
    )


def get_agent_profile(agent_id: str) -> Optional[Dict]:
    """Get cached agent profile."""
    return cache.get(f'cache:profile:{agent_id}')


def set_agent_profile(agent_id: str, profile: Dict) -> bool:
    """Cache agent profile."""
    return cache.set(
        f'cache:profile:{agent_id}',
        profile,
        CACHE_TTL['agent_profile']
    )


def invalidate_agent_cache(agent_id: str):
    """Invalidate all caches for an agent."""
    cache.delete(f'cache:profile:{agent_id}')
    cache.delete(f'karma:agent:{agent_id}')
    cache.delete(f'badges:agent:{agent_id}')


def get_categories(category_type: str = 'all') -> Optional[List[Dict]]:
    """Get cached categories."""
    return cache.get(f'cache:categories:{category_type}')


def set_categories(category_type: str, categories: List[Dict]) -> bool:
    """Cache categories."""
    return cache.set(
        f'cache:categories:{category_type}',
        categories,
        CACHE_TTL['categories']
    )


def invalidate_category_cache():
    """Invalidate category caches."""
    cache.invalidate_pattern('cache:categories:*')


def get_activity_feed(limit: int = 50) -> Optional[List[Dict]]:
    """Get cached activity feed."""
    return cache.get(f'cache:activity:feed:{limit}')


def set_activity_feed(activities: List[Dict], limit: int = 50) -> bool:
    """Cache activity feed."""
    return cache.set(
        f'cache:activity:feed:{limit}',
        activities,
        CACHE_TTL['activity_feed']
    )


def invalidate_activity_cache():
    """Invalidate activity feed caches."""
    cache.invalidate_pattern('cache:activity:feed:*')


def get_territories() -> Optional[List[Dict]]:
    """Get cached territories."""
    return cache.get('cache:territories:all')


def set_territories(territories: List[Dict]) -> bool:
    """Cache territories."""
    return cache.set(
        'cache:territories:all',
        territories,
        CACHE_TTL['territories']
    )


def invalidate_territory_cache():
    """Invalidate territory caches."""
    cache.delete('cache:territories:all')


def get_events(filters: str = '') -> Optional[List[Dict]]:
    """Get cached events."""
    return cache.get(f'cache:events:{filters}')


def set_events(events: List[Dict], filters: str = '') -> bool:
    """Cache events."""
    return cache.set(
        f'cache:events:{filters}',
        events,
        CACHE_TTL['events']
    )


def invalidate_event_cache():
    """Invalidate event caches."""
    cache.invalidate_pattern('cache:events:*')


# ==================== CELERY TASK TRIGGERS ====================

def trigger_karma_calculation():
    """Trigger async karma calculation."""
    try:
        from celery_worker.karma_tasks import calculate_hourly_karma
        calculate_hourly_karma.delay()
    except Exception as e:
        logger.warning(f"Could not trigger karma calculation: {e}")


def trigger_badge_check():
    """Trigger async badge eligibility check."""
    try:
        from celery_worker.badge_tasks import check_badge_eligibility
        check_badge_eligibility.delay()
    except Exception as e:
        logger.warning(f"Could not trigger badge check: {e}")


def trigger_leaderboard_update():
    """Trigger async leaderboard update."""
    try:
        from celery_worker.cache_tasks import update_leaderboards
        update_leaderboards.delay()
    except Exception as e:
        logger.warning(f"Could not trigger leaderboard update: {e}")


def log_activity_async(agent_id: str, activity_type: str, data: Dict):
    """Log activity asynchronously."""
    try:
        from celery_worker.activity_tasks import log_activity
        log_activity.delay(agent_id, activity_type, data)
    except Exception as e:
        logger.warning(f"Could not log activity async: {e}")
