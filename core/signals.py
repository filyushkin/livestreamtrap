from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json


@receiver(post_migrate)
def setup_periodic_tasks(sender, **kwargs):
    """Create periodic tasks after migration"""
    # Create schedule for every minute
    schedule, created = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.MINUTES,
    )

    # Create periodic task for channel checking
    PeriodicTask.objects.get_or_create(
        interval=schedule,
        name='Periodic channel check',
        task='core.tasks.periodic_channel_check',
        defaults={
            'args': json.dumps([]),
            'kwargs': json.dumps({}),
            'enabled': True
        }
    )