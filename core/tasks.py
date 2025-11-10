from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.conf import settings
import googleapiclient.discovery
import googleapiclient.errors
import subprocess
import os
import time
from .models import YouTubeChannel, MonitoringTask, LiveStream, Recording

logger = get_task_logger(__name__)


def get_youtube_service():
    """Initialize YouTube API service"""
    return googleapiclient.discovery.build(
        'youtube',
        'v3',
        developerKey=settings.YOUTUBE_API_KEY
    )


@shared_task
def check_channel_exists(handle):
    """
    Check if a YouTube channel exists by handle using search and customUrl verification
    """
    try:
        youtube = get_youtube_service()

        # Clean handle - remove @ if present
        clean_handle = handle.replace('@', '') if handle.startswith('@') else handle

        logger.info(f"Searching for channel with handle: @{clean_handle}")

        # Method 1: Search for channels and verify customUrl
        search_response = youtube.search().list(
            q=f'@{clean_handle}',
            type='channel',
            part='id,snippet',
            maxResults=20
        ).execute()

        # Look for exact customUrl match
        for item in search_response.get('items', []):
            channel_id = item['id']['channelId']

            try:
                # Get detailed channel information
                channel_response = youtube.channels().list(
                    id=channel_id,
                    part='snippet,statistics'
                ).execute()

                if not channel_response.get('items'):
                    continue

                channel_data = channel_response['items'][0]
                snippet = channel_data['snippet']
                statistics = channel_data.get('statistics', {})

                # Check if customUrl exactly matches our handle
                custom_url = snippet.get('customUrl', '')
                if custom_url:
                    # Remove @ from customUrl for comparison
                    clean_custom_url = custom_url.replace('@', '')

                    if clean_custom_url.lower() == clean_handle.lower():
                        # EXACT MATCH FOUND
                        logger.info(f"Exact customUrl match found: {custom_url} = @{clean_handle}")

                        return {
                            'exists': True,
                            'channel_id': channel_id,
                            'title': snippet['title'],
                            'description': snippet.get('description', ''),
                            'thumbnail_url': snippet['thumbnails']['high']['url'],
                            'subscriber_count': int(statistics.get('subscriberCount', 0)),
                            'view_count': int(statistics.get('viewCount', 0)),
                            'video_count': int(statistics.get('videoCount', 0))
                        }

            except googleapiclient.errors.HttpError as e:
                logger.warning(f"API error for channel {channel_id}: {str(e)}")
                continue

        # Method 2: If no exact customUrl match, try to find the most relevant channel
        if search_response.get('items'):
            # Get the first result and assume it's the correct channel
            first_item = search_response['items'][0]
            channel_id = first_item['id']['channelId']

            try:
                channel_response = youtube.channels().list(
                    id=channel_id,
                    part='snippet,statistics'
                ).execute()

                if channel_response.get('items'):
                    channel_data = channel_response['items'][0]
                    snippet = channel_data['snippet']
                    statistics = channel_data.get('statistics', {})

                    custom_url = snippet.get('customUrl', '')

                    logger.info(f"Using first search result: {snippet['title']} (customUrl: {custom_url})")

                    return {
                        'exists': True,
                        'channel_id': channel_id,
                        'title': snippet['title'],
                        'description': snippet.get('description', ''),
                        'thumbnail_url': snippet['thumbnails']['high']['url'],
                        'subscriber_count': int(statistics.get('subscriberCount', 0)),
                        'view_count': int(statistics.get('viewCount', 0)),
                        'video_count': int(statistics.get('videoCount', 0)),
                        'note': 'Найден по первому результату поиска'
                    }

            except googleapiclient.errors.HttpError as e:
                logger.error(f"Error getting channel details: {str(e)}")

        # No channel found
        logger.warning(f"No channel found for handle: @{clean_handle}")
        return {
            'exists': False,
            'error': f'Канал с псевдонимом @{clean_handle} не найден. Проверьте правильность написания.'
        }

    except googleapiclient.errors.HttpError as e:
        error_msg = f"YouTube API error: {e.resp.status} - {e._get_reason()}"
        logger.error(f"YouTube API error for handle {handle}: {error_msg}")
        return {
            'exists': False,
            'error': f'Ошибка YouTube API: {e._get_reason()}'
        }
    except Exception as e:
        logger.error(f"Unexpected error checking channel existence for handle {handle}: {str(e)}")
        return {
            'exists': False,
            'error': f'Неожиданная ошибка при проверке канала: {str(e)}'
        }


@shared_task
def update_channel_live_status(channel_id):
    """
    Update live stream status for a specific channel
    """
    try:
        channel = YouTubeChannel.objects.get(id=channel_id)
        youtube = get_youtube_service()

        # Search for live streams
        search_response = youtube.search().list(
            channelId=channel.channel_id,
            type='video',
            eventType='live',
            part='id,snippet',
            maxResults=50
        ).execute()

        current_stream_ids = set()

        for item in search_response.get('items', []):
            video_id = item['id']['videoId']
            current_stream_ids.add(video_id)

            # Create or update live stream record
            stream, created = LiveStream.objects.get_or_create(
                stream_id=video_id,
                defaults={
                    'channel': channel,
                    'title': item['snippet']['title'],
                    'description': item['snippet'].get('description', ''),
                    'actual_start_time': timezone.now(),
                    'is_active': True
                }
            )

            if created:
                logger.info(f"New live stream detected: {stream.title}")
                # Check if we should record this stream
                if hasattr(channel, 'monitoring_task') and channel.monitoring_task.is_active:
                    start_recording.delay(stream.id)

        # Mark ended streams
        ended_streams = LiveStream.objects.filter(
            channel=channel,
            is_active=True
        ).exclude(stream_id__in=current_stream_ids)

        for stream in ended_streams:
            stream.is_active = False
            stream.actual_end_time = timezone.now()
            stream.save()
            logger.info(f"Live stream ended: {stream.title}")

    except YouTubeChannel.DoesNotExist:
        logger.error(f"Channel with id {channel_id} not found")
    except Exception as e:
        logger.error(f"Error updating live status for channel {channel_id}: {str(e)}")


@shared_task
def start_monitoring_channel(channel_id):
    """
    Start monitoring a channel for live streams
    """
    try:
        channel = YouTubeChannel.objects.get(id=channel_id)

        # Create or update monitoring task
        task, created = MonitoringTask.objects.get_or_create(
            channel=channel,
            defaults={'is_active': True}
        )

        if not created:
            task.is_active = True
            task.save()

        # Do initial status check
        update_channel_live_status.delay(channel_id)

        logger.info(f"Started monitoring channel: {channel.handle} ({channel.title})")

    except YouTubeChannel.DoesNotExist:
        logger.error(f"Channel with id {channel_id} not found")


@shared_task
def stop_monitoring_channel(channel_id):
    """
    Stop monitoring a channel for live streams
    """
    try:
        # Use filter().update() to avoid DoesNotExist exception
        MonitoringTask.objects.filter(channel_id=channel_id).update(is_active=False)
        logger.info(f"Stopped monitoring for channel ID: {channel_id}")

    except Exception as e:
        logger.error(f"Error stopping monitoring for channel {channel_id}: {str(e)}")


@shared_task
def start_recording(stream_id):
    """
    Start recording a live stream
    """
    try:
        stream = LiveStream.objects.get(id=stream_id, is_active=True)

        # Check if already recording
        if hasattr(stream, 'recording') and stream.recording.is_completed is False:
            logger.info(f"Already recording stream: {stream.title}")
            return

        # Create recording record
        recording = Recording.objects.create(live_stream=stream)
        stream.is_recording = True
        stream.save()

        # Start recording process
        record_stream.delay(recording.id)

        logger.info(f"Started recording stream: {stream.title}")

    except LiveStream.DoesNotExist:
        logger.error(f"Stream with id {stream_id} not found")


@shared_task
def record_stream(recording_id):
    """
    Record stream using ytarchive and convert to MP3
    """
    try:
        recording = Recording.objects.get(id=recording_id)
        stream = recording.live_stream
        channel = stream.channel

        # Create filename
        safe_title = "".join(c for c in stream.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f"{channel.handle}_{safe_title}_{timestamp}"
        video_filename = f"{base_filename}.mp4"
        audio_filename = f"{base_filename}.mp3"

        video_path = settings.RECORDINGS_DIR / 'videos' / video_filename
        audio_path = settings.RECORDINGS_DIR / 'audio' / audio_filename

        # Ensure directories exist
        video_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.parent.mkdir(parents=True, exist_ok=True)

        # Record using ytarchive
        stream_url = f"https://www.youtube.com/watch?v={stream.stream_id}"

        try:
            # Record with ytarchive
            ytarchive_cmd = [
                'ytarchive',
                '--merge',
                '-o', str(video_path.with_suffix('')),  # Output without extension
                stream_url,
                'best'
            ]

            logger.info(f"Starting ytarchive recording: {' '.join(ytarchive_cmd)}")
            process = subprocess.Popen(
                ytarchive_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait for process to complete (stream to end)
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                logger.info(f"Successfully recorded stream: {stream.title}")

                # Convert to MP3
                convert_to_mp3(str(video_path), str(audio_path))

                # Update recording record
                recording.original_video_path = f'recordings/videos/{video_filename}'
                recording.audio_path = f'recordings/audio/{audio_filename}'
                recording.recording_finished = timezone.now()
                recording.is_completed = True

                # Calculate file size
                if audio_path.exists():
                    recording.file_size = audio_path.stat().st_size

                recording.save()

                # Update monitoring task count
                if hasattr(channel, 'monitoring_task'):
                    task = channel.monitoring_task
                    task.recordings_count += 1
                    task.save()

                # Update stream
                stream.is_recording = False
                stream.save()

                logger.info(f"Successfully processed recording: {stream.title}")

            else:
                logger.error(f"ytarchive failed for stream {stream.title}: {stderr}")
                recording.delete()

        except Exception as e:
            logger.error(f"Error during recording process for {stream.title}: {str(e)}")
            recording.delete()

    except Recording.DoesNotExist:
        logger.error(f"Recording with id {recording_id} not found")
    except Exception as e:
        logger.error(f"Error in record_stream task: {str(e)}")


def convert_to_mp3(input_path, output_path):
    """
    Convert video file to MP3 using ffmpeg
    """
    try:
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', input_path,
            '-q:a', '0',
            '-map', 'a',
            output_path,
            '-y'  # Overwrite output file
        ]

        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {result.stderr}")
            raise Exception(f"FFmpeg conversion failed: {result.stderr}")

        logger.info(f"Successfully converted to MP3: {output_path}")

        # Remove original video file to save space
        if os.path.exists(input_path):
            os.remove(input_path)

    except Exception as e:
        logger.error(f"Error converting {input_path} to MP3: {str(e)}")
        raise


@shared_task
def periodic_channel_check():
    """
    Periodic task to check all monitored channels for live streams
    """
    try:
        monitored_channels = YouTubeChannel.objects.filter(
            monitoring_task__is_active=True
        )

        for channel in monitored_channels:
            update_channel_live_status.delay(channel.id)

        logger.info(f"Periodic check completed for {monitored_channels.count()} channels")

    except Exception as e:
        logger.error(f"Error in periodic channel check: {str(e)}")