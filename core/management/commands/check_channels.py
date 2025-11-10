from django.core.management.base import BaseCommand
from core.tasks import periodic_channel_check


class Command(BaseCommand):
    help = 'Check all monitored channels for live streams'

    def handle(self, *args, **options):
        self.stdout.write('Starting channel check...')
        periodic_channel_check.delay()
        self.stdout.write(
            self.style.SUCCESS('Channel check task queued successfully')
        )