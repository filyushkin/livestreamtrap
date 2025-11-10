from django.contrib import admin
from .models import YouTubeChannel, MonitoringTask, LiveStream, Recording

@admin.register(YouTubeChannel)
class YouTubeChannelAdmin(admin.ModelAdmin):
    list_display = ['handle', 'title', 'subscriber_count', 'view_count', 'video_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['handle', 'title']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('handle', 'channel_id', 'title', 'description', 'thumbnail_url')
        }),
        ('Статистика', {
            'fields': ('subscriber_count', 'view_count', 'video_count')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(MonitoringTask)
class MonitoringTaskAdmin(admin.ModelAdmin):
    list_display = ['channel', 'is_active', 'recordings_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Информация о задаче', {
            'fields': ('channel', 'is_active', 'recordings_count')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = ['title', 'channel', 'is_active', 'is_recording', 'actual_start_time']
    list_filter = ['is_active', 'is_recording', 'actual_start_time']
    search_fields = ['title', 'channel__handle']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('channel', 'stream_id', 'title', 'description')
        }),
        ('Время трансляции', {
            'fields': ('scheduled_start_time', 'actual_start_time', 'actual_end_time')
        }),
        ('Статус', {
            'fields': ('is_active', 'is_recording')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ['live_stream', 'is_completed', 'file_size', 'recording_started']
    list_filter = ['is_completed', 'recording_started']
    readonly_fields = ['recording_started', 'recording_finished', 'created_at']
    fieldsets = (
        ('Информация о записи', {
            'fields': ('live_stream', 'is_completed', 'file_size', 'duration')
        }),
        ('Файлы', {
            'fields': ('original_video_path', 'audio_path')
        }),
        ('Время записи', {
            'fields': ('recording_started', 'recording_finished', 'created_at')
        }),
    )