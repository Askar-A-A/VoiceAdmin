from django.contrib import admin
from .models import AudioFile


@admin.register(AudioFile)
class AudioFileAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'file_sid', 'uploaded_at']
    search_fields = ['name', 'file_sid', 'owner__email']
    readonly_fields = ['file_sid', 'container_sid', 'uploaded_at']
    ordering = ['-uploaded_at']
