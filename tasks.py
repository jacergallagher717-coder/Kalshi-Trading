"""
Celery tasks for Kalshi Trading System
Minimal configuration to get celery workers running
"""
import os
from celery import Celery

# Get Redis URL from environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

# Create Celery app
app = Celery(
    'kalshi_trading',
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Example task - can be expanded later
@app.task(name='tasks.health_check')
def health_check():
    """Simple health check task"""
    return {'status': 'healthy', 'service': 'celery_worker'}

# Periodic task schedule (for celery beat)
app.conf.beat_schedule = {
    'health-check-every-5-minutes': {
        'task': 'tasks.health_check',
        'schedule': 300.0,  # 5 minutes
    },
}
