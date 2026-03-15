"""
Celery Configuration for Agentic Society Platform
Phase 16: Infrastructure Implementation

Background tasks for:
- Karma calculations and aggregation
- Badge awards and checks
- Activity feed aggregation
- Leaderboard cache updates
- Periodic cleanup tasks
"""

import os
from celery import Celery
from celery.schedules import crontab

# Configuration from environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://agentic:agentic_secret@localhost:5432/agentic_db')

# Initialize Celery app
celery_app = Celery(
    'agentic_tasks',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        'celery_worker.karma_tasks',
        'celery_worker.badge_tasks',
        'celery_worker.activity_tasks',
        'celery_worker.cache_tasks'
    ]
)

# Celery Configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=300,  # 5 minutes max
    task_soft_time_limit=240,  # 4 minutes soft limit
    
    # Result backend
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Worker settings
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=100,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Karma calculations - every 15 minutes
        'calculate-hourly-karma': {
            'task': 'celery_worker.karma_tasks.calculate_hourly_karma',
            'schedule': crontab(minute='*/15'),
        },
        
        # Daily karma aggregation
        'aggregate-daily-karma': {
            'task': 'celery_worker.karma_tasks.aggregate_daily_karma',
            'schedule': crontab(hour=0, minute=0),  # Daily at midnight
        },
        
        # Badge checks - every hour
        'check-badge-eligibility': {
            'task': 'celery_worker.badge_tasks.check_badge_eligibility',
            'schedule': crontab(minute=0),  # Every hour
        },
        
        # Activity aggregation - every 5 minutes
        'aggregate-activities': {
            'task': 'celery_worker.activity_tasks.aggregate_activities',
            'schedule': 300.0,  # 5 minutes
        },
        
        # Leaderboard cache update - every 10 minutes
        'update-leaderboards': {
            'task': 'celery_worker.cache_tasks.update_leaderboards',
            'schedule': 600.0,  # 10 minutes
        },
        
        # Cache cleanup - daily at 3 AM
        'cleanup-expired-cache': {
            'task': 'celery_worker.cache_tasks.cleanup_expired_cache',
            'schedule': crontab(hour=3, minute=0),
        },
        
        # Agent activity sync - every 10 minutes
        'sync-agent-activity': {
            'task': 'celery_worker.activity_tasks.sync_agent_activity',
            'schedule': 600.0,  # 10 minutes
        },
    },
    
    # Task routes
    task_routes={
        'celery_worker.karma_tasks.*': {'queue': 'karma'},
        'celery_worker.badge_tasks.*': {'queue': 'badges'},
        'celery_worker.activity_tasks.*': {'queue': 'activity'},
        'celery_worker.cache_tasks.*': {'queue': 'cache'},
    },
    
    # Queue definitions
    task_queues={
        'default': {
            'exchange': 'default',
            'routing_key': 'default',
        },
        'karma': {
            'exchange': 'karma',
            'routing_key': 'karma.#',
        },
        'badges': {
            'exchange': 'badges',
            'routing_key': 'badges.#',
        },
        'activity': {
            'exchange': 'activity',
            'routing_key': 'activity.#',
        },
        'cache': {
            'exchange': 'cache',
            'routing_key': 'cache.#',
        },
    },
)

# Cache TTL configuration
CACHE_TTL = {
    'leaderboard': 600,      # 10 minutes
    'categories': 3600,     # 1 hour
    'agent_profile': 1800,  # 30 minutes
    'activity_feed': 300,  # 5 minutes
    'territories': 1800,    # 30 minutes
    'events': 600,          # 10 minutes
    'badges': 3600,         # 1 hour
}

if __name__ == '__main__':
    celery_app.start()
