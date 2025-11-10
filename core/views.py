from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction
import logging
from .models import YouTubeChannel, MonitoringTask, LiveStream, Recording
from .forms import ChannelHandleForm
from .tasks import (
    check_channel_exists,
    update_channel_live_status,
    start_monitoring_channel,
    stop_monitoring_channel
)
import json

logger = logging.getLogger(__name__)


def home(request):
    channels = YouTubeChannel.objects.all().order_by('-created_at')

    if request.method == 'POST':
        form = ChannelHandleForm(request.POST)
        if form.is_valid():
            handle = form.cleaned_data['handle']

            # Check if channel already exists
            if YouTubeChannel.objects.filter(handle=handle).exists():
                messages.warning(request, f'Канал с псевдонимом @{handle} был добавлен в базу данных ранее.')
            else:
                # Check if channel exists on YouTube
                result = check_channel_exists(handle)

                if result['exists']:
                    # Create channel in database
                    channel = YouTubeChannel.objects.create(
                        handle=handle,
                        channel_id=result['channel_id'],
                        title=result['title'],
                        description=result.get('description', ''),
                        thumbnail_url=result.get('thumbnail_url', ''),
                        subscriber_count=result.get('subscriber_count', 0),
                        view_count=result.get('view_count', 0),
                        video_count=result.get('video_count', 0)
                    )

                    if result.get('note'):
                        messages.warning(request, f'Канал @{handle} найден. {result["note"]}')
                    else:
                        messages.success(request, f'Канал @{handle} найден и добавлен в базу данных.')

                    # Логируем информацию о найденном канале для отладки
                    logger.info(f"Channel added: {result['title']} (ID: {result['channel_id']})")

                else:
                    error_msg = result.get('error', f'Канал с псевдонимом @{handle} не существует.')
                    messages.error(request, error_msg)

            return redirect('home')
    else:
        form = ChannelHandleForm()

    # Prepare channel data for template
    channel_data = []
    for index, channel in enumerate(channels, 1):
        has_task = hasattr(channel, 'monitoring_task') and channel.monitoring_task.is_active
        channel_data.append({
            'index': index,
            'channel': channel,
            'has_task': has_task,
            'live_count': channel.current_live_count
        })

    context = {
        'form': form,
        'channel_data': channel_data,
    }
    return render(request, 'core/home.html', context)


@require_http_methods(['POST'])
def delete_channel(request, channel_id):
    try:
        channel = get_object_or_404(YouTubeChannel, id=channel_id)

        # Get channel name before deletion for message
        channel_name = channel.handle

        # Stop monitoring task first
        if hasattr(channel, 'monitoring_task'):
            # Stop the Celery task
            stop_monitoring_channel.delay(channel.id)
            # Delete the monitoring task
            channel.monitoring_task.delete()

        # Delete all related recordings and their files
        recordings = Recording.objects.filter(live_stream__channel=channel)
        for recording in recordings:
            # This will also delete the associated files due to the delete method in Recording model
            recording.delete()

        # Delete all live streams
        LiveStream.objects.filter(channel=channel).delete()

        # Finally delete the channel itself
        channel.delete()

        messages.success(request, f'Канал @{channel_name} полностью удалён из базы данных.')
        logger.info(f"Channel @{channel_name} successfully deleted")

    except Exception as e:
        logger.error(f"Error deleting channel {channel_id}: {str(e)}")
        messages.error(request, f'Ошибка при удалении канала: {str(e)}')

    return redirect('home')


@require_http_methods(['POST'])
def toggle_monitoring(request, channel_id):
    channel = get_object_or_404(YouTubeChannel, id=channel_id)

    if hasattr(channel, 'monitoring_task') and channel.monitoring_task.is_active:
        # Stop monitoring
        stop_monitoring_channel.delay(channel.id)
        messages.success(request, f'Мониторинг канала @{channel.handle} остановлен.')
    else:
        # Start monitoring
        start_monitoring_channel.delay(channel.id)
        messages.success(request, f'Мониторинг канала @{channel.handle} запущен.')

    return redirect('home')


def tasks_view(request):
    active_tasks = MonitoringTask.objects.filter(is_active=True).select_related('channel').order_by('-created_at')

    task_data = []
    for index, task in enumerate(active_tasks, 1):
        task_data.append({
            'index': index,
            'task': task,
            'channel': task.channel
        })

    context = {
        'task_data': task_data
    }
    return render(request, 'core/tasks.html', context)


@require_http_methods(['POST'])
def stop_task(request, task_id):
    task = get_object_or_404(MonitoringTask, id=task_id, is_active=True)
    stop_monitoring_channel.delay(task.channel.id)

    messages.success(request, f'Задача мониторинга для канала @{task.channel.handle} снята.')
    return redirect('tasks')


def downloads_view(request):
    completed_recordings = Recording.objects.filter(
        is_completed=True
    ).select_related(
        'live_stream',
        'live_stream__channel'
    ).order_by('-created_at')

    download_data = []
    for index, recording in enumerate(completed_recordings, 1):
        download_data.append({
            'index': index,
            'recording': recording,
            'live_stream': recording.live_stream,
            'channel': recording.live_stream.channel
        })

    context = {
        'download_data': download_data
    }
    return render(request, 'core/downloads.html', context)


@require_http_methods(['POST'])
def delete_recording(request, recording_id):
    recording = get_object_or_404(Recording, id=recording_id, is_completed=True)
    recording.delete()

    messages.success(request, 'Запись трансляции удалена.')
    return redirect('downloads')


def get_live_counts(request):
    """AJAX endpoint to get current live counts for all channels"""
    channels = YouTubeChannel.objects.all()
    data = {}

    for channel in channels:
        data[channel.id] = channel.current_live_count

    return JsonResponse(data)