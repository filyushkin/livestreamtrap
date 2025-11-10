from django.db import models
import os
from django.utils import timezone
from django.core.exceptions import ValidationError


class YouTubeChannel(models.Model):
    handle = models.CharField(max_length=30, unique=True)
    channel_id = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    subscriber_count = models.BigIntegerField(default=0)
    view_count = models.BigIntegerField(default=0)
    video_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'youtube_channels'
        verbose_name = 'YouTube Channel'
        verbose_name_plural = 'YouTube Channels'

    def __str__(self):
        return f"{self.title} (@{self.handle})"

    def clean(self):
        if len(self.handle) < 3 or len(self.handle) > 30:
            raise ValidationError('Handle must be between 3 and 30 characters')

    @property
    def current_live_count(self):
        return self.live_streams.filter(is_active=True).count()


class MonitoringTask(models.Model):
    channel = models.OneToOneField(
        YouTubeChannel,
        on_delete=models.CASCADE,
        related_name='monitoring_task'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    recordings_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'monitoring_tasks'
        verbose_name = 'Monitoring Task'
        verbose_name_plural = 'Monitoring Tasks'

    def __str__(self):
        return f"Monitoring: {self.channel.handle}"


class LiveStream(models.Model):
    channel = models.ForeignKey(
        YouTubeChannel,
        on_delete=models.CASCADE,
        related_name='live_streams'
    )
    stream_id = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    scheduled_start_time = models.DateTimeField(null=True, blank=True)
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_recording = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'live_streams'
        verbose_name = 'Live Stream'
        verbose_name_plural = 'Live Streams'
        ordering = ['-actual_start_time']

    def __str__(self):
        return self.title

    @property
    def duration(self):
        if self.actual_start_time and self.actual_end_time:
            return self.actual_end_time - self.actual_start_time
        elif self.actual_start_time:
            return timezone.now() - self.actual_start_time
        return None


class Recording(models.Model):
    live_stream = models.OneToOneField(
        LiveStream,
        on_delete=models.CASCADE,
        related_name='recording'
    )
    original_video_path = models.FileField(
        upload_to='recordings/videos/',
        null=True,
        blank=True
    )
    audio_path = models.FileField(
        upload_to='recordings/audio/',
        null=True,
        blank=True
    )
    file_size = models.BigIntegerField(default=0)
    duration = models.DurationField(null=True, blank=True)
    recording_started = models.DateTimeField(auto_now_add=True)
    recording_finished = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recordings'
        verbose_name = 'Recording'
        verbose_name_plural = 'Recordings'
        ordering = ['-created_at']

    def __str__(self):
        return f"Recording: {self.live_stream.title}"

    def delete(self, *args, **kwargs):
        """Override delete to remove associated files"""
        try:
            # Delete associated files if they exist
            if self.original_video_path and os.path.isfile(self.original_video_path.path):
                os.remove(self.original_video_path.path)
            if self.audio_path and os.path.isfile(self.audio_path.path):
                os.remove(self.audio_path.path)
        except Exception as e:
            # Log error but continue with deletion
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error deleting files for recording {self.id}: {str(e)}")

        super().delete(*args, **kwargs)

    @property
    def download_url(self):
        if self.audio_path and self.is_completed:
            return self.audio_path.url
        return None