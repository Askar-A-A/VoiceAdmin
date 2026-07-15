from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('audio/', views.audio_list, name='audio_list'),
    path('audio/upload/', views.AudioUploadView.as_view(), name='audio_upload'),
    path('audio/upload/ajax/', views.audio_upload_ajax, name='audio_upload_ajax'),
    path('audio/<int:pk>/', views.audio_detail, name='audio_detail'),
    path('audio/<int:pk>/delete/', views.audio_delete, name='audio_delete'),
    path('audio/<int:pk>/stream/', views.audio_stream, name='audio_stream'),
    path('audio/<int:pk>/download/', views.audio_download, name='audio_download'),
]
