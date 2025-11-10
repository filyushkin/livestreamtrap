from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('tasks/', views.tasks_view, name='tasks'),
    path('downloads/', views.downloads_view, name='downloads'),
    path('channel/<int:channel_id>/delete/', views.delete_channel, name='delete_channel'),
    path('channel/<int:channel_id>/toggle-monitoring/', views.toggle_monitoring, name='toggle_monitoring'),
    path('task/<int:task_id>/stop/', views.stop_task, name='stop_task'),
    path('recording/<int:recording_id>/delete/', views.delete_recording, name='delete_recording'),
    path('api/live-counts/', views.get_live_counts, name='get_live_counts'),
]